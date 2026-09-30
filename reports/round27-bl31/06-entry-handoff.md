# 06 — entrypoint, image metadata, handoff

## what the FIP data says (FAMILY STRUCTURAL REFERENCE)

`gxlimg/fip.c` documents the format contract: *"BL31 binary store
information about load address and entry point in the FIP data"* — the
0x50-byte BL31 header is copied by the packer into the FIP ToC region
(`FTE_BL31HDR_OFF(n) = 0x430 + n*0x50`), preceded by a two-word marker
`{BL31_ENTRY_MAGIC 0x87654321, 1}` written at FIP offset 0x400 (gxlimg
`bl31magic`). so a real FIP carries, per BL31:

```text
FIP +0x400       87654321 00000001      <- BL31 entry marker
FIP +0x430+n*50  12348765 00004e20 05100000 ...  <- the header (02)
```

in the header itself the only nonzero fields are load/rsv/secure (no separate
entry word), so the family convention is **entry == load address**
(0x05100000): BL2 jumps to the image base after load. consistent with the
reference binaries: `bl31.bin` `_start` (0xaa0003f4 = mov x4,x0 /
0xaa0103f5 = mov x5,x1 — BL2 passes params in x0/x1 saved to x4/x5; then
`ldr x0, =_anon`-style `movz x1,#0x228/movk 0xc810` AClamp loop, `mrs
sctlr_el3` clear M, `msr vbar_el3`, spin table read from SRAM mailbox
`0xd9013f00` for secondaries).

the aquaman FIP at rest is encrypted (`bootloader.img`), so the EXACT entry
field is unrecoverable without decryption; the family value + live boundary
make `0x05100000` the presumed entry.

## what BL33 knows and hands on (EXACT)

```text
AO GP regs (01-ao-regs.md)      : start/size of bl31+bl32 reservations
SMC 0x82000020/21               : sharemem in/out bases (runtime, from BL31)
SMC 0x820000ff (AML_DATA_PROCESS): secure boot decrypt/verify into NS buffers
SMC 0x82000043 (SET_USB_BOOT)   : usb boot function
SMC 0xb2000016                  : tee log level
DTB properties (patched by BL33): secmon/secos ranges + reserve_mem_size
NO pointer/entry/vector/size-of-image beyond the above ever crosses to NS.
```

the round26 summary "no entrypoint in regs: start+size only. NO
pointer/entry/vector in handoff" stands, and round27 explains why none is
needed: NS never jumps to BL31; it only makes SMCs (the dispatcher lives in
the protected window — rounds 14/18/26 negative results in the readable MiB
leave exactly one place for it).

## indirect entrypoint evidence census (brief s9)

```text
function pointers to 0x051xxxxx in BL33 : 0
AO register carrying an entry           : none of CFG0..CFG9 semantics fit
                                          (CFG0 = mem top/chip id, CFG7 =
                                          usb boot flags per romboot.h;
                                          CFG3/4/5 = rsvmem; others unused)
global/.bss holding an image address    : 0 (0x05100000-word census = 0)
device-tree property with an entry      : 0 (ranges + SMC ids only)
literal 0x05100000 word anywhere exact  : 0 (all appearances are computed:
                                          +0x100000 add, table-adjacent
                                          arithmetic, or the absent DTB prop)
```

the entrypoint exists only inside the secure chain: BL2's FIP table, the
encrypted header, and BL31 itself.

## copy/decrypt flow before the secure world (brief s10)

the only NS-side firmware flows are (round14/15/17, unchanged):

```text
eMMC -> RAM (imgread/store read) -> SMC 0x820000ff decrypt+verify in-place
update/burning -> USB -> fixed buffer 0x07700000 -> bootm -> same SMC
```

no NS parser touches AMLSECU/FIP headers *of the bootloader* (the FIP is
consumed entirely inside the pre-BL33 chain); `aml_encrypt_gxl --bootsig
--aeskey enable` (amlsecu-reverse.md §4) encrypts the whole u-boot.bin FIP at
pack time. there is no separate "copy/decrypt into 0x05000000+" flow visible
in NS: the load into the secure window happened once, in BL2, at boot.
nothing to decrypt without the vendor FIP key; per brief, not attempted.
