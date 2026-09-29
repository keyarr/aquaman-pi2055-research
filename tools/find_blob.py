#!/usr/bin/env python3
"""find_blob.py - search for second-stage blob inside bootloader.img.
Usage: python3 find_blob.py
"""
import hashlib
SEC = "boot_unpack/second"
BL = "bootloader.img"
with open(SEC, "rb") as f: sec = f.read()
with open(BL, "rb") as f: bl = f.read()
print(f"second len={len(sec)} sha={hashlib.sha256(sec).hexdigest()[:16]}")
print(f"bootloader len={len(bl)} sha={hashlib.sha256(bl).hexdigest()[:16]}")
for off in [0, 0x1000, 0x5000, 0xA000, 0xE000]:
    chunk = sec[off:off + 32]
    print(f"sec[{hex(off)}] {chunk.hex()[:40]} bl_pos={bl.find(chunk)}")
print("full match:", bl.find(sec))
stripped = sec[:0xEC00]  # without trailing 1024 zeros
print("stripped full match:", bl.find(stripped))
print("first32 match:", bl.find(sec[:32]))
# also check kernel payload / dt
with open("boot_unpack/kernel", "rb") as f: k = f.read(0x60 + 32)
print("kpay32 == dt32:", open("boot_unpack/kernel","rb").read()[0x60:0x60+32].hex() == open("dt.img","rb").read()[:32].hex())
