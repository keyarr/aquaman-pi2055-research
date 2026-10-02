# buffer-proof — download buffer == loadaddr; device is secure-fused (2026-09-29 session)

> NOTE (2026-10-02): title / historical name is stronger than the proof.
> Runtime evidence establishes overlap, not exact equality. See
> `reports/fastboot-memory-flow.md` §4 and `reports/CURRENT_STATE.md`
> (Fastboot). `BUF ∩ Y != ∅` is hardware-reproduced; `BUF == Y == 0x1080000`
> remains INCONCLUSIVE.

SUPERSEDES the X=0x10200000 claim in reports/bootm-test-image.md and the
X!=Y root-cause in reports/fastboot-boot-verdict.md. those were derived
from the khadas reference header (include/g_dnl.h:18), never runtime-proven
on this build. what follows IS runtime-proven, all RAM-only, no
flash/erase/format/saveenv/setenv (only eMMC READS via imgread, RAM writes
via download).

## setup notes (repro)

stock `fastboot` CLI filters `download` (only via flash, banned) and validates
`set_active` args locally, so both go through tools/fb_raw.py (pyusb, sends
exact wire bytes). one sharp edge found: fb_raw MUST NOT call
SET_CONFIGURATION when one is already active — redundant reconfig wedges this
2015.01 gadget (recovered once via USB port reset, no device impact).
fixed in fb_raw.py (get_active_configuration first). `adb reboot fastboot`
lands in U-Boot fastboot (version-bootloader 2015.01-g7ac5df7677-dirty,
unlocked yes, secure no, max-download-size 0x08000000), per user instruction
(no `reboot bootloader` used anywhere this session).

## evidence (one device, aquaman, Android 9, orange)

E1 control raw-download + `set_active:;bootm 0x10200000` -> FAILset slot
error in 0.0s, stays in fastboot, answers getvar. sink works; INVALID dies
pre-GO as predicted (inspector said INVALID).
E2 `set_active:;printenv loadaddr` -> OKAY. `;echo hello` -> OKAY.
Hush runs the SECOND command (return code propagates). sink fully proven,
RAM-only (argc=1 dies pre-storage, see reports/set-active-sink.md — still valid).
E3 `set_active:;bootm <0x63000000,0x6B000000,0x23000000,0x2B000000>` on fresh
stock-encrypted download -> all FAIL 0.0s. (candidates came from the
ddr_size_usable oracle: usable=DRAM-16M-BUF-64M-128M=128M with khadas
constants exact-fits BUF=0x23000000 for 1GB DRAM. all missed.)
E4 `set_active:;imgread kernel boot 0x1080000;bootm 0x1080000` -> USB dies,
Android boots (adb, MemTotal 1004412 kB = 1GB box). normal flow works via
sink; SMC+bootm+GO all functional in fastboot context.
E5 stock `fastboot boot boot.img` (download 16MB + boot) -> USB dies in ~1s
("Status read failed"), adb in ~20s, fresh boot. bootm(Y) works.
E6 same rails, raw-'boot' (no download, Y=decrypted-stale) minutes earlier
-> FAIL fast, stayed. SAME Y, SAME bootm, different outcome than E5.
the download CHANGED what bootm(Y) read => download buffer OVERLAPS Y
=> download overlaps Y (==loadaddr region 0x1080000 per reference tree, ODROID-C2 style), not 0x10200000. Exact BUF==Y remains unproven; overlap is what E5/E6 show.
E7 `fastboot boot m1b_boot.img` (plaintext, 4KB) -> adb ~18s, empty
bootreason. `fastboot boot m1_boot.img` -> adb ~17s. INVALID 4KB control ->
adb ~16s. A/B/control identical => all three die the same pre-GO death.
fresh plaintext at Y + same rails as E5-success => SMC rejects plaintext
=> SECURE-FUSED (getvar secure:no reflects lock state, not the fuse;
orange=unlocked flashing coexists with fused verify).
E8 `set_active:;booti` (ep defaults to loadaddr=Y) on Y=m1b-raw-stub
(valid ARM64 Image, magic+text_offset verified offline) -> FAIL 0.0s.
`set_active:;go 0x1080000` on same bytes -> FAIL 0.0s. both would have
executed (no SMC on either path). instant return => commands ABSENT in
this build (CONFIG_CMD_BOOTI=1 exists only in the khadas ref, not proven
here; `help X` is a broken oracle — cmd_usage always returns 1,
common/command.c:139 — so absence is inferred from instant-FAIL on valid
input, same degeneracy noted and accepted).

## model (fits E1-E8 with one assumption)

Download overlaps the region `bootm` reads (reference `loadaddr 0x1080000`). Exact BUF value remains unknown
(`fastboot boot` was never buggy on this build). BL31 is secure-fused:
aml_sec_boot_check passes AMLSECU-signed bytes (E4,E5), fails plaintext
(E6 raw-boot,E7) and double-decrypt (E6). unsigned legs (M1/M2/raw) die in
SMC -> do_reset -> Android in ~16-18s with empty bootreason. no SMC bypass
is reachable: booti/go stripped, bootm always SMCs, imgread only stages
eMMC reads, autoscr would only re-run the same gated Hush set.

## consequences

- reports/fastboot-boot-verdict.md root-cause (X!=Y): RETIRED for this build.
  its verdict (nothing ever executed) STANDS, cause corrected to SMC/fused.
- reports/bootm-test-image.md gate analysis still describes the real
  validators, but the injection address must be 0x10800000 (==BUF), and the
  operative gate for unsigned images is the SMC, which the inspector cannot
  pass (offline tool limitation, now documented).
- custom-code-exec via fastboot on this box: BLOCKED at BL31. avenues left
  (all out of scope): signed repack (needs aml-user-key, refuted),
  USB-burning/pyamlboot (flash-risk), kernel/userspace exploit (new project).

## run log (T0 = boot/send, adb = Android back)

| run | path | result |
|---|---|---|
| control INVALID raw | sink bootm X | FAIL 0.0s, stayed |
| A m1 raw | sink bootm X | FAIL 0.0s, stayed |
| B m1b raw | sink bootm X | n/a (superseded) |
| stock boot.img | sink bootm X/Y/probes | FAIL 0.0s, stayed |
| imgread+bootm Y | sink 3-chain | BOOTED Android |
| stock `fastboot boot` | stock CLI | adb ~20s |
| m1b `fastboot boot` | stock CLI | adb ~18s, empty reason |
| m1a `fastboot boot` | stock CLI | adb ~17s, empty reason |
| INVALID `fastboot boot` | stock CLI | adb ~16s, empty reason |
| booti / go | sink | FAIL 0.0s (absent) |

device left healthy in Android, fresh boot, nothing persisted.
