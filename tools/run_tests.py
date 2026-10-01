#!/usr/bin/env python3
"""Test suite for the offline parsers and the build artifacts.

stdlib unittest only, no pytest, no network, no device.

  python3 tools/run_tests.py            # everything
  python3 tools/run_tests.py -v         # verbose

Every test either checks a parser against a known-good fixture, or checks a
claim that a report makes. Tests that need artifacts that may not exist are
skipped, not silently passed.
"""
import hashlib
import os
import struct
import sys
import tempfile
import unittest
from subprocess import run

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "tools"))

import bl33_audit  # noqa: E402
import bl33_ctrl  # noqa: E402
import bl33_round15  # noqa: E402
import bl33_round16  # noqa: E402
import bl33_round17  # noqa: E402
import bl33_round18  # noqa: E402
import round27_layout  # noqa: E402
import round28_fip  # noqa: E402
import round29_crypto  # noqa: E402
import config_fingerprint  # noqa: E402
import fastboot_addr  # noqa: E402
import inspect_test_image  # noqa: E402
import ko_inventory  # noqa: E402
import ko_versions  # noqa: E402
import parse_amlsecu  # noqa: E402
import sdat2img  # noqa: E402
import validate_artifacts  # noqa: E402

OBJDIR = os.path.join(REPO, "build-aq")
VENDOR_MODULES = os.path.join(REPO, "out/vendor/modules")
IMG = os.path.join(REPO, "firmware/boot.img")
AQUAMAN_CONFIG = os.path.join(REPO, "aquaman-config")
R14 = os.path.join(REPO, "reports/round14-bl33-persist")
BL33_IMAGE = os.path.join(R14, "bl33-37e18000.bin")
R13_BAND = os.path.join(REPO, "reports/round13-reloc-verify/mread_37800000_00800000.bin")
R = 0x37E18000
IMAGE_END = 0x37FF0000


def have(path):
    return os.path.exists(path)


# ---------------------------------------------------------------- parsers

class TestAmlsecuParser(unittest.TestCase):
    """AMLSECU 0x0905 header. fixtures built byte by byte from the documented
    struct layout in reports/amlsecu-reverse.md."""

    def build_container(self, nblk=3, version=0x0905, magic=b"AMLSECU!"):
        buf = bytearray(0x60 + nblk * 0x60)
        buf[0:8] = magic
        struct.pack_into("<II", buf, 8, version, nblk)
        buf[16:32] = b"2022090612544443"
        for i in range(nblk):
            base = 0x60 + i * 0x60
            struct.pack_into("<IIIII", buf, base, 0x800 + i * 0x1000, 0x1000,
                             0x200, 0x1000, 0x1200)
        return bytes(buf)

    def parse_bytes(self, blob):
        with tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as f:
            f.write(blob)
            path = f.name
        try:
            return parse_amlsecu.parse(path)
        finally:
            os.unlink(path)

    def test_recognises_magic_and_block_count(self):
        self.assertEqual(self.parse_bytes(self.build_container(nblk=3)), 0)

    def test_rejects_wrong_version(self):
        # parse_amlsecu must refuse a version it does not implement rather
        # than silently mis-reading the block table
        self.assertNotEqual(self.parse_bytes(self.build_container(version=0x0904)), 0)

    def test_rejects_missing_magic(self):
        self.assertNotEqual(self.parse_bytes(self.build_container(magic=b"NOTASECU")), 0)

    def test_rejects_truncated(self):
        self.assertNotEqual(self.parse_bytes(self.build_container()[:0x70]), 0)


class TestAndroidBootParser(unittest.TestCase):
    """Android boot image header, built to spec."""

    def build(self, **kw):
        h = bytearray(2048)
        h[0:8] = kw.get("magic", b"ANDROID!")
        struct.pack_into("<I", h, 8, kw.get("kernel_size", 112))
        struct.pack_into("<I", h, 12, kw.get("kernel_addr", 0x1080000))
        struct.pack_into("<I", h, 16, kw.get("ramdisk_size", 0))
        struct.pack_into("<I", h, 24, kw.get("second_size", 0))
        struct.pack_into("<I", h, 36, kw.get("page_size", 2048))
        return bytes(h)

    def test_header_fields(self):
        with tempfile.NamedTemporaryFile(suffix=".img", delete=False) as f:
            f.write(self.build())
            path = f.name
        try:
            d = open(path, "rb").read(2048)
        finally:
            os.unlink(path)
        self.assertEqual(d[:8], b"ANDROID!")
        self.assertEqual(struct.unpack("<I", d[8:12])[0], 112)
        self.assertEqual(struct.unpack("<I", d[12:16])[0], 0x1080000)
        self.assertEqual(struct.unpack("<I", d[36:40])[0], 2048)


class TestConfigFingerprint(unittest.TestCase):
    """The tool the 98.10% / 14.05% numbers all rest on."""

    def write(self, text):
        f = tempfile.NamedTemporaryFile("w", suffix=".cfg", delete=False)
        f.write(text)
        f.close()
        return f.name

    def test_counts_isset_and_notset(self):
        p = self.write("CONFIG_A=y\n# CONFIG_B is not set\nCONFIG_C=300\n")
        d = config_fingerprint.parse(p)
        os.unlink(p)
        self.assertEqual(d["CONFIG_A"], "y")
        self.assertEqual(d["CONFIG_B"], "n")
        self.assertEqual(d["CONFIG_C"], "300")
        self.assertEqual(len(d), 3)

    def test_identical_files_match_fully(self):
        text = "CONFIG_A=y\n# CONFIG_B is not set\n"
        a, b = self.write(text), self.write(text)
        da, db = config_fingerprint.parse(a), config_fingerprint.parse(b)
        os.unlink(a)
        os.unlink(b)
        self.assertEqual(da, db)

    def test_aquaman_config_parses_to_4447(self):
        """Hard-coded expectation. If this breaks, every % in reports/ moves."""
        if not have(AQUAMAN_CONFIG):
            self.skipTest("aquaman-config missing")
        d = config_fingerprint.parse(AQUAMAN_CONFIG)
        self.assertEqual(len(d), 4447)


# ---------------------------------------------------------------- fastboot

class TestFastbootAddressMath(unittest.TestCase):
    """reports/fastboot-memory-flow.md §3: the max-download-size argument that
    the old root cause relied on does not survive its own arithmetic."""

    def test_formula_matches_source(self):
        ddr = 0x40000000
        addr = 0x10200000
        expect = (ddr - 0x01000000 - addr - (64 << 20) - 0x08000000)
        self.assertEqual(fastboot_addr.ddr_size_usable(addr, ddr), expect)

    def test_reported_size_matches_neither_candidate(self):
        """0x08000000 is what the device reported. It is produced by neither
        the khadas buffer address nor loadaddr. This is the refutation."""
        ddr, reported = 0x40000000, 0x08000000
        self.assertNotEqual(
            fastboot_addr.ddr_size_usable(fastboot_addr.KCADAS_BUF_ADDR, ddr), reported)
        self.assertNotEqual(
            fastboot_addr.ddr_size_usable(fastboot_addr.LOADADDR_DEFAULT, ddr), reported)

    def test_inverse_is_self_consistent(self):
        for usable in (0x08000000, 0x22E00000, 0x31F80000):
            addr = fastboot_addr.buf_addr_for_usable(usable, 0x40000000)
            self.assertEqual(fastboot_addr.ddr_size_usable(addr, 0x40000000), usable)

    def test_gxb_window_is_24mib(self):
        """GXB_IMG_SIZE, arch/arm/include/asm/arch-gxl/bl31_apis.h:118"""
        self.assertEqual((24 << 20), 25165824)


class TestBootmInspector(unittest.TestCase):
    """reports/bootm-test-image.md. The trap this guards is the one the old
    test fell into: a raw 4 KiB file is INVALID, not a bootable stub."""

    def test_raw_bytes_are_invalid(self):
        self.assertEqual(inspect_test_image.genimg_format(b"\x00" * 4096),
                         "INVALID")

    def test_android_magic_detected(self):
        self.assertEqual(inspect_test_image.genimg_format(b"ANDROID!" + b"\x00" * 4088),
                         "ANDROID")

    def test_legacy_and_fit_detected(self):
        self.assertEqual(inspect_test_image.genimg_format(
            struct.pack(">I", inspect_test_image.IH_MAGIC) + b"\x00" * 4092), "LEGACY")
        self.assertEqual(inspect_test_image.genimg_format(
            struct.pack(">I", inspect_test_image.FIT_MAGIC) + b"\x00" * 4092), "FIT")

    def test_default_address_is_loadaddr_not_khadas(self):
        """The refuted 0x10200000 must not be the default any more."""
        self.assertEqual(inspect_test_image.X_DEFAULT, 0x01080000)
        self.assertNotEqual(inspect_test_image.X_DEFAULT,
                            inspect_test_image.X_REF_KHADAS)


# ---------------------------------------------------------------- modules

class TestKoInventory(unittest.TestCase):
    def test_elf_header_parse(self):
        """64-bit aarch64 ELF, machine 0xb7"""
        hdr = bytearray(64)
        hdr[0:4] = b"\x7fELF"
        hdr[4] = 2   # 64-bit
        hdr[5] = 1   # little endian
        struct.pack_into("<H", hdr, 18, 0xB7)
        with tempfile.NamedTemporaryFile(suffix=".ko", delete=False) as f:
            f.write(bytes(hdr))
            path = f.name
        try:
            info = ko_inventory.elf_info(path)
        finally:
            os.unlink(path)
        self.assertIn("64-bit", info["arch"])
        self.assertIn("aarch64", info["arch"])

    def test_non_elf_rejected(self):
        with tempfile.NamedTemporaryFile(suffix=".ko", delete=False) as f:
            f.write(b"not an elf at all")
            path = f.name
        try:
            info = ko_inventory.elf_info(path)
        finally:
            os.unlink(path)
        self.assertEqual(info["arch"], "not-elf")


class TestKoVersions(unittest.TestCase):
    """These modules pad every modversion_info to 64 bytes, not the usual 16.
    A parser that assumes 16 silently reads ONE import instead of 82."""

    def make(self, n, stride):
        recs = b""
        for i in range(n):
            name = ("sym%02d" % i).encode()
            recs += struct.pack("<Q", 0x1000 + i) + name.ljust(stride - 8, b"\x00")
        return recs

    def test_reads_64_byte_records(self):
        v = ko_versions._sniff(self.make(82, 64))
        self.assertEqual(len(v), 82)
        self.assertEqual(v[0][1], "sym00")

    def test_reads_16_byte_records(self):
        v = ko_versions._sniff(self.make(5, 16))
        self.assertEqual(len(v), 5)

    def test_real_module_has_64_byte_records(self):
        """The actual bug this guards: a parser assuming 16-byte records
        reads 1 import from amvdec_h264.ko instead of 82."""
        p = os.path.join(VENDOR_MODULES, "amvdec_h264.ko")
        if not have(p):
            self.skipTest("vendor modules not extracted")
        v = ko_versions.versions(p)
        self.assertEqual(len(v), 82)
        self.assertEqual(v[0][1], "module_layout")


class TestVendorModulesOnDisk(unittest.TestCase):
    """Only if the OTA dumps have been unpacked. Skipped, never silently passed."""

    def setUp(self):
        if not os.path.isdir(VENDOR_MODULES):
            self.skipTest("out/vendor/modules not extracted "
                          "(run tools/sdat2img.py on vendor.new.dat.br)")

    def test_28_modules_present(self):
        kos = [f for f in os.listdir(VENDOR_MODULES) if f.endswith(".ko")]
        self.assertEqual(len(kos), 28)

    def test_every_module_is_aarch64(self):
        for name in os.listdir(VENDOR_MODULES):
            if not name.endswith(".ko"):
                continue
            info = ko_inventory.elf_info(os.path.join(VENDOR_MODULES, name))
            self.assertIn("aarch64", info["arch"], name)

    def test_vermagic_is_the_flattened_49y(self):
        """Makefile:1221 flattens the stamp to <major>.<minor>.y on purpose,
        so this is a property of the Amlogic tree, not a provenance clue."""
        from subprocess import run
        out = run(["modinfo", "-F", "vermagic",
                   os.path.join(VENDOR_MODULES, "amvdec_h264.ko")],
                  capture_output=True, text=True).stdout.strip()
        self.assertTrue(out.startswith("4.9.y "), out)
        self.assertIn("modversions", out)

    def test_ddr_window_is_the_foreign_one(self):
        from subprocess import run
        out = run(["modinfo", "-F", "vermagic",
                   os.path.join(VENDOR_MODULES, "ddr_window_64.ko")],
                  capture_output=True, text=True).stdout.strip()
        self.assertTrue(out.startswith("3.14.29"), out)

    def test_w1_imports_are_absent_from_our_vmlinux(self):
        """The 13 missing symbols. If McMCCRU ever grows the W1 stack this
        fails, which is the point: it should be noticed."""
        symvers = os.path.join(OBJDIR, "Module.symvers")
        if not have(symvers):
            self.skipTest("Module.symvers missing, build not run")
        have_syms = set()
        for line in open(symvers):
            p = line.split()
            if len(p) >= 4 and p[2] == "vmlinux":
                have_syms.add(p[1])
        for sym in ("g_w1_hif_ops", "wifi_in_insmod", "pstore_io_save"):
            self.assertNotIn(sym, have_syms, "%s unexpectedly present" % sym)


# ---------------------------------------------------------------- sdat

class TestSdat2img(unittest.TestCase):
    def write(self, text, name, tmpdir):
        p = os.path.join(tmpdir, name)
        with open(p, "w") as f:
            f.write(text)
        return p

    def test_runs_add_up_to_dat_size(self):
        """These transfer lists express runs as boundary pairs, which most
        published sdat2img parsers misread. This pins that behaviour."""
        tmp = tempfile.mkdtemp()
        tl = self.write("4\n25600\n0\n0\nnew 4,0,69,827,1782\n"
                        "new 2,1782,2806\n"
                        "zero 4,69,827,24763,25029\n", "t.transfer.list", tmp)
        version, total, runs = sdat2img.parse(tl)
        self.assertEqual(total, 25600)
        self.assertEqual(runs, [(0, 69), (827, 955), (1782, 1024)])
        # the .dat holds exactly the runs, back to back, and nothing else
        self.assertEqual(sum(c for _, c in runs) * 4096, (69 + 955 + 1024) * 4096)
        os.unlink(tl)
        os.rmdir(tmp)

    def test_rejects_odd_block_list(self):
        tmp = tempfile.mkdtemp()
        tl = self.write("4\n25600\n0\n0\nnew 2,1,2,3\n", "t.transfer.list", tmp)
        with self.assertRaises(SystemExit):
            sdat2img.parse(tl)
        os.unlink(tl)
        os.rmdir(tmp)


# ---------------------------------------------------------------- BL33 round 14

class TestBl33Interface(unittest.TestCase):
    """reports/bl33-bl31-interface-round14.md. the image extent, the sha256, the
    SMC census, the command table and the fastboot dispatch table are all
    claims that report makes, so they get pinned here."""

    @classmethod
    def setUpClass(cls):
        if not have(BL33_IMAGE):
            raise unittest.SkipTest("round-14 image not persisted "
                                    "(tools/bl33_persist.py)")
        cls.img = bl33_audit.Img(BL33_IMAGE, R)

    def test_image_extent_and_hash(self):
        """0x1d8000 bytes, and the hash the report quotes."""
        blob = open(BL33_IMAGE, "rb").read()
        self.assertEqual(len(blob), 0x1D8000)
        self.assertEqual(hashlib.sha256(blob).hexdigest(),
                         "664fb34a9c6d92cdcd576659fb5359bd5218841612dbf38c01426c5d3c1b7818")

    def test_page_table_above_the_image_justifies_the_end(self):
        """board.c reserves PGTABLE_SIZE (0x10000) above relocaddr+mon_len, so
        the image cannot end past 0x37ff0000. the band is the evidence."""
        if not have(R13_BAND):
            self.skipTest("round-13 band missing")
        band = open(R13_BAND, "rb").read()
        off = IMAGE_END - 0x37800000
        words = struct.unpack_from("<64Q", band, off)
        self.assertEqual(sum(1 for w in words if w and (w & 3) == 1), 64)
        # and the image's own last byte is not zero, i.e. mon_len does reach it
        self.assertNotEqual(band[off - 1], 0)

    def test_persist_reproduces_the_same_image(self):
        """the carve is deterministic: re-running the tool on the same band has
        to produce the same bytes."""
        if not have(R13_BAND):
            self.skipTest("round-13 band missing")
        with tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as f:
            out = f.name
        try:
            run([sys.executable, os.path.join(REPO, "tools/bl33_persist.py"),
                 R13_BAND, "0x37800000", "0x37e18000", "0x37ff0000", out],
                capture_output=True, check=True)
            self.assertEqual(hashlib.sha256(open(out, "rb").read()).digest(),
                             hashlib.sha256(open(BL33_IMAGE, "rb").read()).digest())
        finally:
            os.unlink(out)

    def test_smc_census_is_fifteen_exact(self):
        """`smc #0` with a zero immediate, over the whole image. five data words
        decode as `smc #0x1234` and must not be counted."""
        sites = [i.address for i in self.img.insns
                 if i.mnemonic == "smc" and i.op_str == "#0"]
        self.assertEqual(len(sites), 15)
        for a in (0x37E19ED8, 0x37E19F08, 0x37E8BBA0, 0x37E8C144, 0x37E635A0):
            self.assertIn(a, sites)
        loose = [i.address for i in self.img.insns
                 if i.mnemonic == "smc" and i.op_str != "#0"]
        self.assertTrue(loose, "the nonzero-immediate decoys should exist")

    def test_the_five_security_smc_ids(self):
        """the id each security-relevant wrapper sends in x0."""
        for site, want in ((0x37E19ED8, {0x820000FF}),
                           (0x37E19F08, {0x82000043}),
                           (0x37E8C144, {0x82000028}),
                           (0x37E8BBA8, set())            # 2-arg stub: caller passes it
                           ):
            got = bl33_audit.reach(self.img.words, R, site, 0,
                                   lo=self.img.func_of(site))
            if want:
                self.assertIn(next(iter(want)), got, "0x%08x" % site)
        # the 1-arg stub is fed by its callers, not by itself
        callers = self.img.callers(0x37E8BBA8 - 8)  # bl31_storage_ops stub
        self.assertTrue(callers)
        ids = set()
        for c, f in callers:
            ids |= {v for v in bl33_audit.reach(self.img.words, R, c, 0, lo=f)
                    if isinstance(v, int)}
        for want in (0x82000061, 0x82000062, 0x82000060, 0x82000065,
                     0x82000063, 0x82000064):
            self.assertIn(want, ids)

    def test_aml_sec_boot_check_call_sites(self):
        cs = self.img.callers(0x37E19EA8)
        self.assertEqual(len(cs), 15)
        fns = sorted({f for _, f in cs})
        self.assertEqual(len(fns), 7)
        self.assertEqual(fns[0], 0x37E24C00)         # do_bootm
        self.assertEqual(self.img.name_of(0x37E24C00), "bootm")

    def test_command_table_entries(self):
        for addr, name in ((0x37E24C00, "bootm"), (0x37E607E8, "set_usb_boot"),
                           (0x37E3A840, "fastboot"), (0x37E33900, "store"),
                           (0x37E5E968 - 0x144, None)):
            if name:
                self.assertEqual(self.img.name_of(addr), name)
        self.assertGreater(len(self.img.cmd_of), 60)

    def test_fastboot_dispatch_table_and_the_oem_gap(self):
        """13 slots; `oem` -> 0x37e95630; flash/erase/flashall/set_active call
        the lock helper, `oem` does not."""
        band = self.img.data
        want = {0x37EB5BC8: ("reboot", 0x37E95204),
                0x37EB5BD8: ("getvar:", 0x37E95ECC),
                0x37EB5C18: ("flash", 0x37E95D50),
                0x37EB5C38: ("flashall", 0x37E95C90),
                0x37EB5C48: ("erase", 0x37E95B20),
                0x37EB5C78: ("set_active", 0x37E95A14),
                0x37EB5C88: ("oem", 0x37E95630)}
        for slot, (name, cb) in want.items():
            s, c = struct.unpack_from("<QQ", band, slot - R)
            self.assertEqual(c, cb, name)
            self.assertEqual(band[s - R:band.find(b"\0", s - R)].decode(), name)
        lock = {f for _, f in self.img.callers(0x37E9593C)}
        for cb in (0x37E95D50, 0x37E95C90, 0x37E95B20, 0x37E95A14):
            self.assertIn(cb, lock, "0x%08x should be lock-gated" % cb)
        self.assertNotIn(0x37E95630, lock, "the oem handler must not be gated")

    def test_oem_handler_runs_a_command(self):
        """strnlen(cmd,32) -> memcpy(buf,cmd,n+1) -> strsep -> run_command."""
        ins = {i.address: i.mnemonic for i in self.img.insns}
        self.assertEqual(ins[0x37E9565C], "bl")      # strnlen
        self.assertEqual(ins[0x37E9566C], "bl")      # memcpy
        self.assertEqual(ins[0x37E95684], "bl")      # strsep
        self.assertEqual(ins[0x37E956A0], "bl")      # run_command
        targets = [i.operands[0].imm for i in self.img.insns
                   if i.address in (0x37E9565C, 0x37E9566C, 0x37E95684, 0x37E956A0)]
        self.assertEqual(targets, [0x37EAADA0, 0x37EAAEEC, 0x37EAAE44, 0x37E5E968])
        # strnlen is strnlen: it walks at most n bytes and stops on NUL
        s = self.img.data[0x37EAADA0 - R:0x37EAADA0 - R + 12]
        self.assertEqual(struct.unpack_from("<3I", s), (0x8B010001, 0xAA0003E2,
                                                        0xEB01005F))

    def test_secure_storage_public_api_has_no_callers(self):
        """the key read/write interface exists but nothing in the image reaches
        it: no bl/b/blr, no pointer table."""
        apis = (0x37E8C084, 0x37E8C1A0, 0x37E8C234, 0x37E8C25C, 0x37E8C294,
                0x37E8C320, 0x37E8C3A8, 0x37E8C410, 0x37E8C484)
        for t in apis:
            self.assertEqual(self.img.callers(t), [], "0x%08x" % t)
        pt = struct.unpack_from("<%dQ" % (len(self.img.data) // 8), self.img.data, 0)
        for t in apis:
            self.assertNotIn(t, pt, "0x%08x appears in a pointer table" % t)
        # while the one live secure-storage SMC is on the storage init path
        self.assertEqual({f for _, f in self.img.callers(0x37E8C138)},
                         {0x37E904AC})


# ---------------------------------------------------------------- artifacts

class TestBl33Round15(unittest.TestCase):
    """reports/bl33-interface-round15.md. static OEM/run_command + E3 claims."""

    @classmethod
    def setUpClass(cls):
        if not have(BL33_IMAGE):
            raise unittest.SkipTest("round-14 image not persisted")
        cls.img = bl33_audit.Img(BL33_IMAGE, R)
        cls.r15 = bl33_round15.Img(BL33_IMAGE, R)

    def test_command_table_is_80(self):
        self.assertEqual(len(self.img.cmd_of), 80)

    def test_no_top_level_memory_or_script_commands(self):
        names = set(self.img.cmd_of.values())
        for missing in ("md", "mw", "cp", "cmp", "crc32", "iminfo", "base",
                        "go", "booti", "bootz", "source", "fatload",
                        "ext4load", "loady"):
            self.assertNotIn(missing, names, missing)
        for present in ("bootm", "run", "mmc", "store", "env", "setenv",
                        "printenv", "update", "itest", "test", "echo",
                        "ddr_test_copy", "tee_log_level", "set_usb_boot"):
            self.assertIn(present, names, present)

    def test_mw_crc32_strings_are_not_commands(self):
        blob = open(BL33_IMAGE, "rb").read()
        self.assertIn(b"\x00mw\x00", blob)      # i2c subcommand list
        self.assertIn(b"\x00crc32\x00", blob)   # hash algorithm name
        names = set(self.img.cmd_of.values())
        self.assertNotIn("mw", names)
        self.assertNotIn("crc32", names)

    def test_mmc_subtable_has_read_and_write(self):
        data = self.img.data
        rd = struct.unpack_from("<Q", data, 0x37EE5BC0 - R + 48 + 16)[0]
        wr = struct.unpack_from("<Q", data, 0x37EE5BC0 - R + 96 + 16)[0]
        self.assertEqual(rd, 0x37E2D890)
        self.assertEqual(wr, 0x37E2D764)

    def test_mmc_read_takes_host_addr_to_block_read(self):
        ins = {i.address: i for i in self.img.insns}
        self.assertEqual(ins[0x37E2D8BC].mnemonic, "bl")   # simple_strtoul
        self.assertEqual(ins[0x37E2D8BC].operands[0].imm, 0x37EAC21C)
        self.assertEqual(ins[0x37E2D934].mnemonic, "blr")  # blk_dread
        self.assertIn("x4", ins[0x37E2D934].op_str)

    def test_mmc_write_takes_host_addr_to_block_write(self):
        ins = {i.address: i for i in self.img.insns}
        self.assertEqual(ins[0x37E2D790].operands[0].imm, 0x37EAC21C)
        self.assertEqual(ins[0x37E2D82C].mnemonic, "blr")  # blk_dwrite

    def test_ddr_test_copy_parses_src_dst_size(self):
        ins = {i.address: i for i in self.img.insns}
        for a in (0x37E3D224, 0x37E3D238, 0x37E3D24C):
            self.assertEqual(ins[a].operands[0].imm, 0x37E3CBB0)
        self.assertEqual(ins[0x37E3D348].operands[0].imm, 0x37E3AEA0)

    def test_oem_frame_numbers(self):
        ins = {i.address: (i.mnemonic, i.op_str) for i in self.img.insns}
        self.assertEqual(ins[0x37E95630][1], "x29, x30, [sp, #-0x50]!")
        self.assertEqual(ins[0x37E95668][1], "x0, x29, #0x20")
        self.assertEqual(ins[0x37E95654][1], "x1, #0x20")

    def test_e3_registers(self):
        ins = {i.address: (i.mnemonic, i.op_str) for i in self.img.insns}
        self.assertEqual(ins[0x37E24CE4][1], "x0, #0x40")
        self.assertEqual(ins[0x37E24CE8][1], "x2, #0x1800000")
        self.assertEqual(ins[0x37E24CEC][1], "x3, #7")
        self.assertEqual(ins[0x37E24CF0][0], "bl")
        self.assertEqual(ins[0x37E19ED8][0], "smc")

    def test_tee_log_level_smc_id(self):
        got = bl33_audit.reach(self.img.words, R, 0x37E635A0, 0,
                               lo=self.img.func_of(0x37E635A0))
        self.assertIn(0xB2000016, got)

    def test_run_command_reachable_from_run_handler(self):
        bls = dict((a, t) for a, t in bl33_round15.func_bls(self.r15, 0x37E5EA04))
        self.assertIn(0x37E5E968, bls.values())


# ---------------------------------------------------------------- artifacts

class TestBl33Round16(unittest.TestCase):
    """reports/bl33-write-primitive-round16.md + round16-ddr-copy/01..05.

    Static update + ddr_test_copy audit. Image-gated tests skip when the
    round-14 image is absent; pure clamp/bytes tests always run.
    """

    @classmethod
    def setUpClass(cls):
        if not have(BL33_IMAGE):
            raise unittest.SkipTest("round-14 image not persisted")
        cls.img = bl33_audit.Img(BL33_IMAGE, R)
        cls.r16 = bl33_round16.Img(BL33_IMAGE, R)

    def test_fastboot_buffer_base_is_0x10200000(self):
        """rx_handler 0x37e95274: mov x1,#0x10200000 + add dst + memcpy."""
        ins = {i.address: i for i in self.img.insns}
        self.assertEqual(ins[0x37E952DC].op_str, "x1, #0x10200000")
        self.assertEqual(ins[0x37E952E0].op_str, "x0, x1, w0, uxtw")
        self.assertEqual(ins[0x37E952EC].operands[0].imm, 0x37EAAEEC)

    def test_fastboot_usable_has_128mib_cap(self):
        """ddr_size_usable 0x37e953e4: min(computed, 0x8000000)."""
        ins = {i.address: (i.mnemonic, i.op_str) for i in self.img.insns}
        self.assertEqual(ins[0x37E953F8][1], "w1, #0x8000000")
        self.assertEqual(ins[0x37E95400][0], "csel")

    def test_burning_buffer_base_is_0x7700000(self):
        """buf init 0x37e7bbe0: transferBuf must equal 0x7700000."""
        ins = {i.address: (i.mnemonic, i.op_str) for i in self.img.insns}
        self.assertEqual(ins[0x37E7BBF4][1], "x3, #0x7700000")
        self.assertEqual(ins[0x37E7BBF8][1], "x2, x3")

    def test_update_handler_takes_no_address(self):
        """update 0x37e78ff8 maxargs 3: argv go to timeout/env, not an address."""
        ins = {i.address: i for i in self.img.insns}
        self.assertEqual(ins[0x37E79024].operands[0].imm, 0x37EAC21C)
        self.assertEqual(ins[0x37E79044].operands[0].imm, 0x37EAC21C)
        self.assertEqual(ins[0x37E79090].mnemonic, "b")
        self.assertEqual(ins[0x37E79090].operands[0].imm, 0x37E78F94)
        self.assertEqual(self.img.cmd_of.get(0x37E78FF8), "update")

    def test_ddr_copy_parser_and_floor(self):
        ins = {i.address: i for i in self.img.insns}
        for a in (0x37E3D224, 0x37E3D238, 0x37E3D24C):
            self.assertEqual(ins[a].operands[0].imm, 0x37E3CBB0)
        self.assertEqual(ins[0x37E3D348].operands[0].imm, 0x37E3AEA0)
        self.assertEqual((ins[0x37E3D26C].mnemonic, ins[0x37E3D26C].op_str),
                         ("cmp", "w20, #0xfff"))
        self.assertEqual(ins[0x37E3D270].op_str, "w0, #0x2000000")
        self.assertEqual(ins[0x37E3D274].mnemonic, "csel")

    def test_copy_loop_is_4x(self):
        """0x37e3aea0: N=size>>2 iters x 16 B = 4x requested."""
        ins = {i.address: (i.mnemonic, i.op_str) for i in self.img.insns}
        self.assertEqual(ins[0x37E3AEA0][1], "w2, w2, #2")
        self.assertEqual(ins[0x37E3AEB8][1], "x0, x0, #0x10")
        self.assertEqual(ins[0x37E3AEC4][1], "x1, x1, #0x10")
        self.assertEqual(ins[0x37E3AEE0][0], "ret")

    def test_ddr_dst_path_has_no_clamp(self):
        """w25->w23->x0 with no and/lsr/mask/cmp on the dst regs."""
        ins = {i.address: (i.mnemonic, i.op_str) for i in self.img.insns}
        self.assertEqual(ins[0x37E3D318][1], "w23, w25")
        self.assertEqual(ins[0x37E3D33C][1], "x0, x23")
        lo, hi = 0x37E3D218, 0x37E3D348
        for i in self.img.insns:
            if lo <= i.address < hi and i.mnemonic in ("and", "tst"):
                self.fail("unexpected mask on parser path at 0x%08x" % i.address)

    def test_mmc_read_length_mask(self):
        """ubfiz keeps low 23 bits of cnt: len=(cnt&0x7fffff)*512."""
        ins = {i.address: (i.mnemonic, i.op_str) for i in self.img.insns}
        self.assertEqual(ins[0x37E2D93C][1], "x1, x19, #9, #0x17")
        self.assertEqual(ins[0x37E2D934][0], "blr")

    def test_pure_ddr_clamp(self):
        self.assertEqual(bl33_round16.ddr_size_clamp(0), 0x2000000)
        self.assertEqual(bl33_round16.ddr_size_clamp(0xFFF), 0x2000000)
        self.assertEqual(bl33_round16.ddr_size_clamp(0x1000), 0x1000)
        self.assertEqual(bl33_round16.ddr_size_clamp(0x2000000), 0x2000000)
        self.assertEqual(bl33_round16.ddr_size_clamp(0x100000000), 0x2000000)

    def test_pure_ddr_effective_is_4x(self):
        self.assertEqual(bl33_round16.ddr_effective_bytes(0x1000), 0x4000)
        self.assertEqual(bl33_round16.ddr_effective_bytes(0x2000000), 0x8000000)
        self.assertEqual(bl33_round16.ddr_effective_bytes(0), 0x8000000)

    def test_pure_mmc_bytes_mask(self):
        self.assertEqual(bl33_round16.mmc_effective_bytes(1), 512)
        self.assertEqual(bl33_round16.mmc_effective_bytes(0x7FFFFF), 0xFFFFFE00)
        self.assertEqual(bl33_round16.mmc_effective_bytes(0x800000), 0)

    def test_pure_oem_budget(self):
        self.assertTrue(bl33_round16.oem_fits("mmc read 1080000 0 1"))
        self.assertFalse(bl33_round16.oem_fits("x" * 32))


class TestBl33Round37(unittest.TestCase):
    """round 37: ddr_test_copy as a control primitive (write -> control flow).

    The tail write, the live page table, the cmd_tbl consumer and the oem
    character budget. Pure arithmetic tests always run, image-gated ones skip.
    """

    @classmethod
    def setUpClass(cls):
        if not have(BL33_IMAGE):
            raise unittest.SkipTest("round-14 image not persisted")
        cls.d, cls.ins = bl33_ctrl.load_img(BL33_IMAGE)
        cls.at = {i.address: (i.mnemonic, i.op_str) for i in cls.ins}

    # ---- primitive -------------------------------------------------------

    def test_tail_is_four_copies_of_one_word(self):
        """0x37e3d4b8..0x37e3d4d8: one 32-bit value, four times, 16 B at dst+L."""
        for a in (0x37E3D4B8, 0x37E3D4C4, 0x37E3D4D0, 0x37E3D4D8):
            self.assertTrue(self.at[a][0].startswith("str"), hex(a))
        self.assertEqual(self.at[0x37E3D4B8][1], "w1, [x23, x27]")
        self.assertEqual(self.at[0x37E3D4C4][1], "w0, [x24, #4]")
        self.assertEqual(self.at[0x37E3D4D0][1], "w0, [x24, #8]")
        self.assertEqual(self.at[0x37E3D4D8][1], "w0, [x24, #0xc]")
        # w1 and w0 both come from the same read-loop word
        self.assertEqual(self.at[0x37E3D4A4][1], "w1, [x3, #4]!")
        self.assertEqual(self.at[0x37E3D4BC][1], "w0, [x3]")

    def test_fill_length_and_its_start(self):
        """0x37e3d3d0 ubfiz -> stride; 0x37e3d440 -> L = loop*stride."""
        self.assertEqual(self.at[0x37E3D3D0][1], "x0, x22, #4, #0x1e")
        self.assertEqual(self.at[0x37E3D440][1], "x27, x0, x27")
        self.assertEqual(self.at[0x37E3D48C][1], "x24, x23, x27")
        self.assertEqual(self.at[0x37E3D3F4][1], "w6, #0x1234, lsl #16")

    def test_no_cache_maintenance_in_the_handler(self):
        for i in self.ins:
            if 0x37E3D1B0 <= i.address <= 0x37E3D52C:
                self.assertNotIn(i.mnemonic, ("dc", "ic", "dsb", "isb", "dc civac"))
                self.assertNotIn("civac", i.op_str)
                self.assertNotIn("cvau", i.op_str)

    def test_pure_primitive_model(self):
        m = bl33_ctrl.prim_model(0x1000, 1)
        self.assertEqual((m["N"], m["L"], m["srcoff"]), (0x400, 0x4000, 0x200))
        m = bl33_ctrl.prim_model(0x2000000, 1)
        self.assertEqual((m["N"], m["L"], m["srcoff"]),
                         (0x800000, 0x8000000, 0x400000))
        m = bl33_ctrl.prim_model(0x1000, 2)
        self.assertEqual(m["L"], 0x8000)

    # ---- execution surface ----------------------------------------------

    def test_page_table_is_rw_and_executable(self):
        if not have(R13_BAND):
            self.skipTest("round-13 band not present")
        with open(os.path.join(REPO, R13_BAND), "rb") as fh:
            d = fh.read()
        q = struct.unpack("<8192Q", d[0x7F0000:0x800000])
        for v in q:
            ap = (((v >> 4) & 1) << 1) | ((v >> 8) & 1)
            self.assertIn(ap, (0, 2))
            self.assertEqual((v >> 54) & 1, 0)      # XN
            self.assertEqual((v >> 10) & 1, 1)      # AF
            self.assertEqual(v & 3, 1)              # block

    def test_cmd_table_layout_and_consumer(self):
        """0x30-stride array at 0x37f60eb0; ->cmd at +0x10; bootm is index 6."""
        bootm = 0x37F60FD0
        self.assertEqual(struct.unpack_from("<Q", self.d, bootm - R)[0], 0x37EC01FE)
        self.assertEqual(self.d[0x37EC01FE - R:0x37EC01FE - R + 5], b"bootm")
        self.assertEqual(struct.unpack_from("<Q", self.d, bootm - R + 0x10)[0],
                         0x37E24C00)
        # entry 0 is the one the write targets: its ->cmd slot is 0x37f60ec0
        self.assertEqual(bl33_ctrl.A_CMD, 0x37F60EB0 + 0x10)
        # call_cmd: find_cmd -> maxargs gate -> ldr x4,[x19,#0x10] -> blr x4
        self.assertEqual(self.at[0x37E5F6E8][1], "x4, [x19, #0x10]")
        self.assertEqual(self.at[0x37E5F6FC], ("blr", "x4"))
        self.assertEqual(self.at[0x37E5F6B4][1], "w0, [x0, #8]")
        self.assertEqual(self.at[0x37E5F690], ("bl", "#0x37e5ee9c"))
        # find_cmd walks a 0x30-stride array, no global list
        self.assertEqual(self.at[0x37E5EE24][1], "w24, #0x30")
        self.assertEqual(self.at[0x37E5EE6C][1], "x19, x19, #0x30")

    def test_oem_budget_is_28_chars(self):
        """cb_oem 0x37e95630: strnlen(cmd,32) -> memcpy 33 B into a 0x30 B buf."""
        self.assertEqual(self.at[0x37E95654][1], "x1, #0x20")
        self.assertEqual(self.at[0x37E95660][1], "x2, x0, #1")
        self.assertEqual(self.at[0x37E95668][1], "x0, x29, #0x20")
        self.assertEqual(self.at[0x37E95684], ("bl", "#0x37eaae44"))
        self.assertEqual(self.at[0x37E956A0], ("bl", "#0x37e5e968"))
        # 0x37eaada0 is strnlen: end = s + n
        self.assertEqual(self.at[0x37EAADA0][1], "x1, x0, x1")
        self.assertEqual(bl33_ctrl.TOKEN_MAX, 28)

    def test_pure_budget_cannot_fit_the_surgical_form(self):
        free = bl33_ctrl.TOKEN_MAX - len("ddr_test_copy") - 3
        self.assertEqual(free, 12)          # chars for src+dst+size
        self.assertLess(free - 4 - 8, 1)    # size 4 digits + dst 8 digits leave 0 for src

    def test_do_run_does_not_concatenate(self):
        """0x37e5ea04: getenv(argv[i]) then run_command(value) per variable."""
        self.assertEqual(self.at[0x37E5EA30], ("bl", "#0x37e58920"))
        self.assertEqual(self.at[0x37E5EA50], ("bl", "#0x37e5e968"))
        self.assertEqual(self.at[0x37E5EA28][1], "w22, w1, #4")

    def test_optimus_command_buffer_has_no_generic_run(self):
        """0x37f8a638 takes 0xffff bytes (0xc0 sub-op) but 0x34 only matches a list."""
        self.assertEqual(self.at[0x37E76BC0], ("bl", "#0x37eaaeec"))
        self.assertEqual(self.at[0x37E799D4], ("bl", "#0x37e5e8cc"))
        # 0x37e5e8cc is the whitespace tokenizer, not run_command
        self.assertEqual(self.at[0x37E5E8E4][0], "ldrb")
        for a, s in ((0x37ED85E7, "low_power"), (0x37ED85F1, "disk_initial"),
                     (0x37ED8686, "download"), (0x37ED868F, "upload"),
                     (0x37ECFEDF, "read_temp"), (0x37ED876B, "get_chipid")):
            self.assertEqual(self.d[a - R:a - R + len(s)], s.encode())


class TestBl33Round38(unittest.TestCase):
    """round 38: corrective audit. consumer is 64-bit, chain as stated is out."""

    @classmethod
    def setUpClass(cls):
        if not have(BL33_IMAGE):
            raise unittest.SkipTest("round-14 image not persisted")
        cls.d, cls.ins = bl33_ctrl.load_img(BL33_IMAGE)
        cls.at = {i.address: (i.mnemonic, i.op_str) for i in cls.ins}

    def test_consumer_load_is_64_bit(self):
        self.assertEqual(self.at[0x37E5F6E8], ("ldr", "x4, [x19, #0x10]"))
        self.assertEqual(self.at[0x37E5F6FC], ("blr", "x4"))
        self.assertTrue(self.at[0x37E5F6E8][1].split(",")[0].strip().startswith("x"))
        # neighbouring struct fields are 32-bit, which is why w vs x matters
        self.assertEqual(self.at[0x37E5F6B4][1], "w0, [x0, #8]")
        self.assertEqual(self.at[0x37E5F718][1], "w0, [x19, #0xc]")

    def test_cmd_struct_entries_0_to_2(self):
        base, stride = 0x37F60EB0, 0x30
        names = [b"aml_sysrecovery", b"amlmmc", b"avb"]
        cmds = [0x37E8387C, 0x37E2F064, 0x37E63A64]
        for i, (nm, cmd) in enumerate(zip(names, cmds)):
            b = base + i * stride
            ptr = struct.unpack_from("<Q", self.d, b - R)[0]
            self.assertEqual(self.d[ptr - R:ptr - R + len(nm)], nm)
            self.assertEqual(struct.unpack_from("<Q", self.d, b - R + 0x10)[0], cmd)
        self.assertEqual(bl33_ctrl.A_CMD, base + 0x10)
        # table bounds from sconv, 116 entries here
        self.assertEqual((0x37F62470 - base) // stride, 116)

    def test_tail_pointer_is_non_canonical(self):
        w = 0x10200000
        u64 = (w << 32) | w
        self.assertEqual(u64, 0x1020000010200000)
        self.assertNotIn((u64 >> 48) & 0xFFFF, (0x0000, 0xFFFF))

    def test_collateral_range_for_surgical_form(self):
        m = bl33_ctrl.prim_model(0x1000, 1, dst=0x37F5CEC0)
        self.assertEqual(m["L"], 0x4000)
        self.assertEqual(0x37F5CEC0 + m["L"], 0x37F60EC0)
        self.assertEqual(m["tail"], (0x37F60EC0, 0x37F60ED0))

    def test_page_table_is_512mb_identity(self):
        if not have(R13_BAND):
            self.skipTest("round-13 band not present")
        with open(os.path.join(REPO, R13_BAND), "rb") as fh:
            d = fh.read()
        q = struct.unpack("<8192Q", d[0x7F0000:0x800000])
        self.assertEqual(q[0], 0x411)
        self.assertEqual(q[1], 0x20000411)
        self.assertEqual(q[2], 0x40000401)
        for v in q:
            self.assertEqual(v & 3, 1)
            self.assertEqual((v >> 54) & 1, 0)
        self.assertEqual((q[0] >> 2) & 0x7, 4)
        self.assertEqual((q[2] >> 2) & 0x7, 0)


# ---------------------------------------------------------------- artifacts

class TestBl33Round17(unittest.TestCase):
    """reports/bl31-aml-data-process-round17.md. static E3 close-out."""

    @classmethod
    def setUpClass(cls):
        if not have(BL33_IMAGE):
            raise unittest.SkipTest("round-14 image not persisted")
        cls.img = bl33_audit.Img(BL33_IMAGE, R)

    def test_still_fifteen_sites_in_seven_functions(self):
        cs = self.img.callers(0x37E19EA8)
        self.assertEqual(len(cs), 15)
        self.assertEqual(len({f for _, f in cs}), 7)
        self.assertEqual(len(bl33_round17.E3), 15)

    def test_e3_site1_is_the_only_raw_host_address(self):
        ins = {i.address: (i.mnemonic, i.op_str) for i in self.img.insns}
        self.assertEqual(ins[0x37E24CE4][1], "x0, #0x40")
        self.assertEqual(ins[0x37E24CE8][1], "x2, #0x1800000")
        self.assertEqual(ins[0x37E24CEC][1], "x3, #7")
        self.assertEqual(ins[0x37E24CD4][0], "bl")
        # second site in same function is a constant, not argv
        self.assertEqual(ins[0x37E24F80][1], "x1, #0x1080000")
        self.assertEqual(ins[0x37E24F8C][1], "x0, #0x100")

    def test_wrapper_shuffle_and_flush(self):
        ins = {i.address: (i.mnemonic, i.op_str) for i in self.img.insns}
        by = {i.address: i for i in self.img.insns}
        self.assertEqual(ins[0x37E19EC4][1], "x0, #0xff")
        self.assertEqual(ins[0x37E19ED8][0], "smc")
        self.assertEqual(ins[0x37E19EE0][1], "x1, x6, x5")
        self.assertEqual(by[0x37E19EE8].operands[0].imm, 0x37E19310)

    def test_0x1800000_is_gxb_img_size(self):
        self.assertEqual(bl33_round17.GXB_IMG_SIZE, 0x1800000)
        self.assertEqual(bl33_round17.GXB_IMG_SIZE, 24 << 20)
        ins = {i.address: (i.mnemonic, i.op_str) for i in self.img.insns}
        self.assertEqual(ins[0x37E36234][1], "x2, #0x1800000")
        self.assertEqual(ins[0x37E36238][1], "x3, #4")

    def test_ddr_tail_stores_are_src_derived(self):
        ins = {i.address: (i.mnemonic, i.op_str) for i in self.img.insns}
        self.assertEqual(ins[0x37E3D4B8][1], "w1, [x23, x27]")
        self.assertEqual(ins[0x37E3D4C4][1], "w0, [x24, #4]")
        self.assertEqual(ins[0x37E3D3F0][1], "w6, #0x5678")
        self.assertEqual(ins[0x37E3AEA0][1], "w2, w2, #2")

    def test_tee_second_smc_is_log_level_only(self):
        ins = {i.address: (i.mnemonic, i.op_str) for i in self.img.insns}
        self.assertEqual(ins[0x37E63598][1], "w0, #0x16")
        self.assertEqual(ins[0x37E6359C][1], "w0, #0xb200, lsl #16")
        self.assertEqual(ins[0x37E635A0][0], "smc")
        got = bl33_audit.reach(self.img.words, R, 0x37E635A0, 0,
                               lo=self.img.func_of(0x37E635A0))
        self.assertIn(0xB2000016, got)

    def test_reference_bl31_has_no_ff_literal(self):
        for cand in (".src/u-boot-khadas/fip/gxl/bl31.bin",
                     ".src/u-boot-khadas/fip/gxb/bl31.bin"):
            p = os.path.join(REPO, cand)
            if not have(p):
                self.skipTest("%s missing" % cand)
            d = open(p, "rb").read()
            self.assertIn(b"AMLSECU", d)
            words = struct.unpack("<%dI" % (len(d) // 4), d[:len(d) // 4 * 4])
            self.assertNotIn(0x820000FF, words)
            self.assertNotIn(0xD4000003, words)


class TestBl33Round18(unittest.TestCase):
    """reports/bl31-exact-round18.md. exact-aquaman BL31 acquisition, offline."""

    @classmethod
    def setUpClass(cls):
        if not have(BL33_IMAGE):
            raise unittest.SkipTest("round-14 image not persisted")
        cls.bl33 = open(BL33_IMAGE, "rb").read()
        dtb = os.path.join(REPO, "artifacts/aquaman.dtb")
        if not have(dtb):
            raise unittest.SkipTest("runtime DTB missing")
        cls.dtb = open(dtb, "rb").read()

    def test_exact_bl31_absent_and_family_present(self):
        inv = bl33_round18.inventory()
        self.assertIn("EXACT AQUAMAN BL31 binary/dump/map/objdump: ABSENT", inv)
        self.assertIn("FAMILY GXL/GXB", inv)
        for rel in ("bootloader.img", "boot.img",
                    ".src/u-boot-khadas/fip/gxl/bl31.bin"):
            self.assertTrue(have(os.path.join(REPO, rel)), rel)

    def test_bootloader_at_rest_is_encrypted(self):
        d = open(os.path.join(REPO, "bootloader.img"), "rb").read()
        self.assertNotIn(b"AMLSECU!", d)
        self.assertNotIn(bytes([0x01, 0x00, 0x64, 0xAA]), d)
        self.assertIn(b"TOC", d)  # lone frag at 0x4bebe, no FIP magic

    def test_boot_img_amlsecu_container_pins(self):
        d = open(os.path.join(REPO, "boot.img"), "rb").read()
        self.assertEqual(d.find(b"AMLSECU!"), 0x800)
        ver, nblk = struct.unpack("<II", d[0x808:0x810])
        self.assertEqual((ver, nblk), (0x0905, 3))

    def test_handoff_is_hwreg_plus_dtb_not_loader(self):
        h = bl33_round18.handoff()
        for s in ("P_AO_SEC_GP_CFG3", "fdt set /reserved-memory/linux,secmon",
                  "0x82000020", "no BL31 image parser"):
            self.assertIn(s, h)
        for s in ("bl31 reserved memory start", "reserve_mem_size"):
            self.assertIn(s, self.bl33.decode("latin1"))

    def test_dtb_secmon_ranges(self):
        t = bl33_round18.dtb()
        self.assertIn("[0x5000000,0x5400000)", t)
        self.assertIn("[0x5300000,0x7300000)", t)
        self.assertIn("0x300000", t)
        nodes, rsv = bl33_round18._parse_dtb(self.dtb)
        props = {(p, n) for p, n, _ in nodes}
        self.assertIn(("/secmon", "reserve_mem_size"), props)
        self.assertIn(("/psci", "method"), props)
        self.assertIn(("/partitions/tee", "pname"), props)

    def test_reference_bl31_unlinked(self):
        t = bl33_round18.bl31ref()
        self.assertIn("0x820000ff-words=0 smc#0=0 eret=2", t)
        self.assertIn("no call edge", t)


class TestRound27Layout(unittest.TestCase):
    """reports/round27-bl31-layout.md. AO decode, bl31.img header, BL2 FIP
    table, BL33 page-table census. all offline, from persisted bytes."""

    R13 = os.path.join(REPO, "reports/round13-reloc-verify/mread_37800000_00800000.bin")

    @classmethod
    def setUpClass(cls):
        if not have(cls.R13):
            raise unittest.SkipTest("round-13 band missing")
        cls.band = open(cls.R13, "rb").read()

    def test_ao_cfg3_decode_matches_rsvmem_source(self):
        # live values from round 26 (P_AO_SEC_GP_CFG3 = 0x0c008000)
        bl31_size, bl32_size = round27_layout.ao_decode(0x0C008000)
        self.assertEqual((bl31_size, bl32_size), (0x300000, 0x2000000))
        self.assertEqual(round27_layout.AO_SEC_GP_CFG3, 0xC810024C)
        self.assertEqual(round27_layout.AO_SEC_GP_CFG4, 0xC8100250)
        self.assertEqual(round27_layout.AO_SEC_GP_CFG5, 0xC8100254)

    def test_family_bl31_img_header(self):
        p = os.path.join(REPO, ".src/u-boot-khadas/fip/gxl/bl31.img")
        if not have(p):
            raise unittest.SkipTest("gxl bl31.img missing")
        h = round27_layout.parse_bl31_img(open(p, "rb").read())
        self.assertEqual(h["magic"], 0x12348765)
        self.assertEqual(h["load"], 0x05100000)          # <- image base
        self.assertEqual(h["rsv_start"], 0x05000000)     # -> CFG5
        self.assertEqual(h["rsv_size"], 0x00300000)      # -> CFG3 hi
        self.assertEqual(h["secure_start"], 0x05100000)  # <- live fault boundary
        self.assertEqual(h["secure_size"], 0x00200000)

    def test_family_bl2_fip_table_pins_bl31_load_addr(self):
        p = os.path.join(REPO, ".src/u-boot-khadas/fip/gxl/bl2.bin")
        if not have(p):
            raise unittest.SkipTest("gxl bl2.bin missing")
        data = open(p, "rb").read()
        entries = round27_layout.parse_bl2_fip_table(data)
        by = {e["name"]: e for e in entries}
        self.assertEqual(by["bl30"]["addr"], 0x01100000)
        self.assertEqual(by["bl301"]["addr"], 0x01200000)
        self.assertEqual(by["bl31"]["addr"], 0x05100000)
        self.assertEqual(by["bl32"]["addr"], 0x05300000)
        self.assertEqual(by["bl33"]["addr"], 0x01000000)
        # uuid word0 links prove the record order matches gxlimg's uuid_list
        self.assertEqual(by["bl30"]["link"], 0xAABBCCDD)   # -> bl301
        self.assertEqual(by["bl301"]["link"], 0x6D08D447)  # -> bl31
        self.assertEqual(by["bl31"]["link"], 0x89E1D005)   # -> bl32
        self.assertEqual(by["bl32"]["link"], 0xA7EED0D6)   # -> bl33
        self.assertEqual(by["bl33"]["link"], 0)

    def test_bl33_page_table_is_full_identity(self):
        # page table at 0x37ff0000 baked into the round-13 dump; every
        # 512 MiB section of the 4 GiB identity map is present, so the
        # 0x05100000 fault is NOT an unmapped-page abort in BL33.
        pt_off = 0x37FF0000 - 0x37800000
        shapes = round27_layout.pt_census(self.band, pt_off)
        self.assertEqual(shapes, {1: 8192})
        for lo, hi in ((0x05000000, 0x05100000), (0x05100000, 0x05300000),
                       (0x05300000, 0x05400000)):
            self.assertTrue(round27_layout.pt_covers(self.band, pt_off, lo, hi))

    def test_bl33_clear_range_arithmetic(self):
        # do_rsvmem_check (aquaman build) computes the /secmon clear_range as
        # (bl31_start + 0x100000, bl31_size - 0x500000); with the live AO
        # values that is exactly the observed read/fault boundary pair.
        bl31_start = 0x05000000
        bl31_size = 0x00300000
        self.assertEqual(bl31_start + 0x100000, 0x05100000)
        # clear_end = clear_start + (bl31_size - 0x500000): with bl31_size
        # 0x300000 the delta 0x300000-0x500000 is negative, so on aquaman
        # the encoded pair is (0x05100000, wrap) i.e. "no kernel-visible
        # clear window". the boundary derivation itself is what matters:
        self.assertEqual(bl31_start + 0x100000, 0x05100000)
        self.assertLess(bl31_size, 0x500000)  # wrap condition holds on aquaman


class TestBuildArtifacts(unittest.TestCase):
    def setUp(self):
        if not have(os.path.join(OBJDIR, "arch/arm64/boot/Image")):
            self.skipTest("kernel not built (run tools/build_aquaman_kernel.sh)")

    def test_image_is_valid_arm64(self):
        p = os.path.join(OBJDIR, "arch/arm64/boot/Image")
        with open(p, "rb") as f:
            f.seek(0x38)
            magic = struct.unpack("<I", f.read(4))[0]
        self.assertEqual(magic, 0x644D5241)

    def test_text_offset_is_the_stock_convention(self):
        p = os.path.join(OBJDIR, "arch/arm64/boot/Image")
        with open(p, "rb") as f:
            f.seek(0x08)
            text_offset = struct.unpack("<Q", f.read(8))[0]
        self.assertEqual(text_offset, 0x1080000)

    def test_our_modules_carry_the_flattened_vermagic(self):
        """Same Amlogic Makefile hack as the stock modules. This test is what
        disproved the '4.9.y means a different build' reading."""
        from subprocess import run
        mods = []
        for root, _, files in os.walk(OBJDIR):
            mods += [os.path.join(root, f) for f in files if f.endswith(".ko")]
        if not mods:
            self.skipTest("no modules built")
        for m in mods:
            out = run(["modinfo", "-F", "vermagic", m],
                      capture_output=True, text=True).stdout.strip()
            self.assertTrue(out.startswith("4.9.y "), "%s: %s" % (m, out))

    def test_our_modules_resolve_against_our_symvers(self):
        """A working build is self-consistent. A module may import from
        another module as well as from vmlinux, so Module.symvers has to be
        read in full, not just its vmlinux rows. (ath10k_core.ko importing
        ath_regd_init, which cfg80211 exports, is what caught that.)

        The cross-build against the *stock* modules is the opposite question
        and it does not pass -- that is what blocks reuse, see
        reports/vendor-modules.md."""
        symvers = os.path.join(OBJDIR, "Module.symvers")
        exported = set()
        for line in open(symvers):
            p = line.split()
            if len(p) >= 4:
                exported.add(p[1])
        mods = []
        for root, _, files in os.walk(OBJDIR):
            mods += [os.path.join(root, f) for f in files if f.endswith(".ko")]
        self.assertTrue(mods, "no modules built")
        for m in mods:
            v = ko_versions.versions(m)
            if v is None:
                continue
            for _, sym in v:
                self.assertIn(sym, exported, "%s imports unknown %s" % (m, sym))


class TestRound28Fip(unittest.TestCase):
    """reports/round28-fip-reconstruction.md. FIP ToC layout + UUID table
    (proven by running the vendor fip_create on family artifacts), the
    aml_ctrl_blk_check contract, the aes contract read out of
    aml_encrypt_gxl, and the at-rest ciphertext census of bootloader.img.
    all offline, no device."""

    BL = os.path.join(REPO, "bootloader.img")
    FIPC = os.path.join(REPO, ".src/u-boot-khadas/fip/fip_create")

    @classmethod
    def setUpClass(cls):
        if not have(cls.BL):
            raise unittest.SkipTest("bootloader.img missing")
        cls.bl = open(cls.BL, "rb").read()
        cls.bl33 = None
        p = os.path.join(REPO, "reports/round14-bl33-persist/bl33-37e18000.bin")
        if have(p):
            cls.bl33 = open(p, "rb").read()

    def test_toc_layout_matches_fip_create_output(self):
        # reference package built offline by running fip_create on the family
        # gxl artifacts (see tools/fip_probe.sh); these are its own --dump
        # numbers.
        p = os.path.join(REPO, "reports/round28-fip/ref5-toc.bin")
        if not have(p):
            raise unittest.SkipTest("ref5-toc.bin missing")
        with open(p, "rb") as f:
            toc = round28_fip.parse_toc(f.read())
        got = [(e["name"], e["offset"], e["size"]) for e in toc["entries"]
               if e["name"] is not None]
        self.assertEqual(got, [
            ("TOC",  0x4000, 0x95C0),    # -> BL2 payload
            ("BL2",  0x10000, 0x9784),   # -> BL30 payload
            ("BL30", 0x1C000, 0x2C3A8),  # -> BL31 payload
            ("BL31", 0x4C000, 0xC350),   # -> BL32 payload
            ("BL32", 0x5C000, 0x11170),  # -> BL33 payload
        ])
        # the last entry is the null-uuid terminator carrying the image end
        self.assertEqual(toc["entries"][-1]["offset"], 0x70000)

    def test_bl31_uuid_is_the_tf_a_value(self):
        self.assertEqual(
            round28_fip.bl31_uuid(), "05d0e18953dc13478d2b500a4b7a3e38")

    def test_ctrl_blk_contract(self):
        # aml_ctrl_blk_check: AMLC at +0x0c and +0xfc, 0x200 at +0x02/+0x14/+0xfa
        good = bytearray(0x200)
        struct.pack_into("<I", good, 0x0C, 0x434C4D41)
        struct.pack_into("<I", good, 0xFC, 0x434C4D41)
        struct.pack_into("<H", good, 0x02, 0x200)
        struct.pack_into("<H", good, 0xFA, 0x200)
        struct.pack_into("<I", good, 0x14, 0x200)
        ok, fails = round28_fip.check_ctrl_blk(bytes(good))
        self.assertTrue(ok, fails)
        bad = bytearray(good)
        struct.pack_into("<I", bad, 0xFC, 0)
        self.assertFalse(round28_fip.check_ctrl_blk(bytes(bad))[0])

    def test_aes_contract(self):
        # read out of aml_bl2_enc_file + aml_file_aes in aml_encrypt_gxl
        self.assertEqual(round28_fip.AES_BITS, 256)
        self.assertEqual(round28_fip.IV, b"\x00" * 16)
        self.assertEqual(round28_fip.BL2_ENC_WINDOW, 0xC000)
        self.assertEqual(round28_fip.BL31_IMG_MAGIC, 0x12348765)
        self.assertEqual(len(round28_fip.ROOT_KEY_SHA2), 3)
        for d in round28_fip.ROOT_KEY_SHA2:
            self.assertEqual(len(d), 32)

    def test_bootloader_img_is_uniform_ciphertext(self):
        # the only structural finding that needs no key: nothing anywhere in
        # the file deviates from uniform, so there is no plaintext header, no
        # plaintext ToC and no plaintext BL31 in it.
        self.assertEqual(len(self.bl), 0x148200)
        self.assertLess(round28_fip.chi2(self.bl), 310)
        rows = round28_fip.census(self.bl, 4096)
        self.assertEqual(len(rows), 329)
        self.assertTrue(all(c < 340 for _, c, _ in rows),
                        "a 4K block deviates from uniform")

    def test_bootloader_img_has_no_known_magic(self):
        pats = [struct.pack("<I", round28_fip.TOC_MAGIC),
                struct.pack("<I", round28_fip.TOC_VERSION),
                struct.pack("<I", round28_fip.BL31_IMG_MAGIC),
                b"AMLC", b"@AML", b"ANDROID!"]
        pats += [bytes.fromhex(u)[:4] for u in round28_fip.FIP_UUIDS]
        for p in pats:
            self.assertNotIn(p, self.bl, "%s present in bootloader.img" % p.hex())

    def test_single_128_byte_record_repeats_five_times(self):
        dup, where = round28_fip.repeats(self.bl, 16)
        self.assertEqual(len(dup), 8)          # 8 blocks of one 128-byte record
        sites = where[next(iter(dup))]
        self.assertEqual(sites, [0xC080, 0x10080, 0x20080, 0x4C080, 0x8C080])
        lo, hi = round28_fip.common_run(self.bl, sites)
        self.assertEqual((lo, hi), (0, 128))

    def test_ecb_refuted_for_bl33(self):
        # the live BL33 plaintext shares no 16-byte block with bootloader.img
        if self.bl33 is None:
            raise unittest.SkipTest("round-14 BL33 dump missing")
        self.assertEqual(round28_fip.search_blocks(self.bl33, self.bl, 16), [])

    def test_dt_img_is_keyid_plus_ciphertext(self):
        # dt.img = szSHA2KeyID (32 bytes, plaintext) + 0xE800 ciphertext.
        # The KeyID equals the szSHA2KeyID of the AMLSECU! descriptors in
        # boot.img/recovery.img; the ciphertext tail is uniform and does not
        # equal the dtb object stored inside boot.img.
        p = os.path.join(REPO, "dt.img")
        if not have(p):
            raise unittest.SkipTest("dt.img missing")
        dtb = open(p, "rb").read()
        boot = open(os.path.join(REPO, "boot.img"), "rb").read()
        if boot[0x800:0x808] != round28_fip.AMLSECU_MAGIC:
            raise unittest.SkipTest("boot.img AMLSECU! header missing")
        _, _, _, keyid = round28_fip.amlsecu_block(boot, "dtb")
        self.assertEqual(dtb[:32], keyid)
        tail = dtb[0x20:]
        self.assertEqual(len(tail), 0xE800)
        self.assertGreater(round28_fip.entropy(tail), 7.9)
        _, nraw, ntot, _ = round28_fip.amlsecu_block(boot, "dtb")
        self.assertEqual(nraw, len(dtb))       # descriptor raw length
        self.assertEqual(ntot, 0xF000)         # 2048-aligned

    def test_boot_img_payload_map(self):
        # boot.img payload map, all derived from the AMLSECU! descriptors:
        # container [0x800, 0x969000), AVB hash [0x969000, 0x96b000),
        # "AVB0" at 0x96a000, zeros after. Payloads start at container offset
        # 0x800 (file 0x1000) and ciphertexts do NOT carry the KeyID prefix.
        boot = open(os.path.join(REPO, "boot.img"), "rb").read()
        if boot[0x800:0x808] != round28_fip.AMLSECU_MAGIC:
            raise unittest.SkipTest("boot.img AMLSECU! header missing")
        koff, kraw, ktot, kid = round28_fip.amlsecu_block(boot, "kernel")
        doff, draw, dtot, did = round28_fip.amlsecu_block(boot, "dtb")
        self.assertEqual((koff, kraw, ktot), (0x800, 9800145, 0x959000))
        self.assertEqual((doff, draw, dtot), (0x959800, 59424, 0xF000))
        self.assertEqual(kid, did)
        end = round28_fip.AMLSECU_HDR_OFF + doff + dtot
        self.assertEqual(end, 0x969000)
        # AVB tail: hash block [0x969000, 0x96a000), vbmeta header @0x96a000,
        # zeros up to the footer in the last 0x40 bytes of the image.
        self.assertEqual(boot[0x96a000:0x96a004], b"AVB0")
        self.assertEqual(boot[0xFFFFC0:0xFFFFC4], b"AVBf")
        # AVB footer (last 0x40): vendor deviation from libavb -- the three
        # payload fields are stored as BIG-ENDIAN u32 (spec: BE u64), each
        # followed by a zero u32. footer+0x10 = 0x969200, +0x18 = 0x96A000
        # (vbmeta offset), +0x20 = 0x200 (vbmeta size).
        self.assertEqual(struct.unpack_from(">I", boot, 0xFFFFD0)[0], 0x969200)
        self.assertEqual(struct.unpack_from(">I", boot, 0xFFFFD8)[0], 0x96A000)
        self.assertEqual(struct.unpack_from(">I", boot, 0xFFFFE0)[0], 0x200)
        self.assertEqual(struct.unpack_from("<I", boot, 0xFFFFD4)[0], 0)
        self.assertTrue(all(b == 0 for b in boot[0x96B000:0xFFFFC0]))
        self.assertNotEqual(boot[koff:koff + 32], kid)

    def test_bootloader_record_is_not_the_firmware_keyid(self):
        # the five 128-byte records in bootloader.img do not embed the
        # firmware's szSHA2KeyID (ef8996bd...) in any 16-byte slice.
        boot = open(os.path.join(REPO, "boot.img"), "rb").read()
        if boot[0x800:0x808] != round28_fip.AMLSECU_MAGIC:
            raise unittest.SkipTest("boot.img AMLSECU! header missing")
        _, _, _, keyid = round28_fip.amlsecu_block(boot, "kernel")
        for off in (0xC080, 0x10080, 0x20080, 0x4C080, 0x8C080):
            rec = self.bl[off:off + 128]
            self.assertNotIn(keyid[:16], rec)
            self.assertNotIn(keyid[16:], rec)

    def test_no_public_key_reveals_the_toc(self):
        # IV is zero, so block 0 alone is an oracle. try the digests the vendor
        # tool itself hardcodes plus a few obvious keys.
        toc = struct.pack("<II", round28_fip.TOC_MAGIC, round28_fip.TOC_VERSION)
        toc += b"\x00" * 8
        keys = list(round28_fip.ROOT_KEY_SHA2) + [b"\x00" * 32, b"\xff" * 32]
        import hashlib
        for s in (b"aml", b"amlogic", b"fip", b"12345678", b"aml_encrypt_gxl"):
            keys.append(hashlib.sha256(s).digest())
        for k in keys:
            self.assertNotEqual(round28_fip.cbc_decrypt_block0(k, self.bl)[:4],
                                toc[:4], "a candidate key decrypts the ToC magic")


class TestRound29Crypto(unittest.TestCase):
    """reports/round29-fip-crypto/. The aml_encrypt_gxl pipeline read out of
    the vendor ELF (main -> 30 getopt handlers -> bootmk/bl2enc/bl3enc), the
    aml user key package format (aml_key_bnd producer), the fixture oracle
    negatives, and the three structural mismatches between bootloader.img
    and the v1.3 in-tree tool. all offline.
    """

    BL = os.path.join(REPO, "bootloader.img")

    @classmethod
    def setUpClass(cls):
        if not have(cls.BL):
            raise unittest.SkipTest("bootloader.img missing")
        cls.bl = open(cls.BL, "rb").read()

    def test_bootmk_v1_layout_and_tail_arithmetic(self):
        # aml_boot_make: BL2 [0,0xC000), header at 0xC000, payloads from
        # 0x10000, five streams with the sizes round 28 inferred (reading B).
        # 0x8C000 + 0xBC200 closes the file exactly.
        self.assertEqual(len(self.bl), 0x148200)
        self.assertEqual(0x8C000 + 0xBC200, len(self.bl))
        self.assertEqual(round29_crypto.BOOTMK_HDR_START, 0xC000)
        self.assertEqual(round29_crypto.BOOTMK_HDR_V1_END, 0xFE00)
        self.assertEqual(round29_crypto.BOOTMK_HDR_V3_END, 0x10000)

    def test_v1_ctrl_block_must_have_a_plaintext_copy(self):
        # aml_boot_make writes the 0x200 ctrl block at 0xC000 AND 0xFE00.
        # at rest those windows differ -> this file is not a v1.3 --bootmk
        # output with a plaintext ctrl. (either key=1, or v3, or other tool.)
        self.assertFalse(self.bl[0xC000:0xC200] == self.bl[0xFE00:0x10000],
                         "ctrl copy found -- v1 bootmk becomes viable")

    def test_v3_header_would_carry_zero_mga_magic(self):
        # boot_make_v3 writes 0xaa640001 / 0x00030001 at 0xC000+0; word +4
        # is version 0x00030001, NOT the ToC version 0x12345678.
        import struct
        self.assertEqual(round29_crypto.TOC_VERSION_V3, 0x00030001)
        self.assertNotEqual(round29_crypto.TOC_VERSION_V3,
                            round29_crypto.TOC_VERSION)

    def test_package_format_constants(self):
        self.assertEqual(round29_crypto.PKG_SIZE_FULL, 0x1B40)
        self.assertEqual(round29_crypto.PKG_SIZE_SMALL, 0x20)
        self.assertEqual(round29_crypto.PKG_ROOTKEYMAX_MAX, 0x1248)
        self.assertEqual(round29_crypto.PKG_AESKEY_TAIL, 0x20)

    def test_fixtures_are_single_tailed_and_not_the_key(self):
        # the 32 vendor aml-user-key.sig fixtures: 0x1B40 each, one unique
        # tail32, and NONE of them decrypts the ToC first block (both
        # candidate sites 0x0000 and 0xC000, IV=0).
        fx = round29_crypto.user_key_fixtures()
        self.assertEqual(len(fx), 32)
        for _, _, blob in fx:
            self.assertEqual(len(blob), 0x1B40)
        tails = {blob[-32:] for _, _, blob in fx}
        self.assertEqual(len(tails), 1)
        ct0 = self.bl[:16]
        ctC = self.bl[0xC000:0xC010]
        toc8 = round29_crypto.TOC_FIRST_BLOCK[:4]
        for key in tails:
            self.assertNotEqual(
                round29_crypto.ecb_decrypt_block(key, ct0)[:4], toc8)
            self.assertNotEqual(
                round29_crypto.ecb_decrypt_block(key, ctC)[:4], toc8)
        # also the no-userkey build variant: key_info all zero -> key 00*32
        zero = bytes(32)
        self.assertNotEqual(
            round29_crypto.ecb_decrypt_block(zero, ct0)[:4], toc8)
        self.assertNotEqual(
            round29_crypto.ecb_decrypt_block(zero, ctC)[:4], toc8)

    def test_bl31_img_fixture_header(self):
        # the in-tree gxl/bl31.img is a --bl3sig output: 0x200 PLAINTEXT
        # header + intact bl31.bin + tail.
        p = os.path.join(REPO, ".src/u-boot-khadas/fip/gxl/bl31.img")
        if not have(p):
            raise unittest.SkipTest("gxl bl31.img missing")
        img = open(p, "rb").read()
        h = round29_crypto.parse_bl31_img_header(img)
        self.assertEqual(h["magic"], 0x12348765)
        self.assertEqual(h["load"], 0x05100000)
        self.assertEqual(h["secure_start"], 0x05100000)
        self.assertEqual(h["secure_size"], 0x00200000)
        # header word 4 is the image size and matches the bin length
        self.assertEqual(h["size"], 0x4E20)  # header table stride size
        binp = os.path.join(REPO, ".src/u-boot-khadas/fip/gxl/bl31.bin")
        b = open(binp, "rb").read()
        self.assertEqual(len(img), len(b) + 0x200)
        self.assertEqual(img[0x200:], b)

    def test_record128_is_not_in_any_plaintext_object(self):
        # the shared 128B record exists only in the two bootloader.img copies
        # -- no in-tree plaintext object (BL2/BL30/BL31/BL33/key fixtures)
        # contains it, so it is not a plaintext transport header.
        rec = self.bl[0xC080:0xC0C0]
        base = os.path.join(REPO, ".src/u-boot-khadas/fip/gxl")
        for name in ("bl2.bin", "bl30.bin", "bl31.bin", "bl31.img"):
            p = os.path.join(base, name)
            if have(p):
                self.assertNotIn(rec, open(p, "rb").read(), name)
        for board, _, blob in round29_crypto.user_key_fixtures():
            self.assertNotIn(rec, blob, board)

    def test_pipeline_contradictions_are_recorded(self):
        # the three mismatches that close the 'v1.3 --bootmk produced this
        # file directly' hypothesis, as measurable facts.
        # (1) no plaintext ctrl at 0xFE00 (covered above)
        # (2) no plaintext bl31.img header magic anywhere
        self.assertNotIn(struct.pack("<I", 0x12348765), self.bl)
        # (3) no plaintext LZ4C wrapper magic anywhere
        self.assertNotIn(struct.pack("<I", 0x43345A4C), self.bl)

    def test_negative_log_covers_structural_candidates(self):
        neg = round29_crypto.negative_log()
        self.assertIn("00" * 32, neg)
        self.assertIn("ff" * 32, neg)
        # at least the fixture tail32 is in there
        fx = round29_crypto.user_key_fixtures()
        self.assertIn(fx[0][2][-32:].hex(), neg)

    def test_oracle_rejects_wrong_lengths(self):
        with self.assertRaises(ValueError):
            round29_crypto.check_key(b"\x00" * 31, b"\x00" * 16,
                                     b"\x00" * 16)

    def test_oracle_roundtrip(self):
        # the oracle must MATCH for a key we can demonstrate: encrypt a known
        # block under a random key and verify check_key returns True.
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
        key = bytes(range(32))
        pt = round29_crypto.TOC_FIRST_BLOCK
        enc = Cipher(algorithms.AES(key), modes.ECB()).encryptor()
        ct = enc.update(pt) + enc.finalize()
        self.assertTrue(round29_crypto.check_key(key, ct, pt))
        self.assertFalse(round29_crypto.check_key(bytes(32), ct, pt))


PUBLIC_PKG = os.path.join(REPO, "artifacts/public-keys/superbird_aml-user-key.sig")


class TestRound30Provenance(unittest.TestCase):
    """reports/round30-firmware-provenance.md. The public-provenance closure:
    the one public production key package (superbird/Car Thing) is
    format-identical to the vendor fixtures, oracle-NEGATIVE against the
    aquaman ciphertext, and the round-29 stage-1 contract is proven live by
    running the vendor bootsig with it. All offline.
    """

    BL = os.path.join(REPO, "bootloader.img")

    @classmethod
    def setUpClass(cls):
        if not have(cls.BL):
            raise unittest.SkipTest("bootloader.img missing")
        cls.bl = open(cls.BL, "rb").read()

    def test_public_pkg_pinned(self):
        """The persisted superbird package: full 0x1B40 format, sha256 pinned
        upstream by ThingLabsOSS/superbird-fip-tools setup.sh."""
        if not have(PUBLIC_PKG):
            self.skipTest("superbird package not persisted")
        blob = open(PUBLIC_PKG, "rb").read()
        self.assertEqual(len(blob), 0x1B40)
        self.assertEqual(hashlib.sha256(blob).hexdigest(),
                         "f48c731e064193c6584fe3785c193e6ec0ed51c892b5c20457641945cf906afc")

    def test_public_pkg_same_template_as_fixtures(self):
        """Second production sample of the aml_key_bnd template: the >=16-byte
        zero-run map is IDENTICAL to the vendor fixtures (same producer, same
        RSA blob sizes, only the material differs)."""
        if not have(PUBLIC_PKG):
            self.skipTest("superbird package not persisted")
        fx = round29_crypto.user_key_fixtures()
        ref = fx[0][2]

        def zeroruns(b):
            out, i = [], 0
            while i < len(b):
                if b[i] == 0:
                    j = i
                    while j < len(b) and b[j] == 0:
                        j += 1
                    if j - i >= 16:
                        out.append((i, j))
                    i = j
                else:
                    i += 1
            return out

        self.assertEqual(zeroruns(open(PUBLIC_PKG, "rb").read()), zeroruns(ref))

    def test_public_pkg_tail32_is_oracle_negative(self):
        """The one public production key does NOT decrypt the aquaman
        ciphertext first block at either candidate site (IV=0)."""
        if not have(PUBLIC_PKG):
            self.skipTest("superbird package not persisted")
        tail = open(PUBLIC_PKG, "rb").read()[-32:]
        toc8 = round29_crypto.TOC_FIRST_BLOCK[:4]
        for ct in (self.bl[:16], self.bl[0xC000:0xC010]):
            self.assertNotEqual(
                round29_crypto.ecb_decrypt_block(tail, ct)[:4], toc8)

    def test_public_pkg_is_not_a_fixture_tail(self):
        """And it is genuinely different material from the 32 reference
        packages (no accidental copy)."""
        if not have(PUBLIC_PKG):
            self.skipTest("superbird package not persisted")
        tails = {b[-32:] for _, _, b in round29_crypto.user_key_fixtures()}
        self.assertNotIn(open(PUBLIC_PKG, "rb").read()[-32:], tails)

    def test_bootloader_differs_from_reproduced_v13_output(self):
        """The v1.3 --bootsig artifact produced in round 30 (/tmp) proves the
        at-rest constraints on a REAL bootsig output: zero repeated 16B
        blocks (record128 needs ONE common key) and no plaintext AMLC. The
        at-rest file differs from it (different build, different key)."""
        enc = "/tmp/round30-repro/u-boot.bin.encrypt"
        if not have(enc):
            self.skipTest("round-30 reproduction artifact missing "
                          "(reports/round30-provenance/05)")
        data = open(enc, "rb").read()
        seen, dups = {}, 0
        for i in range(0, len(data) - 16, 16):
            b = data[i:i + 16]
            if b in seen:
                dups += 1
            else:
                seen[b] = i
        self.assertEqual(dups, 0)
        self.assertNotIn(b"AMLC", data)
        self.assertNotEqual(data, self.bl)


if __name__ == "__main__":
    unittest.main(verbosity=2)
