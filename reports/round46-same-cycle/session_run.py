#!/usr/bin/env python3
"""Single-session Optimus run: baseline oracle, Exp1 redirect, Exp2 env, Exp3 dumps.
No 0x04/0x05, no saveenv/flash/eMMC/reset. Complete bulkcmds only + drain 0x33."""
import struct
import sys
import time

sys.path.insert(0, "tools")
import optimus  # noqa: E402
import usb.core  # noqa: E402

OUT = "/tmp/opencode/exp_session"
TEST_SLOT = 0x37F62180
TEST_ORIG = 0x37E36774
TRUE_H = 0x37E3676C
STORED_BOOTDELAY = 0x37F723D8
CMDTBL = 0x37F60EB0


def drain(dev):
    for _ in range(6):
        try:
            n = optimus.upload_next(dev, timeout=1500)
        except Exception:
            break
        if not n:
            break
        try:
            got = 0
            while got < n:
                c = dev.read(optimus.BULK_IN_EP, min(n - got, 65536), 5000)
                if not c:
                    break
                got += len(c)
        except Exception:
            break


def bulk(dev, cmd, retries=4):
    last = None
    for i in range(retries):
        try:
            r = optimus.bulkcmd(dev, cmd)
            return r.split(b"\0")[0]
        except Exception as e:
            last = e
            time.sleep(1)
            drain(dev)
    raise IOError("bulkcmd %r failed %dx: %r" % (cmd, retries, last))


def read(dev, addr, ln, retries=4):
    last = None
    for i in range(retries):
        try:
            return bytes(optimus.read_mem(dev, addr, ln))
        except Exception as e:
            last = e
            time.sleep(1)
            drain(dev)
    raise IOError("read %s failed: %r" % (hex(addr), last))


def mread(dev, addr, size):
    return optimus.mread_mem(dev, addr, size)[0]


def fill1(dev, addr, val):
    buf = struct.pack("<II", addr, val)
    dev.ctrl_transfer(optimus.RT_OUT, 0x03, 0, 0, buf, 5000)


def poke(dev, addr, data):
    dev.ctrl_transfer(optimus.RT_OUT, 0x01, (addr >> 16) & 0xFFFF,
                      addr & 0xFFFF, data, 5000)


def main():
    dev = optimus.find()
    rc = optimus.identify(dev)
    print("identify rc=%d (0 ok, want stage 16)" % rc, flush=True)
    if rc != 0:
        sys.exit("not stage 16, abort")

    print("\n== baseline oracle ==", flush=True)
    base = {}
    for c in ["false", "true", "test 1 = 2", "test 1 = 1",
              "run foo1234", "env print foo"]:
        r = bulk(dev, c)
        base[c] = r
        print("  %-14r -> %r" % (c, r), flush=True)
    ok = (base["false"].startswith(b"failed:")
          and base["test 1 = 2"].startswith(b"failed:")
          and base["true"].startswith(b"success")
          and base["test 1 = 1"].startswith(b"success"))
    print("baseline sane: %s" % ok, flush=True)
    if not ok:
        sys.exit("baseline insane, abort before any write")

    print("\n== Exp1 SAVE slot test ==", flush=True)
    before = read(dev, TEST_SLOT, 8)
    print("  slot %s = %s" % (hex(TEST_SLOT), before.hex(" ")), flush=True)
    if before != struct.pack("<Q", TEST_ORIG):
        sys.exit("slot not orig (want %x), abort" % TEST_ORIG)

    print("== Exp1 FILL test->true (1 pair, low 4B) ==", flush=True)
    fill1(dev, TEST_SLOT, TRUE_H)
    mid = read(dev, TEST_SLOT, 8)
    print("  mid = %s" % mid.hex(" "), flush=True)
    if mid != struct.pack("<Q", TRUE_H):
        print("  MID MISMATCH, restoring orig", flush=True)
        fill1(dev, TEST_SLOT, TEST_ORIG)
        sys.exit("fill verify failed, restored")

    print("== Exp1 TRIGGER test 1 = 2 ==", flush=True)
    t1 = bulk(dev, "test 1 = 2")
    t2 = bulk(dev, "test 1 = 1")
    print("  test 1 = 2 -> %r (want success)" % t1, flush=True)
    print("  test 1 = 1 -> %r (want success)" % t2, flush=True)
    exp1 = t1.startswith(b"success")
    print("Exp1 redirect observed: %s" % exp1, flush=True)

    print("== Exp1 RESTORE ==", flush=True)
    fill1(dev, TEST_SLOT, TEST_ORIG)
    after = read(dev, TEST_SLOT, 8)
    print("  after = %s" % after.hex(" "), flush=True)
    rt = bulk(dev, "test 1 = 2")
    print("  re-trigger test 1 = 2 -> %r (want failed:)" % rt, flush=True)
    exp1ok = exp1 and after == struct.pack("<Q", TEST_ORIG) \
        and rt.startswith(b"failed:")
    print("Exp1 PASS: %s" % exp1ok, flush=True)
    if not exp1ok:
        sys.exit("Exp1 failed, stop before Exp2")

    print("\n== Exp2 HUNT env (dynamic, this boot) ==", flush=True)
    hunt = mread(dev, 0x33E18000, 0x8000)
    print("  hunt 32k sha short: %d bytes" % len(hunt), flush=True)
    i = hunt.find(b"\x00avb2\x001\x00")
    if i < 0:
        sys.exit("avb2 pattern not found, abort (no poke without addr)")
    AVB2 = 0x33E18000 + i + 1 + len("avb2") + 1
    print("  avb2 val @ %s = %r ctx=%r"
          % (hex(AVB2), hunt[i + 1 + 5:i + 1 + 5 + 4],
             hunt[max(0, i - 20):i + 20]), flush=True)
    live = read(dev, AVB2, 8)
    print("  live 8B @ avb2: %s" % live.hex(" "), flush=True)
    if live[:2] != b"1\x00":
        sys.exit("avb2 value not '1\\0', abort")
    if True:
        import os
        os.makedirs(OUT, exist_ok=True)
        open("%s/hunt_33e18000_32k.bin" % OUT, "wb").write(hunt)

    print("== Exp2 WRITE avb2 1->0 (1B, no trigger) ==", flush=True)
    poke(dev, AVB2, b"0")
    mid2 = read(dev, AVB2, 8)
    print("  mid = %s" % mid2.hex(" "), flush=True)
    exp2w = mid2[:2] == b"0\x00" and mid2[2:] == live[2:]
    print("  neighbor bytes intact: %s" % (mid2[2:] == live[2:]), flush=True)
    if not exp2w:
        print("  MID BAD, restoring", flush=True)
        poke(dev, AVB2, b"1")
        sys.exit("Exp2 mid failed, restored")

    print("== Exp2 RESTORE avb2 0->1 ==", flush=True)
    poke(dev, AVB2, b"1")
    aft2 = read(dev, AVB2, 8)
    print("  after = %s" % aft2.hex(" "), flush=True)
    ot = bulk(dev, "test 1 = 2")
    print("  oracle still alive: test 1 = 2 -> %r" % ot, flush=True)
    exp2ok = aft2 == live and ot.startswith(b"failed:")
    print("Exp2 PASS: %s" % exp2ok, flush=True)
    if not exp2ok:
        sys.exit("Exp2 restore failed")

    print("\n== Exp3 read-only dumps ==", flush=True)
    import os
    os.makedirs(OUT, exist_ok=True)
    tbl = mread(dev, CMDTBL, 0x15C0)
    open("%s/cmdtbl_37f60eb0.bin" % OUT, "wb").write(tbl)
    print("  cmdtbl %d bytes" % len(tbl), flush=True)
    for tag, a, n in [("stored_bootdelay", STORED_BOOTDELAY, 4),
                      ("slot_test", TEST_SLOT, 8),
                      ("slot_false", 0x37F616D0, 8),
                      ("slot_run", 0x37F61E80, 8),
                      ("slot_fdt", 0x37F617F0, 8),
                      ("slot_get_rebootmode", 0x37F61850, 8),
                      ("dtb_header", 0x01000000, 64)]:
        try:
            b = read(dev, a, n)
            open("%s/%s_%08x.bin" % (OUT, tag, a), "wb").write(b)
            print("  %-18s %s = %s" % (tag, hex(a), b.hex(" ")), flush=True)
        except Exception as e:
            print("  %-18s %s READ FAIL %r" % (tag, hex(a), e), flush=True)
    for name in [b"bootdelay", b"bootcmd", b"active_slot", b"boot_part",
                 b"loadaddr", b"upgrade_step", b"reboot_mode"]:
        j = hunt.find(b"\x00" + name + b"\x00")
        if j < 0:
            print("  env %-12s NOTFOUND" % name.decode(), flush=True)
            continue
        va = 0x33E18000 + j + 1 + len(name) + 1
        e = hunt.find(b"\x00", j + 1 + len(name) + 1)
        print("  env %-12s val@%s=%r"
              % (name.decode(), hex(va), hunt[va - 0x33E18000:e][:80]),
              flush=True)

    print("\n== final oracle ==", flush=True)
    for c in ["false", "true", "test 1 = 2", "test 1 = 1"]:
        print("  %-14r -> %r" % (c, bulk(dev, c)), flush=True)
    print("SESSION DONE exp1=%s exp2=%s" % (exp1ok, exp2ok), flush=True)


if __name__ == "__main__":
    main()
