#!/usr/bin/env python3
"""Rebuild a partition image from a .new.dat + .transfer.list pair (OTA style).

The .dat holds only the non-zero blocks back to back; the transfer list says
where each run lands. These dumps use comma-glued args and express every run
as boundary pairs, so `new 2,1782,2806` is blocks [1782,2806) and
`new 4,0,69,827,1782` is [0,69) + [827,1782). Verified: the runs add up to
exactly the .dat size, byte for byte.

usage: sdat2img.py <part>.transfer.list <part>.new.dat <out.img>
"""
import re
import sys

BLOCK = 4096


def parse(path):
    with open(path) as f:
        lines = f.read().splitlines()
    version, total_blocks = int(lines[0]), int(lines[1])
    runs = []
    for line in lines[4:]:
        line = line.strip()
        if not line:
            continue
        kind, rest = line.split(None, 1)
        args = [int(x) for x in re.split(r"[,\s]+", rest) if x][1:]
        if kind == "zero" or kind == "erase" or kind == "all":
            continue
        if kind != "new":
            raise SystemExit("unhandled op %r" % kind)
        if len(args) % 2:
            raise SystemExit("odd block list, not boundary pairs: %r" % line)
        for i in range(0, len(args), 2):
            start, end = args[i], args[i + 1]
            if end < start:
                raise SystemExit("inverted run %r" % line)
            runs.append((start, end - start))
    return version, total_blocks, runs


def main():
    if len(sys.argv) != 4:
        raise SystemExit(__doc__)
    tlist, dat, out = sys.argv[1:4]
    version, total_blocks, runs = parse(tlist)
    written = 0
    with open(dat, "rb") as src, open(out, "wb") as dst:
        dst.truncate(total_blocks * BLOCK)
        for start, count in runs:
            buf = src.read(count * BLOCK)
            if len(buf) != count * BLOCK:
                raise SystemExit(
                    "%s exhausted after %d/%d blocks (run %d+%d)"
                    % (dat, written, sum(c for _, c in runs), start, count)
                )
            dst.seek(start * BLOCK)
            dst.write(buf)
            written += count
    print(
        "sdat2img: %s -> %s (%d runs, %d/%d blocks, %d bytes total)"
        % (dat, out, len(runs), written, total_blocks, total_blocks * BLOCK)
    )


if __name__ == "__main__":
    main()
