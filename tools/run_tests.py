#!/usr/bin/env python3
"""Test suite for the offline parsers and the build artifacts.

stdlib unittest only, no pytest, no network, no device.

  python3 tools/run_tests.py            # everything
  python3 tools/run_tests.py -v         # verbose

Every test either checks a parser against a known-good fixture, or checks a
claim that a report makes. Tests that need artifacts that may not exist are
skipped, not silently passed.
"""
import os
import struct
import sys
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "tools"))

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


# ---------------------------------------------------------------- artifacts

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


if __name__ == "__main__":
    unittest.main(verbosity=2)
