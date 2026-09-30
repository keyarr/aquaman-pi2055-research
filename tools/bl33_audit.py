#!/usr/bin/env python3
"""bl33_audit.py - round 14: the BL33 -> BL31 interface, offline and static.

The brief for round 14 is "enumerate every privilege boundary the host can
reach from BL33, not just aml_sec_boot_check". This is the tool that answers it
from the persisted image (tools/bl33_persist.py), with no device involved:

  smc      every `smc #0` in the image, its containing function, and what each
           of x0..x4 actually holds at the site (forward constant propagation
           over the preceding 32 instructions, not just "a movz/movk pair")
  callers  BL callers of a function, attributed to their containing function
  refs     every code site that materialises an address (adrp+add / adrp+ldr)
           or BLs into it -- this is how a string finds its handler
  cmds     .u_boot_list cmd_tbl slots: command name -> handler address
  fbtab    the fastboot dispatch table (16-byte {char *cmd; void (*cb);} slots)
  funcs    the function-start census (prologue/ret-separated)

  python3 tools/bl33_audit.py smc     IMAGE.bin R
  python3 tools/bl33_audit.py refs    IMAGE.bin R 0x37edef15
  python3 tools/bl33_audit.py callers IMAGE.bin R 0x37e19ea8
  python3 tools/bl33_audit.py cmds    IMAGE.bin R

"IMAGE.bin R" is the relocated image and its run address (0x37e18000). Every
address this tool prints is an absolute runtime address in the relocated image.
"""
import struct
import sys
from collections import defaultdict

from capstone import Cs, CS_ARCH_ARM64, CS_MODE_LITTLE_ENDIAN

RET = 0xD65F03C0

# arch/arm/include/asm/arch-gxl/bl31_apis.h, the ids the image is expected to use
IDS = {
    0x82000020: "GET_SHARE_MEM_INPUT_BASE", 0x82000021: "GET_SHARE_MEM_OUTPUT_BASE",
    0x82000022: "GET_REBOOT_REASON", 0x82000023: "GET_SHARE_STORAGE_IN_BASE",
    0x82000024: "GET_SHARE_STORAGE_OUT_BASE", 0x82000025: "GET_SHARE_STORAGE_BLOCK_BASE",
    0x82000026: "GET_SHARE_STORAGE_MESSAGE_BASE", 0x82000027: "GET_SHARE_STORAGE_BLOCK_SIZE",
    0x82000028: "SET_STORAGE_INFO",
    0x82000030: "EFUSE_READ", 0x82000031: "EFUSE_WRITE", 0x82000032: "EFUSE_WRITE_PATTERN",
    0x82000033: "EFUSE_USER_MAX", 0x820000f0: "DEBUG_EFUSE_WRITE_PATTERN",
    0x820000f1: "DEBUG_EFUSE_READ_PATTERN",
    0x82000040: "JTAG_ON", 0x82000041: "JTAG_OFF", 0x82000043: "SET_USB_BOOT_FUNC",
    0x82000044: "GET_CHIP_ID",
    0x82000060: "SECURITY_KEY_QUERY", 0x82000061: "SECURITY_KEY_READ",
    0x82000062: "SECURITY_KEY_WRITE", 0x82000063: "SECURITY_KEY_TELL",
    0x82000064: "SECURITY_KEY_VERIFY", 0x82000065: "SECURITY_KEY_STATUS",
    0x82000066: "SECURITY_KEY_NOTIFY", 0x82000067: "SECURITY_KEY_LIST",
    0x82000068: "SECURITY_KEY_REMOVE", 0x82000069: "SECURITY_KEY_NOTIFY_EX",
    0x8200006a: "SECURITY_KEY_SET_ENCTYPE", 0x8200006b: "SECURITY_KEY_GET_ENCTYPE",
    0x8200006c: "SECURITY_KEY_VERSION",
    0x820000ff: "AML_DATA_PROCESS",
    0x00000005: "CALL_TRUSTZONE_HAL_API",
    0x84000008: "PSCI_SYSTEM_OFF", 0x84000009: "PSCI_SYS_REBOOT",
    0x00000000: "SMC32/PSCI (x0 not set: psci_smc? or 0)",
}
AML_TYPES = {0x10: "W_EFUSE_SECURE_BOOT", 0x11: "W_EFUSE_PASSWORD",
             0x12: "W_EFUSE_CUSTOMER_ID", 0x20: "W_EFUSE_AMLOGIC",
             0x40: "IMG_DECRYPT", 0x80: "UPGRADE_CHECK"}
USB_BOOT = {1: "CLEAR_USB_BOOT", 2: "FORCE_USB_BOOT", 3: "RUN_COMD_USB_BOOT",
            4: "PANIC_DUMP_USB_BOOT"}


def load(path):
    return open(path, "rb").read()


def sweep(data, base):
    """linear disassembly, plus the derived function-start set."""
    md = Cs(CS_ARCH_ARM64, CS_MODE_LITTLE_ENDIAN)
    # the image has data interleaved with code: without skipdata the sweep stops
    # at the first non-instruction word
    md.skipdata = True
    md.detail = True
    insns = list(md.disasm(data, base))
    words = struct.unpack_from("<%dI" % (len(data) // 4), data, 0)
    starts = set()
    for i, ins in enumerate(insns):
        if ins.mnemonic == "stp" and ins.op_str.startswith("x29, x30, [sp, #-"):
            starts.add(ins.address)
        if ins.mnemonic == "sub" and ins.op_str.startswith("sp, sp, #") \
                and (i == 0 or insns[i - 1].mnemonic in ("ret", "brk", "b", "nop")):
            starts.add(ins.address)
        # nothing falls through a ret or a brk
        if i and insns[i - 1].mnemonic in ("ret", "brk"):
            starts.add(ins.address)
        # nor into an aligned zero-padded gap
        if i >= 2 and words[i - 1] == 0 and words[i - 2] == 0:
            starts.add(ins.address)
    starts.add(base)
    return insns, words, sorted(starts)


class Img:
    def __init__(self, path, base):
        self.data = load(path)
        self.base = base
        self.insns, self.words, self.starts = sweep(self.data, base)
        self.by_addr = {i.address: i for i in self.insns}
        self.cmd_of = cmd_table(self)

    def func_of(self, addr):
        lo, hi = 0, len(self.starts) - 1
        best = self.starts[0]
        while lo <= hi:
            mid = (lo + hi) // 2
            if self.starts[mid] <= addr:
                best = self.starts[mid]
                lo = mid + 1
            else:
                hi = mid - 1
        return best

    def name_of(self, func):
        return self.cmd_of.get(func, "")

    def callers(self, target):
        return [(i.address, self.func_of(i.address)) for i in self.insns
                if i.mnemonic == "bl" and i.operands
                and i.operands[0].type == 2 and i.operands[0].imm == target]

    def site_str(self, addr, n=6):
        out = []
        for i in range(n, 0, -1):
            ins = self.by_addr.get(addr - i * 4)
            if ins:
                out.append(ins)
        out.append(self.by_addr[addr])
        for k in range(1, n):
            ins = self.by_addr.get(addr + k * 4)
            if ins:
                out.append(ins)
        return out


def cmd_table(img):
    """u-boot .u_boot_list: {name*, maxargs(u32), repeatable(u32), cmd*, usage*, help*}."""
    d, base, out, starts = img.data, img.base, {}, set(img.starts)

    def sptr(v):
        if not base <= v < base + len(d):
            return None
        o = v - base
        e = d.find(b"\0", o, o + 40)
        if e <= o or e - o < 2:
            return None
        if not all(32 <= c < 127 for c in d[o:e]):
            return None
        return d[o:e].decode()

    q = struct.unpack_from("<%dQ" % (len(d) // 8), d, 0)
    for i in range(len(q) - 6):
        nm = sptr(q[i])
        if not nm:
            continue
        # a u-boot command name: short, no spaces
        if len(nm) > 18 or " " in nm:
            continue
        maxargs, repeat = q[i + 1] & 0xFFFFFFFF, (q[i + 1] >> 32) & 0xFFFFFFFF
        if maxargs > 64 or repeat > 4:
            continue
        cmd = q[i + 2]
        if not base <= cmd < base + len(d):
            continue
        # the handler must look like the entry point of a function
        if cmd not in starts:
            continue
        if not (sptr(q[i + 3]) or sptr(q[i + 4])):
            continue
        out[cmd] = nm
    return out


def reach(words, base, site, reg, lo=None, win=64):
    """the set of constant values that can be in `reg` at `site`.

    a forward pass over the preceding instructions with a set-valued register
    file. `movz`/`movk` chains accumulate into one value; any other write unions
    its result into the register's set, so a value selected by a branch before
    the smc shows up as the whole set, not as the last store. this is what
    actually answers "which id goes into x0" for the wrappers that pick the id
    at runtime (`meson_trustzone_efuse` selects 0x30/0x31/0x32).

    None in the set means "not statically determined" (a function argument, a
    memory load, anything the pass cannot follow).
    """
    n = (site - base) // 4
    low = max(0, n - win)
    if lo is not None:
        low = max(low, (lo - base) // 4)
    seen = defaultdict(set)
    acc = {}
    for k in range(low, n):
        x = words[k]
        pc = base + k * 4
        dst = x & 0x1F
        if dst == 31:
            continue
        if (x & 0x7F800000) == 0x52800000 or (x & 0x7F800000) == 0x72800000:
            imm = (x >> 5) & 0xFFFF
            hw = (x >> 21) & 3
            mask = 0xFFFF << (hw * 16)
            if (x & 0x7F800000) == 0x52800000:
                acc[dst] = imm << (hw * 16)
            else:
                acc[dst] = ((acc.get(dst, 0) or 0) & ~mask) | (imm << (hw * 16))
            continue
        # any other instruction: flush whatever was being built
        if dst in acc:
            seen[dst].add(acc.pop(dst))
        v = None
        if (x & 0xFFE0FFE0) == 0xAA0003E0 or (x & 0xFFE0FFE0) == 0x2A0003E0:
            v = seen.get((x >> 16) & 0x1F) or {None}          # mov xD, xS
        elif (x & 0xFFC00000) == 0x91000000:                  # add xD, xS, #imm
            b = seen.get((x >> 5) & 0x1F)
            v = {e if not isinstance(e, int) else e + ((x >> 10) & 0xFFF)
                 for e in b} if b else {None}
        elif (x & 0x9F000000) == 0x90000000:                  # adrp
            imm = (x >> 5) & 0x7FFFF
            if imm & 0x40000:
                imm -= 0x80000
            v = {(pc & ~0xFFF) + (imm << 12)}
        elif (x & 0xFFC00000) in (0xF9400000, 0xB9400000):    # ldr xD, [xS, #imm]
            b = seen.get((x >> 5) & 0x1F)
            v = {e if not isinstance(e, int)
                 else ("mem", e + ((x >> 10) & 0xFFF) * (8 if x >> 30 else 4))
                 for e in b} if b else {None}
        elif x & 0x80000000:
            v = {None}
        elif dst < 31:
            v = {None}
        if v is not None:
            for e in v:
                if len(seen[dst]) < 16:
                    seen[dst].add(e)
    for r, val in acc.items():
        seen[r].add(val)
    out = seen.get(reg)
    return out or {None}


def fmt(v):
    if isinstance(v, tuple):
        return "%s @ 0x%x" % (v[0], v[1])
    return "0x%x" % v if v is not None else "?"


def fmt_set(s, names=None):
    out = []
    for v in sorted(s, key=lambda e: (e is None, e if not isinstance(e, tuple) else 0)):
        if isinstance(v, int) and names and v in names:
            out.append("%s (=%s)" % (fmt(v), names[v]))
        else:
            out.append(fmt(v))
    return "{" + ", ".join(out) + "}"


# the SMC id families this board uses: 0x82xxxxxx (ATF / secure monitor),
# 0x84xxxxxx (PSCI), 0xb20000xx (a second monitor family, see the round-14 report)
def idish(v):
    return isinstance(v, int) and v >> 24 in (0x82, 0x84, 0x85, 0xB2, 0xC2, 0x05, 0xC0)


def argtag(v):
    if isinstance(v, int) and v in AML_TYPES:
        return "  (%s)" % AML_TYPES[v]
    if isinstance(v, int) and v in USB_BOOT:
        return "  (%s)" % USB_BOOT[v]
    return ""


def brief(s, keep=8):
    """readable form: the id-shaped constants first, plus a noise count."""
    ids = sorted(v for v in s if idish(v))
    noise = sorted((v for v in s if not idish(v) and not isinstance(v, tuple)),
                   key=lambda v: (v is None, v if isinstance(v, int) else 0))
    mem = [v for v in s if isinstance(v, tuple)]
    parts = []
    for v in ids[:keep]:
        parts.append("%s (=%s)" % (fmt(v), IDS[v]) if v in IDS else fmt(v))
    if len(ids) > keep:
        parts.append("... %d more ids" % (len(ids) - keep))
    if len(ids) == 1:
        parts[0] += argtag(ids[0])
    if not ids:
        parts.append(", ".join(fmt(v) for v in noise[:4]) if noise else "?")
    elif noise:
        parts.append("...")
    tail = []
    if noise:
        tail.append("%d non-id constant(s)" % len(noise))
    if mem:
        tail.append("%d memory load(s)" % len(mem))
    if not ids and not noise and not mem:
        tail.append("not statically determined")
    return "{%s}%s" % (", ".join(parts), ("   [" + ", ".join(tail) + "]") if tail else "")


def verb_smc(img):
    # `smc #0` exactly: a data word can decode as `smc #0x1234`, and the image
    # has data interleaved, so the immediate has to be checked
    sites = [i for i in img.insns if i.mnemonic == "smc" and i.op_str == "#0"]
    print("smc #0 census over 0x%08x..0x%08x (%d bytes, %d instructions)\n"
          % (img.base, img.base + len(img.data) - 1, len(img.data), len(img.insns)))
    for ins in sites:
        a = ins.address
        f = img.func_of(a)
        # a 2-instruction stub (`smc #0; ret`) follows the previous block's own
        # ret/b, so it is a function in its own right even though nothing
        # "falls into" it: without this the shared stubs get attributed to the
        # block above them and their callers vanish
        prev = img.by_addr.get(a - 4)
        if prev is None or prev.mnemonic in ("ret", "b", "brk"):
            f = a
        print("\nsite 0x%08x   wrapper 0x%08x %s"
              % (a, f, img.name_of(f) or "(no cmd_tbl name)"))
        x0 = reach(img.words, img.base, a, 0, lo=f)
        print("  x0 = %s" % brief(x0))
        for r in (1, 2, 3, 4):
            s = reach(img.words, img.base, a, r, lo=f)
            if s != {None}:
                print("  x%d = %s" % (r, brief(s)))
        cs = img.callers(f)
        if x0 == {None} and cs:
            print("  x0 is a wrapper argument; what each caller passes:")
            for c, cf in cs[:40]:
                v = reach(img.words, img.base, c, 0, lo=cf)
                print("    0x%08x in 0x%08x %-16s x0 = %s"
                      % (c, cf, img.name_of(cf) or "", brief(v)))
        elif cs:
            print("  bl callers of the wrapper: %s"
                  % " ".join("0x%08x" % c for c, _ in cs[:12]))
    print("\n%d opcode-exact `smc #0` site(s)" % len(sites))


def verb_callers(img, targets):
    for t in targets:
        print("\n=== callers of 0x%08x %s" % (t, IDS.get(t, "")))
        cs = img.callers(t)
        groups = defaultdict(list)
        for a, f in cs:
            groups[f].append(a)
        for f in sorted(groups):
            print("  0x%08x %-12s %d call site(s): %s"
                  % (f, img.name_of(f), len(groups[f]),
                     " ".join("0x%08x" % a for a in groups[f])))
        if not cs:
            print("  none (no `bl` reaches this address)")


def verb_refs(img, targets):
    """code sites that materialise an address: adrp+add / adrp+ldr / bl."""
    d = img.data
    for t in targets:
        print("\n=== references to 0x%08x" % t)
        page = t & ~0xFFF
        off = t & 0xFFF
        for ins in img.insns:
            if ins.mnemonic == "bl":
                continue
            a = ins.address
            if ins.mnemonic != "adrp":
                continue
            if ins.operands[0].type != 1:
                continue
            rd = ins.operands[0].reg
            if ins.operands[1].type != 2:
                continue
            if (ins.operands[1].imm & ~0xFFF) != page:
                continue
            for k in range(1, 6):
                nx = img.by_addr.get(a + k * 4)
                if not nx:
                    continue
                if nx.mnemonic == "add" and nx.operands[0].type == 1 \
                        and nx.operands[0].reg == rd and nx.operands[-1].type == 2:
                    tot = ins.operands[1].imm + nx.operands[-1].imm
                    if tot == t:
                        print("  0x%08x  %-10s in 0x%08x %-10s"
                              % (a, "adrp+add", img.func_of(a), img.name_of(img.func_of(a))))
                    break
                if nx.mnemonic in ("ldr", "ldrb", "ldrh", "ldrsw") and nx.operands[-1].type == 3:
                    m = nx.operands[-1]
                    if m.mem.base == rd and m.mem.disp + ((ins.operands[1].imm) & 0xFFF) == off \
                            and (ins.operands[1].imm & ~0xFFF) == page:
                        print("  0x%08x  %-10s in 0x%08x %-10s  (literal load)"
                              % (a, "adrp+ldr", img.func_of(a), img.name_of(img.func_of(a))))
                    break
        for addr, f in img.callers(t):
            print("  0x%08x  %-10s in 0x%08x %-10s" % (addr, "bl", f, img.name_of(f)))


def verb_cmds(img):
    print("cmd_tbl slots (.u_boot_list), %d found\n" % len(img.cmd_of))
    for f in sorted(img.cmd_of, key=lambda a: img.cmd_of[a]):
        nm = img.cmd_of[f]
        d = img.data
        o = f - img.base
        if f + 0x10 <= img.base + len(d):
            usage = struct.unpack_from("<Q", d, o + 8)[0]
            us = ""
            if img.base <= usage < img.base + len(d):
                e = d.find(b"\0", usage - img.base)
                us = d[usage - img.base:e][:48].decode(errors="replace")
            print("  0x%08x  %-14s %s" % (f, nm, us))


def verb_fbtab(img, addr):
    """fastboot dispatch table: {char *cmd; void (*cb)} 16-byte slots."""
    d, base = img.data, img.base
    print("fastboot-shaped dispatch table at 0x%08x\n" % addr)
    for i in range(32):
        o = addr - base + i * 16
        if o + 16 > len(d):
            break
        s, cb = struct.unpack_from("<QQ", d, o)
        if not (base <= s < base + len(d)):
            break
        e = d.find(b"\0", s - base, s - base + 40)
        if e < 0:
            break
        nm = d[s - base:e].decode(errors="replace")
        tag = "code" if base <= cb < base + len(d) else "OUTSIDE"
        print("  +0x%03x  0x%08x %-20r -> 0x%08x %-8s %s"
              % (i * 16, s, nm, cb, tag, img.name_of(cb) if tag == "code" else ""))


def verb_table(img, addr):
    """a {char *cmd; void (*cb)} table, walked while the entries stay valid."""
    d, base = img.data, img.base
    print("16-byte {cmd, cb} table at 0x%08x\n" % addr)
    for i in range(40):
        o = addr - base + i * 16
        if o + 16 > len(d):
            break
        s, cb = struct.unpack_from("<QQ", d, o)
        if not (base <= s < base + len(d)) or not (base <= cb < base + len(d)):
            print("  +0x%03x  (0x%016x, 0x%016x)  -- table ends" % (i * 16, s, cb))
            break
        e = d.find(b"\0", s - base, s - base + 40)
        nm = d[s - base:e].decode(errors="replace") if e > s - base else ""
        print("  slot 0x%08x  cmd=%-16r cb=0x%08x %s"
              % (base + o, nm, cb, img.name_of(cb) or ""))


def verb_ptrs(img, targets, span=0x80):
    """every 8-byte slot holding one of these addresses (pointer tables)."""
    d, base = img.data, img.base
    for t in targets:
        print("\n=== pointers to 0x%08x" % t)
        for i in range(0, len(d) - 8, 8):
            if struct.unpack_from("<Q", d, i)[0] != t:
                continue
            lo = max(0, i - span)
            hi = min(len(d), i + span)
            row = []
            for j in range(lo, hi, 8):
                v = struct.unpack_from("<Q", d, j)[0]
                mark = "<<<" if j == i else ""
                tag = ""
                if base <= v < base + len(d):
                    o = v - base
                    e = d.find(b"\0", o, o + 40)
                    if e > o and all(32 <= c < 127 for c in d[o:e]):
                        tag = "%r" % d[o:e][:28]
                    elif v in img.cmd_of or v in img.starts:
                        tag = "func %s" % (img.name_of(v) or "?")
                print("  0x%08x +0x%03x 0x%016x  %-8s %s %s"
                      % (base + j, j - lo, v, "in-image" if base <= v < base + len(d)
                         else "outside", tag, mark))


def verb_fstrings(img, funcs):
    """the rodata a function points at -- how an unnamed handler gets named."""
    d, base = img.data, img.base
    for f in funcs:
        stop = img.base + len(d)
        for s in img.starts:
            if s > f:
                stop = s
                break
        print("\n=== function 0x%08x (%s) 0x%08x..0x%08x"
              % (f, img.name_of(f) or "?", f, stop - 1))
        seen = []
        for ins in img.insns:
            if not (f <= ins.address < stop) or ins.mnemonic != "adrp":
                continue
            rd = ins.operands[0].reg
            for k in range(1, 5):
                nx = img.by_addr.get(ins.address + k * 4)
                if not nx or nx.mnemonic != "add" or nx.operands[0].reg != rd:
                    continue
                a = ins.operands[1].imm + nx.operands[-1].imm
                if base <= a < base + len(d):
                    e = d.find(b"\0", a - base, a - base + 96)
                    if e > a - base and all(32 <= c < 127 for c in d[a - base:e]):
                        t = d[a - base:e].decode()
                        if len(t) >= 5 and t not in seen:
                            seen.append(t)
                            print("    0x%08x %r" % (a, t[:88]))
                break
        if not seen:
            print("    (no string references)")


def verb_strrefs(img, needle):
    """find a string, then the code that points at it."""
    d, base = img.data, img.base
    i = 0
    while True:
        i = d.find(needle, i)
        if i < 0:
            break
        addr = base + i
        e = d.find(b"\0", i, i + 80)
        print("%r at 0x%08x: %r" % (needle, addr, d[i:e][:80]))
        verb_refs(img, [addr])
        i += 1


def main():
    if len(sys.argv) < 4:
        sys.exit(__doc__)
    verb, path, base = sys.argv[1], sys.argv[2], int(sys.argv[3], 0)
    img = Img(path, base)
    print("image %s  base 0x%08x  size 0x%x" % (path, base, len(img.data)))
    args = sys.argv[4:]
    ints = [int(a, 0) for a in args] if args and args[0].startswith("0x") else []
    if verb == "smc":
        verb_smc(img)
    elif verb == "callers":
        verb_callers(img, ints)
    elif verb == "refs":
        verb_refs(img, ints)
    elif verb == "cmds":
        verb_cmds(img)
    elif verb == "fstrings":
        verb_fstrings(img, ints)
    elif verb == "ptrs":
        verb_ptrs(img, ints)
    elif verb == "table":
        verb_table(img, ints[0])
    elif verb == "fbtab":
        verb_fbtab(img, ints[0])
    elif verb == "strrefs":
        verb_strrefs(img, args[0].encode())
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
