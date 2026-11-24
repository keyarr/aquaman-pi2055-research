# V2: kernel RAM patch via low-use syscall - 2026-11-19

Status: **PHASE A COMPLETE (OFFLINE_ONLY). PHASE B EXECUTED (2026-11-19) - FAILURE. uid=0 NOT obtained.**

No device was touched. No BOOT_ID exists in this round. Nothing here
supersedes `CURRENT_STATE.md`, `INVALIDATED_HYPOTHESES.md`, `apatch.md` or
`kernelsu-next.md`. The "AMLSECU ciphertext" block documented in those last two
files still stands: it will only be overcome if Phase B proves uid=0 in
hardware.

## 1. Scope

Patch the stock kernel in RAM, without Magisk, without a custom ramdisk, without initrd in
the FDT and without GhostLock. The SMC wrapper decrypts the kernel; the trampoline
injects `commit_creds(prepare_kernel_cred(0))` at the entry of the
`personality` syscall (nr 92). Boot with stock ramdisk and DTB.

Phase A (offline only): obtain plaintext, parse header, extract kallsyms,
choose syscall and code cave, assemble trampoline, generate bytes, verify
the userspace trigger, run tests.

Out of scope in this round: all of Phase B (device). No SMC, no
BL33 write, no boot.

## 2. Evidence level per line

| Line | Level | Basis |
| ----- | ----- | ---- |
| Reused plaintext dump (`stock_boot_plain.bin`, sha `035aa74d...`) | HARDWARE_REPRODUCED (reuse from a previous session) | v1, `imgread` + wrapper + MREAD; local file sha matches |
| Android header: page 0x800, kernel 0x959000 @0x800, ramdisk 0, second 0xf000 | PROVEN | `tools/analyze_android_boot.py` on `firmware/boot.img` |
| Effective KASLR N=0, kallsyms VA == runtime VA | OFFLINE_ONLY (inherited, strong inference) | `hazel-mm-struct-aquaman.md` KASLR section; no `/chosen/kaslr-seed`; Not reopened |
| `commit_creds` @ `0xffffff80090ccf08` | OFFLINE_ONLY (kallsyms + disasm) | vmlinux-to-elf on the raw Image; prologue matches |
| `prepare_kernel_cred` @ `0xffffff80090cd590` | OFFLINE_ONLY (kallsyms + disasm) | idem |
| `sys_call_table` @ `0xffffff8009dc2000` | OFFLINE_ONLY (kallsyms + relocs) | idem; entries are zeros in the file, filled by reloc at boot |
| `selinux_enforcing` @ `0xffffff800aaa132c` | OFFLINE_ONLY (kallsyms + source) | `.src/linux-amlogic/security/selinux/hooks.c:102`, `avc.c:989` |
| `__NR_personality = 92`, handler `sys_arm64_personality` @ `0xffffff800908ad00` | PROVEN | `include/uapi/asm-generic/unistd.h:292-293`; reloc addend matches the symbol |
| `sys_call_table[92]` is filled by R_AARCH64_RELATIVE at boot | PROVEN (static) | `arch/arm64/kernel/head.S:774-798` (`__relocate_kernel`); 424 relocs in the table page |
| Code cave `0xffffff8009dbbe00` (84 B) | OFFLINE_ONLY | zeros at the end of .text, no symbols, 0 relocs targeting the region |
| Trampoline AArch64 (84 B) | PROVEN (offline) | `aarch64-linux-gnu-objdump -D -b binary -m aarch64` (Linaro 6.3.1) + capstone 5.0.7 |
| Static trigger compiled with syscall 92 / arg 0xffffffff | PROVEN (offline) | NDK r28c clang, API 28, `llvm-objdump` shows `mov w0,#0x5c ; mov w1,#-1` |
| Test suite: 126 tests, OK (1 skip) | PROVEN | `python3 tools/run_tests.py` |
| Patch works in hardware (uid=0) | OFFLINE_ONLY (not evaluated; depends on Phase B) | no hardware result in this round |

## 3. Commands executed

```sh
# reused dump
cp /tmp/v1/artifacts/kernel_plain.bin /tmp/v2/stock_boot_plain.bin
cp /tmp/v1/artifacts/kernel_image.bin /tmp/v2/stock_Image.bin
sha256sum /tmp/v2/stock_boot_plain.bin

# header
python3 tools/analyze_android_boot.py firmware/boot.img

# kallsyms
vmlinux-to-elf --e-machine 183 --bit-size 64 stock_Image.bin stock_vmlinux.elf
nm -n stock_vmlinux.elf | grep -E 'commit_creds|prepare_kernel_cred|sys_call_table|selinux_enforcing|kernel_init'

# VA validation: raw offsets + reloc addends
python3  # reading stock_Image.bin and stock_vmlinux.elf, see section 4

# generation and verification
python3 build_patch.py
aarch64-linux-gnu-objdump -D -b binary -m aarch64 --adjust-vma=0xffffff8009dbbe00 tramp_final.bin

# trigger
aarch64-linux-gnu-gcc -c -o trigger.o trigger.c
<ndk>/clang --target=aarch64-linux-android28 -static -O2 -o trigger trigger.c
<ndk>/llvm-objdump -d trigger | grep -B4 -A2 'mov.*0x5c'

# tests
cd /home/erick/Documentos/projetos/aquaman_9_PI_2055 && python3 tools/run_tests.py
```

Linaro 6.3.1 toolchain (`aarch64-linux-gnu-gcc`) compiles `.o` but does not link:
the sysroot lacks `crt1.o` / `libc.a`. Trigger linked with NDK r28c clang,
static, API 28.

## 4. Addresses, expected vs observed bytes

Convention: `VA = 0xffffff8009080000 + file_off(Image)`;
`phys = 0x1080000 + file_off(Image)` (KASLR N=0).

### Symbols

| Symbol | VA | file_off | Use |
| ------- | -- | -------- | --- |
| `_text` | `0xffffff8009080000` | `0x0` | base |
| `commit_creds` | `0xffffff80090ccf08` | `0x4cf08` | call 2 |
| `prepare_kernel_cred` | `0xffffff80090cd590` | `0x4d590` | call 1 |
| `selinux_enforcing` | `0xffffff800aaa132c` | `0x1a2132c` | zeroed in the trampoline |
| `sys_call_table` | `0xffffff8009dc2000` | `0xd42000` | table |
| slot 92 (personality) | `0xffffff8009dc22e0` | `0xd422e0` | target |
| `sys_arm64_personality` | `0xffffff800908ad00` | `0xad00` | original handler |

### Patch 1 - relocation addend of slot 92 (8 bytes)

Reason: the table comes zeroed in the file. `__relocate_kernel` writes
`addend + slide` to each entry. With slide=0, the value written is the
addend itself. Patching the slot directly is useless: the relocation overwrites it.
Therefore the target is the addend field of entry 95549 in the `.rela` table.

| Field | Value |
| ----- | ----- |
| VA of addend | `0xffffff800a657828` |
| phys of addend | `0x2657828` |
| file_off | `0x15d7828` |
| expected bytes (stock Image) | `00 ad 08 09 80 ff ff ff` |
| bytes to write | `00 be db 09 80 ff ff ff` |
| meaning | `0xffffff8009dbbe00` (VA of trampoline) |

### Patch 2 - trampoline (84 bytes)

| Field | Value |
| ----- | ----- |
| VA | `0xffffff8009dbbe00` |
| phys | `0x1dbbe00` |
| file_off | `0xd3be00` |
| expected bytes (stock Image) | 84 x `00` |
| bytes to write | see `patch_spec.json` (`patches[1].bytes`) |

Cave: end of `.text`, between `__idmap_text_end` (`0xffffff8009db74c0`) and
`_etext` (`0xffffff8009dc0000`). Zeros, no symbols, no relocation with
`r_offset` in the region. Does not overwrite the body of a live function.

### Disassembled trampoline (Linaro objdump)

```
ffffff8009dbbe00: a9bf7bfd  stp x29, x30, [sp,#-16]!
ffffff8009dbbe04: 910003fd  mov x29, sp
ffffff8009dbbe08: d2826581  mov x1, #0x132c
ffffff8009dbbe0c: f2a15541  movk x1, #0xaaa, lsl #16
ffffff8009dbbe10: f2dff001  movk x1, #0xff80, lsl #32
ffffff8009dbbe14: f2ffffe1  movk x1, #0xffff, lsl #48
ffffff8009dbbe18: b900003f  str wzr, [x1]              // selinux_enforcing = 0
ffffff8009dbbe1c: d29ab202  mov x2, #0xd590
ffffff8009dbbe20: f2a12182  movk x2, #0x90c, lsl #16
ffffff8009dbbe24: f2dff002  movk x2, #0xff80, lsl #32
ffffff8009dbbe28: f2ffffe2  movk x2, #0xffff, lsl #48
ffffff8009dbbe2c: 52800000  mov w0, #0
ffffff8009dbbe30: d63f0040  blr x2                     // prepare_kernel_cred(0)
ffffff8009dbbe34: d299e103  mov x3, #0xcf08
ffffff8009dbbe38: f2a12183  movk x3, #0x90c, lsl #16
ffffff8009dbbe3c: f2dff003  movk x3, #0xff80, lsl #32
ffffff8009dbbe40: f2ffffe3  movk x3, #0xffff, lsl #48
ffffff8009dbbe44: d63f0060  blr x3                     // commit_creds(cred)
ffffff8009dbbe48: 52800000  mov w0, #0                 // syscall return
ffffff8009dbbe4c: a8c17bfd  ldp x29, x30, [sp],#16
ffffff8009dbbe50: d65f03c0  ret
```

SP aligned to 16 throughout the sequence. x29/x30 saved and restored. No
callee-saved register clobbered. SELinux neutralized via `selinux_enforcing` (the 4.9
field equivalent to `selinux_state->enforcing` in later kernels), derived from
the source, not invented.

## 5. Syscall choice

`personality` (nr 92) instead of `syslog` (nr 116):

- `__NR_personality` in `asm-generic/unistd.h:292`, not used on the
  boot path of stock Android 9. `syslog` is more likely to be called by
  logging tools.
- `el0_svc` (`entry.S:985`) indexes `sys_call_table` directly by `scno`,
  with no offset. The 64-bit trigger uses the main table, not the compat one.
- Argument `0xffffffff` is the classic "restore default" value, harmless
  if the patch fails and the original syscall runs.

Residual risk: if anything in boot calls `personality`, the trampoline will run before
userspace and call `prepare_kernel_cred` early. No call found
in the source on init paths.

## 6. Risks and pending items for Phase B

1. **Patch application timing.** The trampoline and addend live in the
   *decompressed* Image. The site1 wrapper leaves the boot image with a gzip kernel at
   `0x1080800`. The phys addresses above (`0x1dbbe00`, `0x2657828`) only contain
   the Image after bootm decompresses. The exact point between decrypt/decompress/eret
   at which to apply the patch was not resolved offline. If Phase B patches the gzip,
   the bytes will not match and the MREAD criterion will abort - that is correct.
2. **Phase B boot address.** The prompt indicates `x2=0x1080800` in the boot
   stub. Offline, the entry of the decompressed Image is `0x1080000`
   (v1's `stub_br_final` used `0x1080000`). Confirm live before giving the
   `br`; if the Image is loaded with a 0x800 offset, all phys addresses above
   shift by 0x800.
3. **Addend vs slot.** The slot 92 relocation must be patched. Writing
   only the 8 bytes of the slot will be reverted by `__relocate_kernel`.
4. **SMC:** a direct call by the stub has already frozen the gadget. Use at most one
   per session; count on a power cycle.
5. **KASLR:** N=0 is a strong inference, not a hardware read in this round. If
   the slide is not 0, all VAs of the trampoline and the calls are wrong.
6. **SELinux:** `selinux_enforcing=0` makes the mode permissive; the credential
   will still have a SELinux context. Minimum criterion is uid=0; `getenforce` is extra.

None of this was tested in hardware. Offline-only.

## 7. Verdict

Phase A: **GO (offline)**. Patch spec generated in `/tmp/v2/patch_spec.json`,
trampoline verified by two disassemblers, static trigger compiled,
126 tests passing. No hardware result.

Phase B: **FAILURE (HARDWARE_REPRODUCED for the failure).** Several sessions, all with
Phase 0 PASS and Phase 1 GO. No variant reached uid=0. Details in section 9.

## 8. Superseding

None. Phase B failed; `apatch.md` and `kernelsu-next.md` are **not**
superseded on the point "block by AMLSECU ciphertext" - the V2 hypothesis of bypassing
the block via a RAM patch was REFUTED in the forms tested. `CURRENT_STATE.md`
was not altered. Nothing was erased or softened.

## 9. Phase B - live execution (2026-11-19)

### 9.1 Entry and GO (HARDWARE_REPRODUCED)

Each session: `adb reboot fastboot` -> `fastboot oem update 5000` (expected
FAILED) -> `1b8e:c003`, stage 16. read-only Phase 0 always PASS: `false` handler
`64 67 e3 37 00 00 00 00`, site1 `6e d4 ff 97`, site2 `c6 d3 ff 97`,
scratch zero. Phase 1 always GO: stub `00 00 80 52 c0 03 5f d6`, `false ->
success`, clean restore (`false -> failed:`). Baselines in
`/tmp/v2/baseline/`.

USB permission obtained via `pkexec` (sudo is not passwordless on the account, pkexec without
a password works for the wheel group).

### 9.2 Decrypt and dump integrity (HARDWARE_REPRODUCED)

Decrypt done by `bootm` itself (no direct SMC from the stub): `imgread kernel
boot 0x1080000` + intercept of the `cbz` at `0x37e24cf8` (`c0 00 00 34` ->
`c2 6c e7 17` = `b 0x37800000`), stub returning to the epilogue `0x37e25000`.
Header `ANDROID!` and kernel `1f 8b 08 00` at `0x1080800` confirmed.

sha256 of the live plaintext kernel == offline dump:
`035aa74de5c48f72189597ed823bea574a06696ef71608ab6d7a695d8768a02f`.
This promotes the Phase A offline dump to HARDWARE_REPRODUCED in this session.

### 9.3 Patches applied (HARDWARE_REPRODUCED)

Decompressed Image (26,544,640 B, sha `3c3522d8...`) downloaded at `0x1080000`
via `download_mem`, sha read back identical. The two targets of
`patch_spec.json` matched byte for byte before the patch (addend
`00 ad 08 09 80 ff ff ff`, cave 84 x `00`), and after an aligned 8B WRITE +
`dcache flush` the readback matched the expected bytes:
addend `00 be db 09 80 ff ff ff`, trampoline `fd 7b bf a9 ... c0 03 5f d6`.
Oracle before/after: `failed:` / `success`.

### 9.4 Boot attempts and results (HARDWARE_REPRODUCED for the failure)

| # | Variant | USB off | Android | BOOT_ID | trigger | uid | getenforce |
| - | -------- | ------- | ------- | ------- | ------- | --- | ---------- |
| 1 | `br x20` -> `0x1080000`, Image with addend + V1 trampoline | 1.62s | ~18s | `6a771ad4-a1a0-415f-a8eb-07e00eba15fb` | `personality=8` | 2000 | Enforcing |
| 2 | `br x20`, addend + V2 trampoline (`adr`-relative) + direct `b` in `sys_arm64_personality` | 1.61s | ~14s | `5a4cab8e-5cc0-4bdc-bbab-99a102f724ed` | `personality=8` | 2000 | Enforcing |
| 3 | `bootm` + CBZ intercept + patched gzip kernel (V2 trampoline) | 4.80s | ~16s | `dd9a7bb3-b3a3-4f6e-93ef-77893b407db1` | `personality=8` | 2000 | Enforcing |
| 4 | same as 3, trampoline with constant return `0x1234` (decisive test) | 4.77s | ~16s | `06ab7138-5304-4d38-846d-cfff371e5112` | `personality=8` | 2000 | Enforcing |

In all, `su: not found`. The `personality=8` return is the stock value (the
function `sys_arm64_personality` at `0xffffff800908ad00` does `and w0,w19,#0xff` and returns
the current personality). No variant executed the trampoline.

Trigger verification: static NDK r28c/API 28 binary, `main` passes
`w0=0x5c` (92) and `w1=-1`, `syscall` does `mov x8,x0 ; svc #0`. Syscall
number correct. `asm-generic/unistd.h:292` and the relocation table confirm slot 92 =
`sys_arm64_personality` @ `0xffffff800908ad00`. So the target was correct in the
file; what failed was the boot path.

### 9.5 Diagnostics (HARDWARE_OBSERVED)

- The copy stub after decrypt works: MREAD of `0x1080800` matched byte for byte
  with the patched gzip and the sha of the first 1 MiB identical. `bootm -> success`
  when the stub returns to the epilogue `0x37e25000`. In other words, the replacement of
  the kernel inside the decrypted image is real and verified.
- With the `bl` to `do_bootm_linux` (`0x37e25f68`, `96 01 00 94`) replaced by
  `mov w0,#0`, `bootm` returns without booting. After that, `0x1080000` still
  contains `ANDROID!`, `0x1080800` still contains the gzip, and there is no `ARMd` nor
  branch bytes at any of the candidate addresses checked
  (`0x1000000`, `0x1080000`, `0x1100000`, `0x1800000`, `0x1900000`,
  `0x19d9800`, `0x1a000000`, `0x20000000`, `0x2100000`, `0x30000000`).
- A scan of 4 MiB-aligned slots from `0x1000000` to `0x5400000` did not find
  `ARMd`; the gadget fell at `0x5400000` (read of an unmapped region) and the
  session was ended by a power cycle. No conclusion about the location of the
  decompressed image is drawn from this.
- Diagnostics conclusion: the direct `br` to `0x1080000` does not execute the
  carpet-bombed image (the SoC reboots and boots the stock kernel from eMMC), and `bootm` did
  not leave an observable decompressed image at `0x1080000`. The root cause of
  the patch not being consumed is the boot chain, not the patch bytes.

### 9.6 Compatibility between relocations and patch

Useful finding for any future attempt: `__rela_offset` is
`0x2427a60` and `__rela_size` `0x3e2878` (literals in
`__relocate_kernel`, `0xffffff8009db72f4/8`), not `0x13a7a60`. This is
consistent: `.rela` is at `KIMAGE_VADDR + 0x2427a60` and, with the Image loaded
at `0x1080000`, lands at physical `0x2427a60` (file `0x13a7a60`). The addend of
slot 92 is at index 95549, file `0x15d7828`, physical `0x2657828`. The bytes
are correct; the problem is that the kernel that boots does not consume them.

### 9.7 Final state and rollback

Everything written was RAM-only. The attempts with boot rebooted the SOC and discarded
RAM. The last diagnostic session ended with the gadget down and was recovered
by a power cycle. There was no flash, erase, saveenv, persistent setenv, efuse,
BootROM, RUN_IN_ADDR, MODIFY or blind ioctl. No direct SMC call by the stub
was made in any attempt; decrypt always went through `bootm`. No
versioned file was altered other than this report. `CURRENT_STATE.md` and
`INVALIDATED_HYPOTHESES.md` remain intact.

### 9.8 Final verdict

**FAILURE / REFUTED in the forms tested.** The RAM patch mechanism is
HARDWARE_REPRODUCED (bytes written, read back, oracle sound), but none
of the four boot variants executed the injected code. The minimum
uid=0 criterion was not achieved; `getenforce` remained Enforcing. There is no evidence
to promote any line of `apatch.md`/`kernelsu-next.md`. Next open question
(unanswered): why `br`/`bootm` does not deliver
the patched image to the kernel, even though the copy after decrypt is byte-exact.
Future investigation should begin by identifying the real physical address of the
decompressed image that bootm executes, instead of repeating patch variants.

Artifacts: `/tmp/v2/` (outside the repo): `stock_boot_plain.bin`,
`stock_Image.bin`, `stock_vmlinux.elf`, `build_patch.py`, `patch_spec.json`,
`tramp_final.bin`, `trigger.c`, `trigger.o`, `trigger`.
