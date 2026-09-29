#!/usr/bin/env python3
"""mk_m1_boot.py - assemble m1_boot.img: ANDROID! v0 + M1 delay stub as kernel.
Usage: python3 tools/mk_m1_boot.py   (generates m1_boot.img, ~4 KB, RAM-only)
"""
import struct
import subprocess
import sys

TC = ".src/MiTV_OpenSource/cross_compile_tool/bin/aarch64-linux-gnu-"
# usage: mk_m1_boot.py [outer_hex] [out.img]  (default: 0x0FA0 m1_boot.img)
outer = sys.argv[1] if len(sys.argv) > 1 else "0x0FA0"
out = sys.argv[2] if len(sys.argv) > 2 else "m1_boot.img"

subprocess.run([TC + "gcc", "-c", "-march=armv8-a", "-nostdlib",
                "-DM1_OUTER=" + outer,
                "tools/m1_delay_stub.S", "-o", "/tmp/m1_stub.o"],
               check=True)
subprocess.run([TC + "objcopy", "-O", "binary",
                "/tmp/m1_stub.o", "/tmp/m1_kernel.bin"],
               check=True)
kern = open("/tmp/m1_kernel.bin", "rb").read()
assert struct.unpack("<I", kern[0x38:0x3C])[0] == 0x644D5241, "no ARM64 magic"
print("stub: %d bytes, magic ok" % len(kern))

PAGE = 2048
hdr = bytearray(PAGE)
struct.pack_into("<8s10I", hdr, 0, b"ANDROID!", len(kern), 0x1080000,
                 0, 0x13000000, 0, 0xF00000, 0x100, PAGE, 0, 0)
img = bytes(hdr) + kern + b"\0" * (-len(kern) % PAGE)
open(out, "wb").write(img)
print("%s: %d bytes (kernel_addr 0x1080000, page 2048, outer %s)"
      % (out, len(img), outer))
