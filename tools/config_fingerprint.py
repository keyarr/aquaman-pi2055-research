#!/usr/bin/env python3
"""Fingerprint two kernel .config/defconfig files. stdlib only."""
import re
import sys

RE_OFF = re.compile(r"^#\s+(CONFIG_\S+)\s+is not set\s*$")
RE_ON = re.compile(r"^(CONFIG_\S+?)=(.*)\s*$")


def parse(path):
    d = {}
    with open(path, errors="replace") as f:
        for raw in f:
            line = raw.strip()
            if not line:
                continue
            m = RE_OFF.match(line)
            if m:
                d[m.group(1)] = "n"
                continue
            if line.startswith("#"):
                continue
            m = RE_ON.match(line)
            if m:
                d[m.group(1)] = m.group(2).strip()
    return d


def compare(a, b):
    keys = set(a) | set(b)
    only_a = sorted(k for k in keys if k not in b)
    only_b = sorted(k for k in keys if k not in a)
    differ = sorted(k for k in keys if k in a and k in b and a[k] != b[k])
    match = len(keys) - len(only_a) - len(only_b) - len(differ)
    pct = 100.0 * match / len(keys) if keys else 100.0
    return keys, match, pct, only_a, only_b, differ


def prefix(k):
    p = k.split("_")
    return p[1] if len(p) > 1 else k


def grouped(keys, top):
    g = {}
    for k in keys:
        g.setdefault(prefix(k), []).append(k)
    out = []
    for grp in sorted(g, key=lambda x: (-len(g[x]), x)):
        items = sorted(g[grp])
        out.append("  %s (%d): %s" % (grp, len(items), ", ".join(items[:top])))
        if len(items) > top:
            out[-1] += " ... +%d more" % (len(items) - top)
    return out


def report(ta, ca, cb, na, nb, top):
    keys, match, pct, oa, ob, df = compare(ca, cb)
    L = []
    L.append("A: %s (%d opts)" % (na, len(ca)))
    L.append("B: %s (%d opts)" % (nb, len(cb)))
    L.append("union=%d match=%d (%.2f%%) differ=%d only-A=%d only-B=%d"
             % (len(keys), match, pct, len(df), len(oa), len(ob)))
    L.append("--- only in A [%d] ---" % len(oa))
    L += grouped(oa, top)
    L.append("--- only in B [%d] ---" % len(ob))
    L += grouped(ob, top)
    L.append("--- value differs [%d] ---" % len(df))
    gd = {}
    for k in df:
        gd.setdefault(prefix(k), []).append("%s (A=%s B=%s)" % (k, ca[k], cb[k]))
    for grp in sorted(gd, key=lambda x: (-len(gd[x]), x)):
        items = sorted(gd[grp])[:top]
        s = "  %s (%d): %s" % (grp, len(gd[grp]), "; ".join(items))
        if len(gd[grp]) > top:
            s += " ... +%d more" % (len(gd[grp]) - top)
        L.append(s)
    return "\n".join(L), pct


def main(argv):
    top = 15
    if "--top" in argv:
        i = argv.index("--top")
        top = int(argv[i + 1])
        argv = argv[:i] + argv[i + 2:]
    if len(argv) >= 3 and argv[1] == "--rank":
        target = argv[2]
        ta = parse(target)
        rows = []
        for c in argv[3:]:
            cb = parse(c)
            _, _, pct, _, _, _ = compare(ta, cb)
            rows.append((pct, c, len(cb)))
        rows.sort(reverse=True)
        for pct, c, n in rows:
            print("%.2f%%  %s (%d opts, union with target)" % (pct, c, n))
        return
    if len(argv) != 3:
        sys.exit("usage: config_fingerprint.py <a> <b> [--top N] | --rank <target> <cand...>")
    ca, cb = parse(argv[1]), parse(argv[2])
    out, _ = report(argv[1], ca, cb, argv[1], argv[2], top)
    print(out)


if __name__ == "__main__":
    main(sys.argv)
