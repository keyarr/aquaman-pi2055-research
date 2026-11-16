#!/usr/bin/env python3
"""bootm_env_closure.py - can the tested boot path silently rebuild the env?

Rounds 48/49/53/56/58 all ended the same way: a byte-verified htab `bootargs`
went into `bootm`, and the running Android reported the stock string back. The
three candidate explanations were "env got re-imported", "a different FDT was
delivered", "Linux re-derived it". This tool answers the first one offline, and
lists the Hush command lines `bootm` itself runs, which nothing had enumerated.

  python3 tools/bootm_env_closure.py IMAGE.bin R

Method: transitive `bl` closure from a start function, reusing bl33_audit's
function census so attribution matches the rest of the repo. `blr` is counted
but not followed, and the OS dispatch into the FDT fixup stage is an indirect
table edge, so "not reachable by bl" is a scoped negative, not a proof.
"""
import sys
from collections import deque

sys.path.insert(0, __file__.rsplit("/", 1)[0])
import bl33_audit as B

ENV_REBUILD = {
    0x37e58b24: "set_default_env  himport_r(defenv 0x37eb65a0, len 0x1785)",
    0x37e58c10: "do_env_import     himport_r(serialised blob)",
    0x37e581a0: "himport site 3    inside the env_relocate region",
    0x37e2769c: "env_import        storage-backed",
    0x37e58d94: "env_relocate",
    0x37e58f10: "env api table entry",
    0x37e581fc: "do_env_setenv     env -s -a/-f",
    0x37e58294: "env_set           setenv (MUTATES the htab)",
    0x37e58920: "env_get           READS the htab",
}

ENV_WRITERS = (0x37e58b24, 0x37e58c10, 0x37e581a0)

SCRIPT_RUNNER = 0x37e5e968  # parse_stream: what `run` and the C call sites use
STARTS = {0x37e24c00: "bootm", 0x37e356d0: "imgread"}


def main():
    path, base = sys.argv[1], int(sys.argv[2], 16)
    img = B.Img(path, base)
    edges = {}
    for ins in img.insns:
        if ins.mnemonic == "bl" and ins.op_str.startswith("#0x"):
            edges.setdefault(img.func_of(ins.address), set()).add(int(ins.op_str[1:], 16))

    def closure(start):
        seen = {img.func_of(start)}
        q = deque(seen)
        while q:
            for t in edges.get(q.popleft(), ()):
                if t not in seen:
                    seen.add(t)
                    q.append(t)
        return seen

    def cstr(addr):
        off = addr - base
        end = img.data.find(b"\x00", off)
        return img.data[off:end].decode("latin1")

    for start, name in STARTS.items():
        c = closure(start)
        indirect = sum(1 for i in img.insns
                       if i.mnemonic == "blr" and img.func_of(i.address) in c)
        print("=== %s (%#x): bl-closure %d functions, %d blr sites ===" %
              (name, start, len(c), indirect))
        for addr in sorted(ENV_REBUILD):
            print("  [%s] %#-12x %s" % ("IN " if addr in c else "out", addr, ENV_REBUILD[addr]))
        writers_in = [a for a in ENV_WRITERS if a in c]
        print("  env rebuild sites reachable: %s" %
              (", ".join(hex(a) for a in writers_in) if writers_in else "NONE"))
        print()

    print("=== Hush command lines reached by bootm itself (parse_stream calls) ===")
    c = closure(0x37e24c00)
    by_addr = {i.address: i for i in img.insns}
    for ins in img.insns:
        if ins.mnemonic != "bl" or ins.op_str != "#%#x" % SCRIPT_RUNNER:
            continue
        if img.func_of(ins.address) not in c:
            continue
        # x0 is either a rodata literal (adrp page + add imm just above) or a
        # stack buffer that snprintf() just filled. The window yields a superset
        # of literals, tagged with the register each landed in, so the caller
        # picks the argument rather than trusting the list blindly.
        lits = []
        for k in range(1, 9):
            prev = by_addr.get(ins.address - 4 * k)
            page = by_addr.get(ins.address - 4 * (k + 1))
            if prev is None or page is None:
                continue
            if prev.mnemonic != "add":
                continue
            ops = prev.op_str.split(", ")
            if len(ops) != 3 or not ops[2].startswith("#"):
                continue
            reg, imm = ops[1], ops[2][1:]
            # the adrp that set this add's base register may be several
            # instructions further back, not necessarily the previous one
            for j in range(k + 1, k + 9):
                page = by_addr.get(ins.address - 4 * j)
                if page is None or page.mnemonic != "adrp":
                    continue
                pops = page.op_str.split(", ")
                if len(pops) != 2 or pops[0].strip() != reg or not pops[1].startswith("#"):
                    continue
                lits.append("%s=%r" % (reg, cstr(int(pops[1][1:], 16) + int(imm, 16))))
                break
        print("  %#x  %s" % (ins.address, "; ".join(lits) if lits else
                              "<stack buffer from snprintf>"))


if __name__ == "__main__":
    main()