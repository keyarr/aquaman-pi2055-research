#!/usr/bin/env python3
"""round28: static summarizer for the vendor aml_encrypt_gxl binary.

For each named function, extracts:
  - resolved call targets (via nm symbol map)
  - rip-relative data references resolved to printable strings / immediates
  - notable constants (sizes, magic values) loaded into registers

Offline only: reads the binary and prints a per-function summary.
Usage: tools/round28_vendor_summ.py [func_name ...]
"""
import re
import subprocess
import sys

BIN = '.src/u-boot-khadas/fip/gxl/aml_encrypt_gxl'


def load_sections():
    out = subprocess.run(['readelf', '-S', '-W', BIN],
                         capture_output=True, text=True).stdout
    secs = []
    for line in out.splitlines():
        ls = line.split()
        if len(ls) > 6 and ls[0].startswith('['):
            try:
                secs.append((ls[2], int(ls[3], 16), int(ls[4], 16),
                             int(ls[5], 16)))
            except ValueError:
                pass
    return secs


def load_syms():
    syms = []
    out = subprocess.run(['nm', '-S', BIN], capture_output=True,
                         text=True).stdout
    for line in out.splitlines():
        p = line.split()
        if len(p) == 4 and p[2] in 'tT':
            syms.append((int(p[0], 16), int(p[1], 16), p[3]))
    syms.sort()
    return syms


def read_at(secs, va, n):
    for _name, addr, off, sz in secs:
        if addr <= va < addr + sz and addr:
            with open(BIN, 'rb') as f:
                f.seek(off + (va - addr))
                return f.read(min(n, addr + sz - va))
    return b''


def cstr_at(secs, va, maxlen=80):
    b = read_at(secs, va, maxlen)
    if not b:
        return None
    b = b.split(b'\x00')[0]
    if len(b) >= 4 and all(32 <= c < 127 or c in (9, 10) for c in b):
        return b.decode('ascii')
    return None


def sym_of(syms, a):
    for addr, sz, n in syms:
        if addr <= a < addr + sz:
            return f"{n}+0x{a-addr:x}"
    return None


def summarize_func(secs, syms, lines, start, end, name):
    calls, strs, imms = {}, {}, {}
    prev = ''
    for line in lines:
        m = re.match(r'\s+([0-9a-f]+):\t(.*)', line)
        if not m:
            continue
        addr = int(m.group(1), 16)
        if not (start <= addr < end):
            continue
        ins = m.group(2)
        cm = re.search(r'call\s+([0-9a-f]+) <([^>]*)>', ins)
        if cm:
            tgt = int(cm.group(1), 16)
            calls[sym_of(syms, tgt) or cm.group(2)] = \
                calls.get(sym_of(syms, tgt) or cm.group(2), 0) + 1
        rm = re.search(r'# ([0-9a-f]+) <', ins)
        if rm:
            va = int(rm.group(1), 16)
            s = cstr_at(secs, va)
            if s and len(s) >= 3:
                strs.setdefault(s, hex(va))
        im = re.findall(r'\$0x([0-9a-f]{2,8})\b', ins)
        for v in im:
            iv = int(v, 16)
            if iv >= 0x10 and (iv & 0xfff) == 0 or iv in (
                    0x200, 0x100, 0x30, 0x60, 0x10, 0x20, 0x50, 0x400,
                    0x1000, 0x2000, 0x4000, 0x8000, 0x10000):
                imms[hex(iv)] = imms.get(hex(iv), 0) + 1
        prev = ins
    print(f"\n=== {name} [{hex(start)}..{hex(end)}) ===")
    print(" calls:")
    for k, v in sorted(calls.items(), key=lambda x: -x[1]):
        print(f"   {v:3d}  {k}")
    if strs:
        print(" strings:")
        for k, v in sorted(strs.items(), key=lambda x: x[1]):
            print(f"   @{v}  {k!r}")
    if imms:
        print(" constants:", ', '.join(sorted(imms, key=imms.get,
                                            reverse=True)[:12]))


def main():
    funcs = sys.argv[1:]
    secs = load_sections()
    syms = load_syms()
    dump = subprocess.run(['objdump', '-d', BIN], capture_output=True,
                          text=True).stdout.splitlines()
    for addr, sz, name in syms:
        if funcs and name not in funcs:
            continue
        if sz == 0 or sz > 0x8000:
            continue
        summarize_func(secs, syms, dump, addr, addr + sz, name)


if __name__ == '__main__':
    main()
