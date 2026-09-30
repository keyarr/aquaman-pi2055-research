# BL33 interface round 15: OEM/run_command surface + AML_DATA_PROCESS validation

date: 2026-09-30, round 15. **strictly static, offline, no device.**
no USB, no `AM_REQ_RUN_IN_ADDR (0x05)`, no RAM write, no eMMC write,
no destructive fuzzing, no reset. every address below comes from the
round-14 image (`reports/round14-bl33-persist/bl33-37e18000.bin`,
sha256 `664fb34a…`, `[0x37e18000, 0x37ff0000)`) plus the reference
source in `.src/u-boot-khadas`. prior artifacts untouched; new evidence
in `reports/round15-bl33-interface/`, new tool `tools/bl33_round15.py`,
new tests `TestBl33Round15` in `tools/run_tests.py` (11 tests, pass).

answer to the round question first:

> Existe no BL33 uma primitiva controlavel pela OEM interface que
> permita modificar memoria ou transferir controle, ou o unico caminho
> relevante continua sendo do_bootm -> AML_DATA_PROCESS -> BL31?

**both.** `do_bootm -> AML_DATA_PROCESS -> BL31` is still the only
*verified* path, but it is **not** the only controllable memory/control
path: `oem` reaches two HIGH-confidence RAM-write primitives
(`mmc read`, `ddr_test_copy`), env-RAM writes (`setenv`, `env set`),
eMMC writes (`mmc write`, `store write`, `gpt`, `env save`), and three
control-flow mechanisms (`bootm`, `run`, `update`/burning). what is
**not** shown: signature bypass, key material, kernel arbitrary-write,
or any BL31 vulnerability. details below.

## 0. answer block

```text
image                   0x37e18000 .. 0x37ff0000 (0x1d8000, sha256 664fb34a...)
cmd_tbl                 80 slots (15-char max name, 48 B stride, §A)
top-level md/mw/cp/go   ABSENT (build has no CONFIG_CMD_MEMORY etc, §A.1)
run_command             0x37e5e968 (unchanged from round 14)
cb_oem frame            0x50 B; local buf x29+0x20, 0x30 B; copy max 33 B (E2, §D)
E2 verdict              REFUTED as a primitive (truncation/over-read only)
HIGH RAM primitives     mmc read 0x37e2d890 (eMMC->RAM) / ddr_test_copy 0x37e3d1b0 (RAM->RAM)
E3 SMC                  X0=0x820000ff X1=0x40 X2=user_addr X3=0x1800000 X4=7 (§E)
BL31 validation         UNPROVEN from available artifacts (§F)
second SMC 0xb2000016   host-reachable via oem, log-level only, no secboot link (§H)
```

## A. the real run_command universe (80 commands)

extracted with `tools/bl33_round15.py cmdsurface` (file `01_cmdsurface.txt`).
handler addresses are HIGH (cmd_tbl slots); behavioral flags are per-handler
direct-callee evidence (HIGH where the handler itself parses host args into
the primitive, MEDIUM where a sub-dispatch or backend stands in between).

### A.1 absence proof (the priority list vs the build)

of the brief's priority list, present: `itest printenv setenv mmc echo
test bootm`. absent as top-level commands: `md cmp crc32 iminfo imls cp
cp.b cp.l cp.q mw mw.b mw.l mw.q load fatload ext4load part source go
booti bootz saveenv loady`. evidence: 80-slot census (`04_cmds.txt` round
14, `01_cmdsurface.txt` this round) + string probes (`02_memscan.txt`):
`memory display/copy/write`, `checksum calculation`, `go - start`,
`booti -`, `source -`, `\0md\0`, `\0cp\0`, `\0go\0`, `\0source\0`,
`\0booti\0`, `\0base\0` all absent. three decoys that ARE present but are
not commands: `\0mw\0` (i2c subcommand name at `0x37ec292d`), `\0crc32\0`
(hash algorithm name at `0x37ebfd80`), `\0loadb\0` (serial-load help at
`0x37ec3406`). `setenv`/`saveenv` note: `setenv` exists (`0x37e58470`);
`saveenv` exists only as `env save` (`0x37e57d3c`). the reference source
defines md/mw/cp/cmp/crc32/base/loop in `common/cmd_mem.c` and
source/go/booti elsewhere, but this build does not compile them in.

### A.2 Table 1 - OEM/run_command surface

legend: HC = host-controlled input reaches handler args (hex/strings);
MW = memory write; CF = control-flow transfer; LOCK = lock-gated in BL33
(all `no`: the `0x37e9593c` gate covers fastboot flash/erase, never U-Boot
commands); conf = confidence in the MW/CF verdict.

```text
command            handler     HC input              MW              CF              LOCK  conf
amlmmc             0x37e2f064  subcmd+args           sub-dependent   no              no    MED
avb                0x37e63a64  subcmd+args           no              no              no    MED
bcb                0x37e2b3e8  args (no-op stub)     no              no              no    MED
bmp                0x37e277f0  subcmd+addr           no (RAM read for display only)  no   no  MED
boot_cooling       0x37e56860  none                  no              no              no    MED
bootm              0x37e24c00  addr hex              no              YES (verified boot)   no  HIGH
chipid             0x37e634bc  none                  no              no              no    MED
clkmsr             0x37e57ac8  clk id                no              no              no    MED
cvbs               0x37e62b44  subcmd+args           no              no              no    MED
d2pll              0x37e3a9e8  numeric args          POSSIBLE (PLL regs) no          no    MED
dcache             0x37e27ba4  on/off/flush          no (cache ctl)  no              no    MED
ddr_spec_test      0x37e3e098  test args             POSSIBLE (pattern fill, test area) no no MED
ddr_sram_tune      0x37e3aaf4  numeric args          no              no              no    MED
ddr_test_cmd       0x37e56170  test args             no              no              no    MED
ddr_test_copy      0x37e3d1b0  src dst size (hex)    YES (RAM->RAM copy+fill) no     no    HIGH
ddr_tune_dqs       0x37e40148  none (empty)          no              no              no    MED
ddr_tune_dqs_step  0x37e40c08  numeric args          no              run_command (constant "save"-ish) no MED
ddrtest            0x37e3d540  test args             POSSIBLE (pattern fill, test area) no no MED
dtimg              0x37e36508  subcmd+args           no              no              no    MED
echo               0x37e28000  text                  no              no              no    HIGH
efuse              0x37e56804  none (empty stub)     no              no              no    MED
efuse_user         0x37e72ef0  op+addr/size          OTP via SMC (writes use verified path per round 14) no no MED-HIGH
emmc               0x37e2f0ec  subcmd+args           sub-dependent (storage) no      no    MED
env                0x37e57d6c  subcmd (8, §B.3)      YES via set / eMMC via save YES via run no HIGH(disp)/MED-HIGH(eff)
exit               0x37e280e4  code                  no              no (script exit) no   MED
ext4size           0x37e2811c  dev:file              no              no              no    MED
false              0x37e36764  none                  no              no              no    HIGH
fastboot           0x37e3a840  none                  no              no (re-enters USB) no MED
fatinfo            0x37e2814c  dev                   no              no              no    MED
get_avb_mode       0x37e2b820  none                  env var (setenv backend) no     no    MED-HIGH
get_rebootmode     0x37e60478  none                  env var + run_command   dispatch (br x1) no MED
get_valid_slot     0x37e2bb7c  none                  no              no              no    MED
gpio               0x37e2a204  pin/val               POSSIBLE (MMIO regs) no        no    MED
gpt                0x37e2e9b8  args                  YES (eMMC GPT write path) no    no    MED-HIGH
hdmitx             0x37e6141c  subcmd+args           no              no              no    MED
help               0x37e26644  none                  no              no              no    HIGH
i2c                0x37e2a4e4  subcmd (mw/mm = I2C bus, NOT RAM) device-bus only no  no    MED
icache             0x37e27b18  on/off                no (cache ctl)  no              no    MED
img_osd            0x37e6225c  subcmd+args           no              no              no    MED
irblaster          0x37e27c30  subcmd+args           no              no              no    MED
itest              0x37e2b348  expr                  no              no (br x2 = bounded op dispatch) no MED-HIGH
keyman             0x37e74290  subcmd+args           sub-dependent (key areas) no    no    MED
keyunify           0x37e73c84  op+name/addr          POSSIBLE (secure/normal/efuse backends) no no MED-HIGH
mmc                0x37e2ca3c  subcmd (14, §B.2)     YES via read (RAM) / write (eMMC) no no HIGH(disp)/HIGH(eff)
mmcinfo            0x37e2cbf0  none                  no              no              no    MED
monitor_bt_cmdline 0x37e63e44  args                  no evidenced    table blr (bounded) no MED
open_scp_log       0x37e60864  level                 no              no              no    MED
osd                0x37e61da0  subcmd+args           no              no              no    MED
printenv           0x37e57ea8  [names]               no (env read)   no              no    HIGH
query              0x37e56224  op                    no evidenced    no              no    MED
read_temp          0x37e571f8  none                  POSSIBLE (env backend) dispatch (br x3) no MED
reboot             0x37e60654  [mode]                no              no (SMC 0x82000042/PSCI reboots) no HIGH
reset              0x37e21684  none                  no              no (resets)     no    MED
ringmsr            0x37e57afc  args                  no              no              no    MED
rpmb_state         0x37e57b4c  none                  POSSIBLE (env/bootargs) no      no    MED
rsvmem             0x37e62e84  subcmd+args           no              no              no    MED
run                0x37e5ea04  var names             no              YES (env script -> run_command) no HIGH(chain)/MED(bytes)
set_active_slot    0x37e2bd60  slot (no-op stub)     no              no              no    MED
set_trim_base      0x37e56d40  numeric               no evidenced    no              no    MED
set_usb_boot       0x37e607e8  value (hex, unvalidated) no          no (SMC 0x82000043) no HIGH
setenv             0x37e58470  name [value]          YES (env RAM)   no              no    HIGH
setkeys            0x37e219f0  ids                   env vars (2x setenv backend) no no   MED-HIGH
showvar            0x37e22aa8  [names]               no              no              no    MED
silent             0x37e59300  flag                  no              no              no    MED
sleep              0x37e2c9b8  seconds               no              no              no    MED
store              0x37e33900  subcmd (14, §B.2)     YES via write (eMMC), RAM via read no no HIGH(disp)/MED-HIGH(eff)
systemoff          0x37e6084c  none                  no              no (SMC system-off) no HIGH
tee_log_level      0x37e63534  level (decimal)       no              no (SMC 0xb2000016) no HIGH
temp_triming       0x37e56d80  trim base             no              run_command x3 (constant strings) no MED-HIGH
test               0x37e36774  expr                  no              no (br x0 = bounded op dispatch) no MED-HIGH
true               0x37e3676c  none                  no              no              no    HIGH
ui                 0x37e62580  subcmd+args           no              no              no    MED
unpackimg          0x37e358e0  [addr]                image buffers (RAM, MED-HIGH) backends call aml_sec_boot_check (round 14) no MED-HIGH
update             0x37e78ff8  [ms]                  bounded (download buffer) INDIRECT (burning -> bootm) no MED-HIGH
usb                0x37e37310  subcmd                no              no              no    MED
vout               0x37e62d0c  subcmd+args           no              no              no    MED
vpp                0x37e602cc  subcmd+args           no              no              no    MED
vpu                0x37e3a88c  subcmd+args           no              no              no    MED
write_trim         0x37e57518  args                  POSSIBLE (trim persistent write) dispatch (br) no MED
write_version      0x37e56d18  version               POSSIBLE (version persistent write) no no      MED
```

## B. memory-write commands (no execution; handlers fully traced)

rating rule used: LOW = name found; MEDIUM = handler + plausibly
controlled args; HIGH = handler -> write function with host arg in the
register at the call. only HIGH items are called primitives.

### B.1 HIGH: `mmc read` - eMMC -> RAM, host address (file 06_handlers.txt)

`oem mmc read <addr> <blk> <cnt>` -> `mmc` dispatcher `0x37e2ca3c`
(`find_cmd` + `blr x4`, maxargs check) -> `do_mmc_read` `0x37e2d890`:

```text
argc == 4 required (else usage return)
argv[1] -> simple_strtoul(.,0,16) -> x22 (RAM dst)
argv[2] -> simple_strtoul -> x21 (blk)
argv[3] -> simple_strtoul -> x19 (cnt)
blk_dread = [x23,#0x158]; blr x4(dev, blk, cnt, buf=x22)
flush_cache(addr, cnt*512) after
```

matches `common/cmd_mmc.c:284 do_mmc_read` line for line. host controls
dst/blk/cnt, no address validation in the handler. bytes written are
eMMC contents (not host bytes). fits the oem 31-char budget, e.g.
`mmc read 1080000 0 1` (22 chars). eMMC is only read, not modified.

### B.2 HIGH: `mmc write` - RAM -> eMMC, host address (storage write)

`do_mmc_write` `0x37e2d764`: same parse (`argv[1]`->x24 source,
`argv[2]`->w23 blk, `argv[3]`->w20 cnt), `blk_dwrite` at `[x22,#0x160]`
via `blr x4`. matches `common/cmd_mmc.c:312`. modifies eMMC (not RAM);
listed so the two directions are not confused.

### B.3 HIGH: `ddr_test_copy` - RAM -> RAM copy+fill, host src/dst/size

`do_ddr_test_copy` `0x37e3d1b0` vs `common/cmd_ddr_test.c:1667`:

```text
argc > 3 required for host args (else defaults 0x1080000/0x8180000/0x2000000)
argv[1] -> strtoul-variant 0x37e3cbb0 -> src (x26)
argv[2] -> strtoul -> dst (x23)
argv[3] -> strtoul -> size w20; size < 0x1000 forced to 0x2000000
copy loop 0x37e3aea0(dst, src, size): ldr w3,[x1]; stur w3,[x0] (16 B/iter)
pattern-fill loop writes 0x12345678 words over the dst region
single-word stage: ldr from src region, str to [dst+r27]
```

source `ddr_test_copy(dst, src, size)` confirms the direction. minimal
invocation `ddr_test_copy 0 0 0x1000` is 23 chars (fits oem); full-size
addresses need short hex without `0x` to fit 31 chars. no range check on
src/dst in handler or source.

### B.4 MEDIUM-HIGH: env RAM and storage

- `setenv 0x37e58470`: 6-instruction trampoline (`cmp w2,#1; b.le fail;
  b 0x37e58294` = do_env_set). `setenv name value` writes env RAM. HIGH
  as a mechanism, MEDIUM-HIGH end-to-end only because persistence
  (`env save` -> `0x37e57d3c` -> eMMC) was not executed here.
- `env` dispatcher `0x37e57d6c` -> 8 subcommands at `0x37ee70f8`
  (`default/delete/export/import/print/run/save/set`, 48 B stride):
  `env set` = same backend as setenv; `env run` = do_run `0x37e5ea04`.
- `mmc` subtable at `0x37ee5bc0` (14 valid: info/read/write/erase/rescan/
  part/dev/list/lifetime/ext_csd/ffu/hwpartition/setdsr/test).
- `store` subtable at `0x37ee62f0` (14 valid: init/exit/disprotect/
  rom_protect/size/scrub/erase/read/write/rom_read/rom_write/dtb/key/
  mbr). `store read/write` are the same RAM<->eMMC shape as mmc; their
  sub-handlers were entry-checked, not instruction-traced this round,
  hence MEDIUM-HIGH not HIGH.
- `gpt` (`write`), `keyunify` (`write`, secure/normal/efuse backends per
  strings `secure`/`do_keyunify`), `efuse_user` (OTP via sharemem; secure
  writes already inside the round-14 verified set), `write_trim`,
  `write_version`, `ddrtest`/`ddr_spec_test` (pattern fills of test
  areas): MEDIUM - reachable backend families, byte-level primitive not
  isolated to HIGH this round.

### B.5 bounded host-bytes path

`update 0x37e78ff8` -> `0x37e78f94` (v2 burning). `cb_download`
validates size (`0` rejected, `> ddr_size_usable` rejected, round 14
E6) before USB RX into the download buffer. host bytes land in one
bounded buffer, not at a host address. MEDIUM-HIGH, not a general write.

## C. control transfer without do_bootm (no new jump primitive found)

- `go/booti/bootz/source` do not exist in this build (§A.1). no handler
  contains a host-address `br/blr` to a parsed address: every `blr x4`
  in dispatchers (`mmc/store/env/amlmmc/avb/...`) calls a subcommand
  function pointer returned by `find_cmd` (table-bounded); `br x0/x2` in
  `test/itest` and `br x1/x3` in `get_rebootmode/read_temp` are bounded
  operator/table dispatches, not address jumps (`02_memscan.txt` lists
  all sites).
- `run 0x37e5ea04`: `getenv(argv[i])` -> `run_command` per var (loop).
  host picks var names; bytes come from env RAM. composed with `setenv`
  (`oem setenv k v` + `oem run k`) this chains two <=31-char calls into
  longer script execution. mechanism HIGH, multi-call chain POSSIBLE BUT
  UNPROVEN (not executed).
- `bootm`: the verified path (fails closed, `Sig Check %d`, round 14 E6).
- `update`: burning protocol re-enters `bootm` on downloaded images
  (round 14 §D.3); INDIRECT transfer, needs protocol steps.
- `temp_triming`/`ddr_tune_dqs_step`/`get_rebootmode` call `run_command`
  with constant/table strings, not host addresses.
- verdict: no equivalent of `go`/raw-jump exists; transfers go through
  `run_command` (script semantics) or the verified `bootm`.

## D. E2 precise analysis (file 03_oemframe.txt) - REFUTED as primitive

```text
0x37e95630  stp x29,x30,[sp,#-0x50]!   frame = 0x50 = 80 B, x29 = sp
0x37e95648  str x1,[x29,#0x48]          save cmd ptr (x19 spill at [sp,#0x10])
0x37e95654  mov x1,#0x20               strnlen(cmd, 32)
0x37e95660  add x2,x0,#1               n = min(strlen,32)+1 = 1..33
0x37e95668  add x0,x29,#0x20           buf; bytes to frame end = 0x50-0x20 = 0x30 = 48
0x37e9566c  bl memcpy                  memcpy(buf, cmd, n), max 33 into 48
0x37e95678  str x0,[x29,#0x48]          p = buf
0x37e9567c  add x1,#0xa0d (" ")        strsep(&p, " ")
0x37e956a0  bl run_command             run_command(token-after-"oem", 0)
```

1. read past the buffer: YES, bounded - cmd >= 32 B leaves buf
   unterminated (`buf[32] = cmd[32] != 0`), `strsep` scans past the 33
   copied bytes for ` ` or NUL into stack garbage (up to frame end at
   48 B if lucky, past it if not). read-only over-read, no secret
   exfiltration path (result goes to the local parser, not the host).
2. alter adjacent data: NO - copy length clamped to 33 <= 48, the frame
   cannot be overflowed; no write past buf.
3. parser impact: YES, trivially - `run_command` can receive a token
   with trailing stack bytes when input >= 32 B; that affects which
   command string is parsed, not memory safety.
4. usable primitive: NO - truncated/unterminated behavior only.

## E. E3 reconstruction (file 04_e3.txt)

source: `common/cmd_bootm.c:142` + `arch/arm/cpu/armv8/gxl/bl31_apis.c`
`aml_sec_boot_check(nType, pBuffer, nLength, nOption)`, confirmed by the
image (`0x37e24cc8..0x37e24cf0`, wrapper `0x37e19ea8`):

```text
do_bootm site 1 (0x37e24cf0):
  argv[1] -> simple_strtoul(.,0,16) -> w1   (argc > 0; else x1 = 0x1080000)
  x0 = 0x40            nType  = AML_D_P_IMG_DECRYPT
  x1 = user_addr       pBuffer (host hex, NO range/compare in BL33)
  x2 = 0x1800000       nLength = GXB_IMG_SIZE (24 MiB, fixed)
  x3 = 7               nOption = GXB_IMG_DEC_ALL (fixed)
wrapper 0x37e19ea8 -> SMC:
  x7=x0 x6=x1 x5=x2 x4=x3 preserved
  x0 = 0x820000ff (mov x0,#0xff; movk x0,#0x8200,lsl#16)
  x1 = x7 (0x40); x2 = x6 (user_addr); x3 = x5 (0x1800000); x4 kept (7)
  smc #0
  then flush_dcache_range(pBuffer, pBuffer+nLength); return SMC x0
i.e.  smc(X0=0x820000ff, X1=0x40, X2=user_addr, X3=0x1800000, X4=7)
```

second site `0x37e24f90`: `(nType=0x100, pBuffer=0x1080000, nLength=0x500,
nOption=7)` on the boot-flow buffer (`bl 0x37e5b2f0` result combined
with the return value afterwards). BL33-side validation of the
user address: none found (no compare against RAM top `0x38000000`, DTB,
or image header before `0x37e24cf0`). return handling fails closed
(`cbz w0 -> continue`, else `Sig Check %d`, round 14 E6).

## F. BL31 side (file 05_bl31ref.txt) - UNPROVEN, by design of artifacts

- repo has no ATF/BL31 source (`.src/` = linux-amlogic, MiTV_OpenSource,
  u-boot-khadas). reference binaries
  `.src/u-boot-khadas/fip/gxl/bl31.bin` (`0x2c3a8` B) and `gxb/bl31.bin`
  exist and DO contain the secure-boot module: strings `AMLSECU`,
  `secureboot`, `plat/gxl/crypto/secureboot.c`,
  `Amlogic-secure-boot-module-v0.4`, `fail to load internal RSA key!`,
  `no key found`, `R%d`/`R-%d` logging.
- bounds-flavored error strings exist on neighboring paths: `ERROR!
  exceed max DMA SHA2/AES length`, `flash size is too large!`,
  `storage size is larger than flash!`. these prove *some* size checks
  exist in BL31 crypto/storage code, NOT that `AML_DATA_PROCESS`
  validates the caller buffer range. the link is unproven.
- no `0x820000ff` literal, no `0x1800000` literal, no `movk ...#0x8200`
  in either binary; the two `cmp w0,#0xff` sites are DER-length loops
  (`ldrb [x25],#1` / `ldrb [x19],#1` terminators), not SMC dispatch.
  SiP dispatch compares table-loaded IDs, so the handler was not
  isolated to function level this round. stated plainly instead of
  inferred.
- verdict: `BL33 does not validate` (HIGH, §E) + `BL31 unknown from
  available artifacts` = POSSIBLE BUT UNPROVEN validation gap. the
  `BL31 validates correctly` alternative is equally unproven. no BL31
  vulnerability is claimed.

## G. address range / page table (evidence only, no invented perms)

- candidate BL33 range `[0x37e18000, 0x37ff0000)` is proven resident:
  round-14 page map (code/data/rodata pages), nonzero tail to
  `0x37feffff`, live `.bss` write at `0x37f8a638`, page table at
  `0x37ff0000` (8192 descriptor-shaped words ending at `0x3800000
...[truncated 3070 chars]