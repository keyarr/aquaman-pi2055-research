#!/usr/bin/env python3
"""round27: BL31 layout / load-origin / boundary helpers (offline, no device).

Every function here re-derives a number that reports/round27-bl31-layout.md
claims, from bytes that are already in the repo:

  ao_decode(cfg3)            -> bl31/bl32 reserved sizes from P_AO_SEC_GP_CFG3
  parse_bl31_img(buf)        -> the 0x12348765 header of a family bl31.img
  parse_bl2_fip_table(buf)   -> the plaintext FIP image table at the tail of
                                family bl2.bin (bl30/bl301/bl31/bl32/bl33
                                load addresses)
  pt_covers(dump, pt_off, lo, hi) -> whether the BL33 page table baked into the
                                round-13 dump maps [lo, hi) (2 MiB sections)

No USB, no device, no writes anywhere.
"""
import struct

AO_BASE = 0xC8100000
AO_SEC_GP_CFG3 = AO_BASE + (0x93 << 2)  # 0xC810024C sizes (hi=bl31, lo=bl32)
AO_SEC_GP_CFG4 = AO_BASE + (0x94 << 2)  # 0xC8100250 bl32 start
AO_SEC_GP_CFG5 = AO_BASE + (0x95 << 2)  # 0xC8100254 bl31 start

BL31_IMG_MAGIC = 0x12348765
BL31_ENTRY_MAGIC = 0x87654321

FIP_IMG_MAGIC = 0xAABBCCDD


def ao_decode(cfg3):
    """cmd_rsvmem.c do_rsvmem_check/dump: CFG3 hi16<<10 = bl31 size,
    lo16<<10 = bl32 size (KiB units)."""
    bl31_size = ((cfg3 & 0xFFFF0000) >> 16) << 10
    bl32_size = (cfg3 & 0x0000FFFF) << 10
    return bl31_size, bl32_size


def parse_bl31_img(buf):
    """Family bl31.img: magic 0x12348765, then (u32 size, u64 fields):
    +0x08 load address, +0x10 rsvmem start, +0x18 rsvmem size,
    +0x20 secure-window start, +0x28 secure-window size.
    gxlimg fip.c: 'BL31 binary store information about load address and
    entry point in the FIP data' (0x50-byte header at offset 0x100)."""
    if len(buf) < 0x30:
        raise ValueError("buffer too small")
    magic, size = struct.unpack_from("<II", buf, 0)
    load, rsv_start, rsv_size = struct.unpack_from("<QQQ", buf, 0x08)
    sec_start, sec_size = struct.unpack_from("<QQ", buf, 0x20)
    return {
        "magic": magic,
        "size": size,
        "load": load,
        "rsv_start": rsv_start,
        "rsv_size": rsv_size,
        "secure_start": sec_start,
        "secure_size": sec_size,
    }


def parse_bl2_fip_table(buf):
    """Tail of family bl2.bin: a record table, stride 0x28, one record per
    boot image:  u64 load_addr; char name[8]; u32 0; u32 next_uuid_w0;
    u64 0; u64 0.  next_uuid_w0 (at +0x14) is the first word of the NEXT
    image's FIP UUID (gxlimg uuid_list): bl30 links 0xaabbccdd (bl301),
    bl301 links 0x6d08d447 (bl31), bl31 links 0x89e1d005 (bl32), bl32 links
    0xa7eed0d6 (bl33), bl33 links 0.  This is BL2's own load-address table:
    bl30 0x01100000, bl301 0x01200000, bl31 0x05100000, bl32 0x05300000,
    bl33 0x01000000."""
    records = []
    off = 0
    while True:
        p = buf.find(b"bl30\x00\x00\x00\x00", off)
        if p < 0:
            break
        off = p + 1
        if p < 8:
            continue
        base = p - 8
        if base + 0x28 > len(buf):
            continue
        addr, = struct.unpack_from("<Q", buf, base)
        if addr == 0 or addr > 0xFFFFFFFF:
            continue
        recs = []
        cur = base
        for _ in range(8):
            a, = struct.unpack_from("<Q", buf, cur)
            name = buf[cur + 8:cur + 16].split(b"\x00")[0]
            if not name or not all(48 <= c <= 57 or 97 <= c <= 122
                                   for c in name):
                break
            link, = struct.unpack_from("<I", buf, cur + 0x14)
            recs.append({"name": name.decode(), "addr": a, "link": link})
            cur += 0x28
        if recs:
            records = recs
            break
    if not records:
        raise ValueError("no FIP image records found")
    return records


def pt_census(dump, pt_off, n_entries=8192):
    """Census of descriptor shapes in a page table baked into a dump."""
    shapes = {}
    for i in range(n_entries):
        d, = struct.unpack_from("<Q", dump, pt_off + i * 8)
        if d:
            shapes[d & 3] = shapes.get(d & 3, 0) + 1
    return shapes


def pt_covers(dump, pt_off, lo, hi, n_entries=8192, section_bits=29):
    """True if every section covering [lo, hi) has a valid level-2 section
    descriptor (desc[1:0] == 1) in the table. U-Boot ARM64 (cache_v8.c)
    uses SECTION_SHIFT 29 -> 512 MiB per entry, one table = 8192 entries =
    4 GiB identity; page boundaries can only exist every 512 MiB."""
    first = lo >> section_bits
    last = (hi - 1) >> section_bits
    if last >= n_entries:
        raise ValueError("range beyond table")
    for idx in range(first, last + 1):
        d, = struct.unpack_from("<Q", dump, pt_off + idx * 8)
        if (d & 3) != 1:
            return False
    return True
