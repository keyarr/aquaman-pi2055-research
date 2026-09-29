#!/usr/bin/env python3
"""analyze_android_boot.py - parse boot.img header + AMLSECU blocks.
Usage: python3 analyze_android_boot.py [boot.img|recovery.img]
"""
import struct, sys
path = sys.argv[1] if len(sys.argv) > 1 else "boot.img"
with open(path, "rb") as f:
    hdr = f.read(2048)
    print("magic:", hdr[:8])
    print("kernel_size:", struct.unpack("<I", hdr[8:12])[0])
    print("kernel_addr:", hex(struct.unpack("<I", hdr[12:16])[0]))
    print("ramdisk_size:", struct.unpack("<I", hdr[16:20])[0])
    print("second_size:", struct.unpack("<I", hdr[24:28])[0])
    print("second_addr:", hex(struct.unpack("<I", hdr[28:32])[0]))
    print("page_size:", struct.unpack("<I", hdr[36:40])[0])
    print("header_version:", struct.unpack("<I", hdr[40:44])[0])
    print("cmdline:", hdr[64:64+128].split(b"\0")[0].decode())
    ps = struct.unpack("<I", hdr[36:40])[0]
    f.seek(ps)
    k = f.read(32 + 3*96)
    print("k magic:", k[:8], "ver:", hex(struct.unpack("<I", k[8:12])[0]),
          "nblk:", struct.unpack("<I", k[12:16])[0], "ts:", k[16:32])
    for i in range(3):
        b = k[32+i*96:32+(i+1)*96]
        off, raw, sig, al, tot = struct.unpack("<5I", b[:20])
        print(f"blk{i}: off={hex(off)} raw={hex(raw)} sig={hex(sig)} tot={hex(tot)}")
