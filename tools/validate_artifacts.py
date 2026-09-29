#!/usr/bin/env python3
"""Validate build artifacts: ELF/Image header, arch, sizes, DTB magic, modules.

usage: validate_artifacts.py <objdir>
exit 0 if every required artifact is present and sane, 1 otherwise.
"""
import os
import struct
import sys

ARM64_MAGIC = 0x644D5241  # "ARM\x64" little-endian
FDT_MAGIC = 0xD00DFEED
MIN_IMAGE = 1 << 20       # a working arm64 Image is never under 1 MiB
STOCK_IMAGE_APPROX = 27 << 20


def check(label, ok, detail=""):
    print("  %-6s %-34s %s" % ("PASS" if ok else "FAIL", label, detail))
    return ok


def read_at(path, off, n):
    with open(path, "rb") as f:
        f.seek(off)
        return f.read(n)


def main():
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    obj = sys.argv[1]
    ok = True

    image = os.path.join(obj, "arch/arm64/boot/Image")
    vmlinux = os.path.join(obj, "vmlinux")
    symvers = os.path.join(obj, "Module.symvers")
    dts = os.path.join(obj, "arch/arm64/boot/dts")

    print("artifacts in %s" % obj)

    if not os.path.exists(image):
        return check("Image present", False, image) or 1
    size = os.path.getsize(image)
    magic = struct.unpack("<I", read_at(image, 0x38, 4))[0]
    ok &= check("Image present", True, "%d bytes (%.1f MiB)" % (size, size / 1048576.0))
    ok &= check("Image arm64 magic @0x38", magic == ARM64_MAGIC,
                "0x%08x" % magic)
    ok &= check("Image size sane", size > MIN_IMAGE,
                "stock ~%d MiB" % (STOCK_IMAGE_APPROX >> 20))
    text_off, img_size = struct.unpack("<QQ", read_at(image, 0x08, 16))
    ok &= check("Image text_offset", text_off != 0, "0x%x" % text_off)
    ok &= check("Image image_size", img_size != 0, "0x%x" % img_size)

    if os.path.exists(vmlinux):
        head = read_at(vmlinux, 0, 20)
        is_elf = head[:4] == b"\x7fELF"
        machine = struct.unpack_from("<H", head, 18)[0] if is_elf else 0
        ok &= check("vmlinux ELF aarch64", is_elf and machine == 0xB7,
                    "machine 0x%x" % machine)
    else:
        ok &= check("vmlinux present", False)

    if os.path.exists(symvers):
        n = sum(1 for line in open(symvers) if line.split() and
                line.split()[2] == "vmlinux")
        ok &= check("Module.symvers vmlinux exports", n > 1000, "%d symbols" % n)
    else:
        ok &= check("Module.symvers present", False)

    dtbs = []
    for root, _, files in os.walk(dts) if os.path.isdir(dts) else []:
        dtbs += [os.path.join(root, f) for f in files if f.endswith(".dtb")]
    ok &= check("dtb built", len(dtbs) > 0, "%d found" % len(dtbs))
    for d in dtbs:
        m = struct.unpack(">I", read_at(d, 0, 4))[0]
        ok &= check("dtb fdt magic %s" % os.path.basename(d), m == FDT_MAGIC,
                    "0x%08x" % m)

    print("RESULT: %s" % ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
