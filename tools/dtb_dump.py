#!/usr/bin/env python3
"""dtb_dump.py - dump a flattened device tree as text, straight from the blob.

dtc is fine but it re-formats, drops the padding and reorders nothing, which is
exactly what you do not want when the blob is the only copy of the evidence.
This walks the struct block and prints every property of every node with its
offset in the strings block, so a value in the report can be traced back to a
byte range of artifacts/aquaman.dtb.

  tools/dtb_dump.py artifacts/aquaman.dtb
  tools/dtb_dump.py artifacts/aquaman.dtb --path /reserved-memory
"""
import struct
import sys

FDT_BEGIN_NODE, FDT_END_NODE, FDT_PROP, FDT_NOP, FDT_END = 1, 2, 3, 4, 9


def parse(blob):
    (magic, tot, off_struct, off_strings, off_rsv, ver, lcv, cpu,
     size_strings, size_struct) = struct.unpack(">10I", blob[:40])
    if magic != 0xD00DFEED:
        raise SystemExit("bad magic 0x%08x" % magic)
    st = blob[off_struct:off_struct + size_struct]
    stx = blob[off_strings:off_strings + size_strings]

    def name_at(o):
        return stx[o:stx.index(b"\0", o)].decode("ascii")

    nodes = []
    stack = []
    p = 0
    while p < len(st):
        tok = struct.unpack(">I", st[p:p + 4])[0]
        p += 4
        if tok == FDT_BEGIN_NODE:
            e = st.index(b"\0", p)
            stack.append(st[p:e].decode("ascii"))
            p = (e + 4) & ~3
        elif tok == FDT_END_NODE:
            stack.pop()
        elif tok == FDT_PROP:
            ln, no = struct.unpack(">II", st[p:p + 8])
            p += 8
            val = st[p:p + ln]
            p = (p + ln + 3) & ~3
            path = "/" + "/".join(x for x in stack if x)
            nodes.append((path, name_at(no), no, val))
        elif tok == FDT_NOP:
            continue
        elif tok == FDT_END:
            break
        else:
            raise SystemExit("bad token %d at struct offset 0x%x" % (tok, p - 4))
    return dict(magic=magic, totalsize=tot, off_dt_struct=off_struct,
                off_dt_strings=off_strings, off_mem_rsvmap=off_rsv,
                version=ver, last_comp_version=lcv, boot_cpuid_phys=cpu,
                size_dt_strings=size_strings, size_dt_struct=size_struct), nodes


def value(val):
    """Print a property the way the blob holds it, never guessing."""
    if len(val) == 0:
        return "(present, zero length)"
    if val[-1:] != b"\0" or not all(32 <= c < 127 for c in val[:-1] if c):
        pass
    else:
        parts = val.split(b"\0")[:-1]
        if all(parts):
            return ", ".join('"%s"' % p.decode("ascii") for p in parts)
    if len(val) % 4 == 0 and len(val) <= 256:
        return "<" + " ".join("0x%x" % x for x in struct.unpack(">%dI" % (len(val) // 4), val)) + ">"
    return "[%d bytes: %s...]" % (len(val), val[:16].hex(" "))


def main():
    path = sys.argv[1]
    want = None
    if "--path" in sys.argv:
        want = sys.argv[sys.argv.index("--path") + 1]

    blob = open(path, "rb").read()
    hdr, nodes = parse(blob)

    if not want:
        for k, v in hdr.items():
            print("// %-18s 0x%08x  (%d)" % (k, v, v))
        print()

    cur = None
    for npath, pname, noff, val in nodes:
        if want and not (npath == want or npath.startswith(want.rstrip("/") + "/")):
            continue
        if npath != cur:
            cur = npath
            print(npath)
        print("    %-30s str@0x%-5x %s" % (pname, noff, value(val)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
