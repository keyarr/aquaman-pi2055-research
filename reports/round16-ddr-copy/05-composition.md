# round 16.05 - composition: update + ddr_test_copy, and mmc read

static only, nothing executed, nothing written to the device.

## 1. the claimed chain

```text
host -> update -> RAM buffer (fixed, 01)
                    |
                    v (argv[1] = buffer addr)
             ddr_test_copy (02)
                    |
                    v (argv[2] = dst, argv[3] = len)
          destination (unclamped, 03)
```

Address composition: PROVEN. Data composition: REFUTED as arbitrary
(only 16 tail bytes survive). The chain is therefore a destructive
constant-fill primitive with a word-tail, not an arbitrary write.

Walked end to end with concrete values (offline arithmetic, no I/O):

```text
1. host: fastboot download 0x1000 bytes
   -> cb_download 0x37e95408 accepts (0 < size <= usable)
   -> rx_handler 0x37e95274 memcpy(0x10200000+bytes, usb, len)
   -> RAM [0x10200000,0x10201000) = host bytes. CONFIRMED path (01).
2. host: oem ddr_test_copy 10200000 <dst> 1000  (spelling fits 31 chars
   when hex is shortened; parser takes no-0x hex)
   -> argv[1]=0x10200000 -> x1, argv[2]=dst -> x0, argv[3]=0x1000 -> w2
   -> copy loop writes (0x1000>>2)*16 = 0x4000 bytes src->dst (transient)
   -> fill loop writes 0x4000 bytes of 0x12345678 over dst (destroys step above)
   -> tail writes 16 src-derived bytes at dst+0x4000.
   End state at dst: 0x4000 bytes pattern + 16 bytes host-derived.
```

Same walk with the burning buffer (src 0x07700000) is identical except
the ingress is USB bulk slots instead of fastboot download.

What the chain CAN do (proven shape):

```text
- write 0x12345678 over [dst, dst+L) where L=(clamp(len)>>2)*16*loop (min 16 KiB)
- write 16 host-derived bytes at dst+L
- pick dst arbitrarily (HIGH, 03), pick L via len/loop within the floor (PARTIAL)
```

What it CANNOT do:

```text
- place N arbitrary host bytes at an arbitrary dst with N chosen freely.
  The copy that could do it is overwritten before return (02 sect 4).
- write <16 KiB (floor), write without touching dst..dst+L with pattern,
  skip the pattern, or reorder the phases. All are fixed in code order.
```

Attempted salvages that fail statically:

```text
size<4 to skip the fill: impossible, parser floors to 0x2000000.
loop=0 to skip phases: parses as 0 (valid "0"), then subs x19,#1 underflows
  to 2^64 iterations -> hang, not a skip. No early-out path exists.
print=0 to skip the fill: print only gates printf, not the fill/reads/tail.
overlapping src==dst to preserve data: fill still overwrites with pattern;
  tail then copies pattern-derived words, not original host bytes.
```

## 2. mmc read, same analysis (brief section 9)

do_mmc_read 0x37e2d890 (common/cmd_mmc.c:284, full disasm in round 15
06_handlers.txt):

```text
argc==4 else usage return
argv[1] -> simple_strtoul64 -> x22 dst (no clamp)
argv[2] -> simple_strtoul64 -> x21 blk (w truncation at call)
argv[3] -> simple_strtoul64 -> x19 cnt (w truncation at call)
blk_dread = [x23,#0x158]; blr x4(dev=w0, blk=w1, cnt=w2, buf=x3=x22)
flush_cache(dst, cnt_masked*512) at 0x37e2d93c..0x37e2d944
  0x37e2d93c ubfiz x1,x19,#9,#0x17 ; len keeps low 23 bits of cnt
  0x37e2d944 bl 0x37e19764
```

```text
source      = eMMC blocks (blk,cnt). Host picks which blocks, not their bytes.
destination = RAM, host-controlled, no clamp (same HIGH shape as ddr dst).
length      = cnt*512 masked to (cnt&0x7ffffF)*512; top 9 bits of cnt dropped.
```

Why it is less composable than ddr_test_copy for host DATA (not for address):

```text
- data leg needs an eMMC round-trip: host->download buffer->eMMC (via
  mmc write / store write / flash, each with its own gates and eMMC wear)
  -> mmc read -> dst. Two extra stores, partition/erase constraints, and
  the bytes at rest are eMMC bytes, not host-live bytes.
- ddr_test_copy reads live RAM (the download buffer directly); mmc read
  cannot see the download buffer until it is flashed.
- address/length legs are equivalent (both unclamped dst; mmc has the
  extra 23-bit cnt mask, ddr has the 0x1000 floor + 4x factor).
```

So: mmc read = equally powerful address primitive, strictly weaker data
primitive. It is the right exfil path (eMMC->RAM->upload was how rounds
7-13 read), not the right injection path.

## 3. what remains UNPROVEN / REFUTED (no BL31 work this round, per brief 10)

```text
signature / key / BL31 bypass: UNPROVEN (unchanged; nothing here touches SMC policy)
E2 as primitive: REFUTED (round 15, kept)
update gives host an address: REFUTED (01: both bases are mov-imm)
ddr_test_copy is a clean copy: REFUTED (02 sect 4: copy then fill)
update+copy is arbitrary write: NO (matrix in 03 sect 4; shape in sect 1 above)
mmc read is host-data arbitrary write: NO (source is eMMC, not host bytes)
```

No branch to RAM, no AM_REQ_RUN_IN_ADDR, no SMC patch, no
aml_sec_boot_check / do_bootm patch was attempted or proposed. First the
primitive had to be proven; it is now proven to be narrower than claimed.
