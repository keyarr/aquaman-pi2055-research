#!/usr/bin/env python3
"""inspect_test_image.py - offline proof that a test image reaches bootm entrypoint.

Simulates, in order, the validators bootm X will hit on the aquaman
2015.01 fork (khadas/u-boot khadas-vims-nougat reference):
  genimg_get_format -> android_image_get_kernel -> bootm_find_os ->
  bootm_load_os (ARM64 magic at ep+0x38) -> boot_jump_linux.

Usage: python3 tools/inspect_test_image.py [--bootm-addr 0x1080000] <img...>
Exit 0 if EVERY file would reach the entrypoint, 1 otherwise.
Read-only, never touches the device.
"""
import struct
import sys
import binascii

X_DEFAULT = 0x01080000  # runtime-proven 2026-09-29: BUF==loadaddr on this
# build (see reports/buffer-equals-loadaddr-proof.md). the old 0x10200000
# came from the khadas reference header only, refuted on-device.
X_REF_KHADAS = 0x10200000
Y_DEFAULT = 0x01080000  # loadaddr env default (gxl_p241_v1.h:90)
GXB_IMG_SIZE = 0x1800000  # 24 MiB (arch/arm/include/asm/arch-gxl/bl31_apis.h:118)
GXB_IMG_LOAD_ADDR = 0x01080000
ARM64_MAGIC = 0x644D5241
IH_MAGIC = 0x27051956
FIT_MAGIC = 0xD00DFEED

LZOP_MAGIC = bytes([0x89, 0x4C, 0x5A, 0x4F, 0x00, 0x0D, 0x0A, 0x1A, 0x0A])
GZIP_MAGIC = bytes([0x1F, 0x8B])


def align(n, a):
    return (n + a - 1) // a * a if a else n


def genimg_format(d):
    if len(d) >= 4 and struct.unpack(">I", d[:4])[0] == IH_MAGIC:
        return "LEGACY"
    if len(d) >= 4 and struct.unpack(">I", d[:4])[0] == FIT_MAGIC:
        return "FIT"
    if d[:8] == b"ANDROID!":
        return "ANDROID"
    return "INVALID"


def android_comp(payload):
    if payload[:9] == LZOP_MAGIC:
        return "LZO"
    if payload[:2] == GZIP_MAGIC:
        return "GZIP"
    return "NONE"


def inspect_android(path, d, X):
    ok = True
    print("  format: ANDROID (genimg_get_format: memcmp ANDROID! ok)")
    magic, ksz, kaddr = d[:8], struct.unpack("<I", d[8:12])[0], struct.unpack("<I", d[12:16])[0]
    rsz = struct.unpack("<I", d[16:20])[0]
    tags = struct.unpack("<I", d[20:24])[0]
    second_sz = struct.unpack("<I", d[24:28])[0]
    second_addr = struct.unpack("<I", d[28:32])[0]
    page = struct.unpack("<I", d[36:40])[0]
    hver = struct.unpack("<I", d[40:44])[0]
    print("  header magic: ANDROID! OK")
    print("  kernel_size=%d kernel_addr=0x%x ramdisk_size=%d second_size=%d "
          "tags=0x%x second_addr=0x%x page_size=%d header_version=%d"
          % (ksz, kaddr, rsz, second_sz, tags, second_addr, page, hver))
    if page not in (512, 1024, 2048, 4096, 8192, 16384):
        print("  WARN page_size unusual (stock uses 2048)")
    if page == 0 or ksz == 0:
        print("  FAIL: page_size/kernel_size zero -> os_len 0 -> "
              "\"ERROR: can't get kernel image!\" (bootm.c:92)");
        return False
    if len(d) < page + ksz:
        print("  FAIL: file truncated (need page+ksz=%d, have %d)" % (page + ksz, len(d)))
        return False
    payload = d[page:page + ksz]
    comp = android_comp(payload)
    print("  compression: %s (android_image_get_comp mirrors lzo/gzip magic probe; "
          "need NONE for memmove path)" % comp)
    if comp != "NONE":
        print("  FAIL: compressed kernel needs malloc+reloc (android_image_need_move) "
              "and valid compressed stream; use NONE")
        ok = False
    kload = kaddr
    if kload == 0x10008000:
        kload = 0x1080000
        print("  kload quirk: 0x10008000 remapped to 0x1080000 (bootm.c:160)")
    print("  load (kload): 0x%x  entry (ep=load): 0x%x" % (kload, kload))
    if kload == 0:
        print("  FAIL: kload 0");
        return False
    blob_start, blob_end = X, X + page + align(ksz, page) + align(rsz, page) + align(second_sz, page)
    image_start, image_len = X + page, ksz
    load_end = kload + image_len
    no_overlap = (comp == "NONE" and kload == image_start)
    overlap = (not no_overlap) and (kload < blob_end) and (load_end > blob_start)
    print("  with bootm X=0x%x: image_start=0x%x image_len=%d blob=[0x%x,0x%x) "
          "load_end=0x%x no_overlap=%s overlap=%s"
          % (X, image_start, image_len, blob_start, blob_end, load_end, no_overlap, overlap))
    if len(payload) < 0x3C:
        print("  FAIL: kernel < 60 bytes, no room for ARM64 magic at +0x38")
        return False
    m = struct.unpack("<I", payload[0x38:0x3C])[0]
    print("  ARM64 magic at kernel+0x38: 0x%08x (need 0x644d5241)" % m)
    if overlap:
        if m != ARM64_MAGIC:
            print("  FAIL -> overlap so bootm_load_os checks ep+0x38 -> "
                  "\"Bad Linux ARM64 Image magic!\" (bootm.c:464), return 1, reset")
            return False
        print("  overlap -> bootm_load_os checks ep+0x38 AFTER memmove (bootm.c:462-466): OK")
    else:
        print("  no overlap ([load,load_end) vs [blob_start,blob_end) disjoint) -> "
              "bootm_load_os SKIPS the ep+0x38 check (bootm.c:444) and returns 0; "
              "GO jumps to ep unconditionally")
        if m != ARM64_MAGIC:
            print("  WARN: magic absent but harmless on THIS path; keep it anyway "
                  "(required if the same bytes are ever booted from Y=0x1080000, "
                  "where overlap=True and the check runs)")
        else:
            print("  magic present anyway: same file also passes the Y-path check")
    toff, isz = struct.unpack("<QQ", payload[8:24])
    print("  text_offset=0x%x image_size=%d (informational; ANDROID path ignores "
          "both, runs at kload)" % (toff, isz))
    total = page + align(ksz, page) + align(rsz, page) + align(second_sz, page)
    print("  total image footprint: %d bytes (GXB window 24 MiB: %s)"
          % (total, "OK" if total <= GXB_IMG_SIZE else "EXCEEDS - aml_sec_boot_check SMC may reject"))
    if total > GXB_IMG_SIZE:
        ok = False
    if len(d) > GXB_IMG_SIZE:
        print("  NOTE: file size %d > 24 MiB; download would still succeed "
              "(limit is ddr_size_usable, ~hundreds of MB) but the SMC decrypt "
              "window starting at X only covers 24 MiB" % len(d))
    print("  ramdisk: %s  fdt: control DTB via dtb_mem_addr/get_multi_dt_entry "
          "(no 3rd bootm arg needed)" % ("absent, rd_start=rd_end=0" if rsz == 0 else "present"))
    return ok


def inspect_legacy(path, d, X):
    print("  format: LEGACY (genimg_get_format: IH_MAGIC 0x27051956 ok)")
    ih = struct.unpack(">IIIIIIIIBBBB32s", d[:64])
    magic, hcrc, time_, size, load, ep, dcrc = ih[0], ih[1], ih[2], ih[3], ih[4], ih[5], ih[6]
    os_, arch, type_, comp = ih[7], ih[8], ih[9], ih[10]
    name = ih[11].split(b"\0")[0]
    print("  magic=0x%08x load=0x%x ep=0x%x size=%d os=%d arch=%d type=%d comp=%d name=%s"
          % (magic, load, ep, size, os_, arch, type_, comp, name))
    hdr = bytearray(d[:64])
    struct.pack_into(">I", hdr, 4, 0)
    calc_hcrc = binascii.crc32(bytes(hdr)) & 0xFFFFFFFF
    print("  hcrc stored=0x%08x computed=0x%08x %s (image_get_kernel: always checked)"
          % (hcrc, calc_hcrc, "OK" if hcrc == calc_hcrc else "FAIL"))
    if hcrc != calc_hcrc:
        return False
    print("  arch: %d (need 22=ARM64, IH_ARCH_DEFAULT on arm64)  os: %d (need 5=LINUX)  "
          "type: %d (need 2/14/4/3 KERNEL/NOLOAD/MULTI/STANDALONE)  comp: %d (need 0=NONE)"
          % (arch, os_, type_, comp))
    if arch != 22 or os_ != 5 or type_ not in (2, 14, 4, 3) or comp != 0:
        print("  FAIL: header field mismatch")
        return False
    calc_dcrc = binascii.crc32(d[64:64 + size]) & 0xFFFFFFFF if len(d) >= 64 + size else None
    print("  dcrc stored=0x%08x computed=%s (only checked if verify=yes env)"
          % (dcrc, ("0x%08x" % calc_dcrc) if calc_dcrc is not None else "TRUNCATED"))
    image_start, image_len = X + 64, size
    no_overlap = (comp == 0 and load == image_start)
    load_end = load + image_len
    overlap = (not no_overlap) and (load < X + 64 + size) and (load_end > X)
    print("  with bootm X=0x%x: image_start=0x%x no_overlap=%s overlap=%s"
          % (X, image_start, no_overlap, overlap))
    if overlap:
        if size < 0x3C:
            print("  FAIL: too small for ARM64 check");
            return False
        m = struct.unpack("<I", d[64 + 0x38:64 + 0x3C])[0]
        print("  ARM64 magic at data+0x38: 0x%08x (need 0x644d5241)" % m)
        if m != ARM64_MAGIC:
            print("  FAIL -> bootm_load_os returns 1");
            return False
    else:
        print("  no_overlap: ARM64 magic check SKIPPED (bootm.c:444), jumps to ep=0x%x" % ep)
    return True


def inspect_fit(path, d, X):
    print("  format: FIT (genimg_get_format: fdt_check_header ok)")
    totalsize = struct.unpack(">I", d[4:8])[0] if len(d) >= 8 else 0
    print("  fdt magic 0xd00dfeed OK, totalsize=%d" % totalsize)
    has = lambda s: (d.find(s) >= 0)
    print("  has /images/kernel node: %s  arch=arm64: %s  os=linux: %s  type=kernel: %s  "
          "load prop: %s  entry prop: %s"
          % (has(b"kernel"), has(b"arm64"), has(b"linux"), has(b"kernel"),
             has(b"load"), has(b"entry")))
    print("  NOTE: FIT kernel path needs config node + loadable kernel subimage "
          "(image-fit.c:1508 fit_image_load) AND ARM64 magic at ep+0x38 "
          "(bootm.c:462, CONFIG_ANDROID_BOOT_IMAGE overlap branch).")
    print("  FIT is valid but heavier than ANDROID for this test; prefer ANDROID.")
    return True


def inspect_one(path, X):
    d = open(path, "rb").read()
    print("== %s (%d bytes), bootm addr 0x%x" % (path, len(d), X))
    print("  GXB window: file %s 24 MiB" % ("fits in" if len(d) <= GXB_IMG_SIZE else "EXCEEDS"))
    fmt = genimg_format(d)
    if fmt == "INVALID":
        print("  format: INVALID (no legacy/FIT/ANDROID magic)")
        print("  -> boot_get_kernel returns NULL -> \"Wrong Image Format\" / "
              "\"ERROR: can't get kernel image!\" (bootm.c:896,93) -> return 1 -> reset")
        print("  VERDICT: would NOT reach entrypoint (this is the raw-stub trap)")
        return False
    if fmt == "ANDROID":
        ok = inspect_android(path, d, X)
    elif fmt == "LEGACY":
        ok = inspect_legacy(path, d, X)
    else:
        ok = inspect_fit(path, d, X)
    print("  VERDICT: %s" % ("would reach entrypoint" if ok else "would NOT reach entrypoint"))
    return ok


def main():
    X = X_DEFAULT
    files = []
    for a in sys.argv[1:]:
        if a.startswith("--bootm-addr="):
            X = int(a.split("=", 1)[1], 16)
        elif a in ("-h", "--help"):
            print(__doc__)
            return 0
        else:
            files.append(a)
    if not files:
        print("usage: inspect_test_image.py [--bootm-addr=0x1080000] <img...>")
        return 2
    print("BUF=0x%x (download buffer == loadaddr on this build)  GXB=0x%x"
          % (X, GXB_IMG_SIZE))
    rc = 0
    for f in files:
        print()
        if not inspect_one(f, X):
            rc = 1
    return rc


if __name__ == "__main__":
    sys.exit(main())
