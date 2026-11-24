#!/usr/bin/env python3
"""Offline generator/validator for the EL3 SMC matrix diagnostic stubs.

Builds the AArch64 stub used by /tmp/diag_smc.py, extended to store
x0..x3 in the MREAD-visible scratch at 0x37800800. No device access: the
generate command only prints encodings and disassembles them for checking.
The run command is the same item-1 harness (optimus + false/true oracle),
adapted to one matrix row at a time; it restores handler and scratch in
a finally block.

Usage:
  python3 tools/diag_smc_matrix.py generate
  python3 tools/diag_smc_matrix.py run <row>       # needs USB stage 16
"""
import struct
import sys

WRAPPER = 0x37E19EA8          # BL33 AML_DATA_PROCESS wrapper (0x820000ff)
SMC_STUB = 0x37E8BBA0         # BL33 bare smc #0; ret (storage 0x60..0x65)
SCRATCH = 0x37800000
RESULT = 0x37800800
HANDLER = 0x37F616D0          # "false" cmd_tbl entry (item 1 injection point)
ORIG_HANDLER = 0x37E36764
ZEROS40 = b"\0" * 0x40

# (tag, wrapper, cmd/x0, buf/x1, len/x2, opt/x3, expected)
ROWS = [
    ("ff40-ctrl-ns",   WRAPPER, 0x40, 0x01080000, 0x00100000, 7, "OK plaintext at buf"),
    ("ff40-share-ns",  WRAPPER, 0x40, 0x05000000, 0x00010000, 7, "OK / trashes IN staging"),
    ("ff40-bl31-win",  WRAPPER, 0x40, 0x05100000, 0x00010000, 7, "OK raw EL3 write or reset"),
    ("ff40-bl32-slot", WRAPPER, 0x40, 0x05300000, 0x00010000, 7, "OK raw EL3 write or reset"),
    ("ff40-sram",      WRAPPER, 0x40, 0xD9013F00, 0x00000100, 7, "OK or reset"),
    ("ff80-ctrl-ns",   WRAPPER, 0x80, 0x01080000, 0x00010000, 0, "OK / status"),
    ("ff20-ctrl-ns",   WRAPPER, 0x20, 0x01080000, 0x00000200, 0, "OK / status"),
    ("ff14-ctrl-ns",   WRAPPER, 0x14, 0x01080000, 0x00000000, 0, "OK / status"),
    ("ff10-ctrl-ns",   WRAPPER, 0x10, 0x01080000, 0x00000000, 7, "OK / status"),
    ("ff12-ctrl-ns",   WRAPPER, 0x12, 0x01080000, 0x00000000, 0, "OK / status"),
    # Storage 0x60..0x65 take NO address in registers: x1/x2/x3 below are
    # just residue. The staging bases live in BL33 globals 0x37fbde60/58;
    # redirection is a separate pre-step, documented in 03-test-matrix.md.
    ("storage61-ctrl",  SMC_STUB, 0x82000061, 0, 0, 0, "OK C2 blob at 0x05040000"),
    ("storage62-ctrl",  SMC_STUB, 0x82000062, 0, 0, 0, "OK status only (C1 must exist)"),
]


def movz(rd, imm16, hw=0):
    return 0xD2800000 | (hw << 21) | (imm16 << 5) | rd


def movk(rd, imm16, hw=0):
    return 0xF2800000 | (hw << 21) | (imm16 << 5) | rd


def build_reg(rd, value):
    """Return instructions setting x{rd} to a 64-bit value.

    MOVZ at the first nonzero half, then MOVK for the remaining halves.
    Zero value is MOVZ rd,#0.
    """
    out = []
    halves = [(value >> (16 * i)) & 0xFFFF for i in range(4)]
    nz = [i for i, h in enumerate(halves) if h]
    if not nz:
        return [movz(rd, 0)]
    out.append(movz(rd, halves[nz[0]], nz[0]))
    for i in nz[1:]:
        out.append(movk(rd, halves[i], i))
    return out


def bl(from_addr, to_addr):
    off = to_addr - from_addr
    assert off % 4 == 0 and -0x4000000 <= off < 0x4000000
    return 0x94000000 | ((off // 4) & 0x03FFFFFF)


def stub(cmd, buf, length, opt, target=WRAPPER, result=RESULT):
    """Stub layout (10 insns / 40 bytes, fits SCRATCH 0x40):

        mov x0,#cmd ; mov x1,#buf ; mov x2,#len ; mov x3,#opt
        bl  <wrapper or bare-smc stub>
        mov x4,#result_page ; movk x4,#result_off
        stp x0,x1,[x4] ; stp x2,x3,[x4,#0x10] ; ret
    """
    words = []
    for rd, val in ((0, cmd), (1, buf), (2, length), (3, opt)):
        words += build_reg(rd, val)
    # BL is the 5th..Nth word depending on how many MOVZ/MOVK were needed.
    bl_pos = len(words)
    words.append(bl(0x37800000 + 4 * bl_pos, target))
    # x4 = result address, built as MOVZ + MOVK (page + offset)
    lo = result & 0xFFFF
    hi = (result >> 16) & 0xFFFF
    words.append(movz(4, lo))
    words.append(movk(4, hi, 1))
    words.append(0xA9000480)          # stp x0,x1,[x4]        (verified below)
    words.append(0xA9010C82)          # stp x2,x3,[x4,#0x10]  (verified below)
    words.append(0xD65F03C0)          # ret
    b = b"".join(struct.pack("<I", w) for w in words)
    assert len(b) <= 0x40, len(b)
    return b


def show(b):
    try:
        from capstone import Cs, CS_ARCH_ARM64, CS_MODE_LITTLE_ENDIAN
    except ImportError:
        return b.hex(" ")
    md = Cs(CS_ARCH_ARM64, CS_MODE_LITTLE_ENDIAN)
    lines = []
    for i in md.disasm(b, SCRATCH):
        lines.append("0x%08x: %-8s %s" % (i.address, i.mnemonic, i.op_str))
    return "\n".join(lines)


def generate():
    for tag, wrapper, cmd, buf, length, opt, expected in ROWS:
        b = stub(cmd, buf, length, opt, wrapper)
        print("=== %s  x0=%#x x1=%#x x2=%#x x3=%#x  -> %s ===" %
              (tag, cmd, buf, length, opt, expected))
        print("hex: " + b.hex(" "))
        print(show(b))
        # sanity: round-trip the first qword at RESULT after execution
        print("size %d bytes, result 0x%x..0x%x\n" %
              (len(b), RESULT, RESULT + 0x20))


def mread(dev, a, n):
    sys.path.insert(0, "tools")
    import optimus
    return bytes(optimus.mread_mem(dev, a, n)[0])


def fill64(dev, addr, val):
    sys.path.insert(0, "tools")
    import optimus
    dev.ctrl_transfer(optimus.RT_OUT, 0x03, 0, 0,
                      struct.pack("<II", addr, val), 5000)


def poke(dev, addr, data):
    sys.path.insert(0, "tools")
    import optimus
    for i in range(0, len(data), 8):
        dev.ctrl_transfer(optimus.RT_OUT, 0x01, ((addr + i) >> 16) & 0xFFFF,
                          (addr + i) & 0xFFFF, data[i:i + 8], 5000)


def bulk(dev, cmd, timeout=15000):
    sys.path.insert(0, "tools")
    import optimus
    return optimus.bulkcmd(dev, cmd, timeout=timeout).split(b"\0")[0]


def run(tag):
    row = next((r for r in ROWS if r[0] == tag), None)
    if row is None:
        sys.exit("unknown row %s" % tag)
    _, wrapper, cmd, buf, length, opt, expected = row
    sys.path.insert(0, "tools")
    import optimus
    dev = optimus.find()
    if optimus.identify(dev) != 0:
        sys.exit("ABORT: not stage 16")
    b = stub(cmd, buf, length, opt, wrapper)
    try:
        poke(dev, SCRATCH, b)
        poke(dev, RESULT, b"\0" * 0x20)
        fill64(dev, HANDLER, SCRATCH)
        print("dcache flush -> %r" % (bulk(dev, "dcache flush"),), flush=True)
        print("trigger false -> %r" % (bulk(dev, "false", timeout=30000),),
              flush=True)
        print("dcache flush pos -> %r" % (bulk(dev, "dcache flush"),),
              flush=True)
        r = mread(dev, RESULT, 0x20)
        vals = struct.unpack("<4Q", r)
        print("row %s: expected %s" % (tag, expected), flush=True)
        print("x0..x3 = %s" % " ".join("%#x" % v for v in vals), flush=True)
        if buf < 0x05400000:
            print("buf[0:0x20] = %s" % mread(dev, buf, 0x20).hex(" "),
                  flush=True)
    finally:
        fill64(dev, HANDLER, ORIG_HANDLER)
        poke(dev, SCRATCH, ZEROS40)
        poke(dev, RESULT, b"\0" * 0x20)
        print("restore: handler=%s oracle=%r/%r" % (
            mread(dev, HANDLER, 8).hex(" "),
            bulk(dev, "false"), bulk(dev, "true")), flush=True)


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    if sys.argv[1] == "generate":
        generate()
    elif sys.argv[1] == "run":
        run(sys.argv[2])
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
