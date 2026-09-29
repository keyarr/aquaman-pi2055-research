#!/usr/bin/env python3
"""Dump the __versions CRC table of a .ko (needed when the kernel was built
with CONFIG_MODVERSIONS). Also diffs those symbols against a Module.symvers.

usage: ko_versions.py <file.ko>... [--symvers Module.symvers]
"""
import os
import re
import struct
import subprocess
import sys

ENV = dict(os.environ, LC_ALL="C")


def section(path, name):
    out = subprocess.run(["readelf", "-S", "-W", path], capture_output=True,
                         text=True, env=ENV).stdout
    m = re.search(r"\[\s*\d+\]\s+%s\s+PROGBITS\s+\S+\s+(\S+)\s+(\S+)" % re.escape(name), out)
    if not m:
        return None
    off, size = int(m.group(1), 16), int(m.group(2), 16)
    with open(path, "rb") as f:
        f.seek(off)
        return f.read(size)


def _parse_stride(data, stride):
    out = []
    for i in range(0, len(data) - stride + 1, stride):
        rec = data[i:i + stride]
        sym = rec[8:].split(b"\x00")[0]
        if not sym:
            break
        name = sym.decode("ascii", "replace")
        if not name.replace("_", "").replace(".", "").isalnum():
            return None
        out.append((struct.unpack_from("<Q", rec, 0)[0], name))
    return out


def _sniff(data):
    # these builds pad every modversion_info to 64 bytes, not the usual 16,
    # so the stride has to be sniffed instead of assumed. require the stride
    # to divide the section exactly, otherwise a short section parses as one
    # bogus record at the largest stride and the count comes out wrong.
    for stride in (64, 56, 48, 40, 32, 24, 16):
        if len(data) % stride:
            continue
        out = _parse_stride(data, stride)
        if out:
            return out
    return []


def versions(path):
    """[(crc:u64, symbol:str)] in section order, None if no __versions."""
    data = section(path, "__versions")
    if data is None:
        return None
    return _sniff(data)


def main():
    args = sys.argv[1:]
    symvers = None
    if "--symvers" in args:
        i = args.index("--symvers")
        symvers = args[i + 1]
        del args[i:i + 2]
    if not args:
        raise SystemExit(__doc__)

    have = {}
    if symvers:
        with open(symvers) as f:
            for line in f:
                parts = line.split()
                if len(parts) >= 4 and parts[2] == "vmlinux":
                    have[parts[1]] = parts[0]

    for path in args:
        v = versions(path)
        name = os.path.basename(path)
        if v is None:
            print("%-24s no __versions section (module built without MODVERSIONS)" % name)
            continue
        print("%-24s %d versioned imports" % (name, len(v)))
        if not have:
            continue
        missing = [s for _, s in v if s not in have]
        # CRC mismatch is the real gate: MODVERSIONS is on, so a rebuilt
        # kernel that exports the same name with a different CRC still refuses
        mismatch = [s for crc, s in v
                    if s in have and have[s].lower() != "0x%08x" % (crc & 0xffffffff)]
        print("    missing=%d crc-diff=%d of %d  (against %s)"
              % (len(missing), len(mismatch), len(v), os.path.basename(symvers)))
        for s in missing[:15]:
            print("      MISSING   %s" % s)
        for s in mismatch[:15]:
            print("      CRC-DIFF  %s" % s)


if __name__ == "__main__":
    main()
