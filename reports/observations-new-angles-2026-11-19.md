# Observations: angles not covered by the current state

Date: 2026-11-19. Observations only. None of them has been executed, none
changes `CURRENT_STATE.md`. The operational plan for the main shortcut is in
`plan-smc-gate-neutralize-magisk.md`.

## 2. Dump the plaintext kernel before any boot

The same execution primitive in BL33 that enables the SMC patch has a second
use: call the wrapper `0x37e19ea8` with the site 1 args (`x0=0x40`,
`x1=0x1080000`, `x2=0x1800000`, `x3=7`) on the stock container in RAM, **without**
issuing the `eret`, and read the result with `MREAD 0x02`.

What this would deliver, which does not exist in the repo today:

- exact kernel image, with offsets for `commit_creds`, `prepare_kernel_cred`,
  `rt_mutex_waiter`, `pi_state`, and ROP gadgets;
- decrypted ramdisk;
- post-decrypt DTB (the `artifacts/aquaman.dtb` and the pre-fixup blob at
  `0x01000000`, without `/chosen`).

KASLR is the declared bottleneck of the GhostLock track (`CONFIG_RANDOMIZE_BASE=y`,
39-bit VA, `%pK`). With the exact image the slide is still necessary, but
guessing the structure from the McMCCRU is no longer needed. Even if the SMC
patch fails, this observation unblocks the kernel track.

Status: dependent on Phase 1 of the plan. OFFLINE_ONLY.

## 3. The keyman blobs as the AMLSECU AES key

`key-surface-round24.md` mapped 19 DTS keys, 18 readable via
`keyman read <name> <addr>` with a destination in host-chosen RAM and readback
via `MREAD`. The text explicitly says that the meaning of the bytes on the
secure side is UNPROVEN. That is: it was never tested whether any of these
blobs is the AES-256 key for `--imgsig`.

The test is offline and cheap after a collection session: for each of the 18
blobs, try it as a direct key, as `SHA256(blob)`, and as a pair
`(key=blob[0:0x20], iv=blob[0x20:0x30])`, which is the `key_info` layout of
`aml_encrypt_gxl` (`round28-fip/05-decrypt-pipeline.md`). Decrypt only the first
block of `boot.img` and check for the ARM64 magic / `ANDROID!`.

If any candidate matches, the kernel/ramdisk plaintext appears with no code
execution in BL33 and without touching the SMC. Cost: one read session plus
seconds of CPU.

Status: not attempted. OFFLINE_ONLY.

## 4. CBC oracle at the SMC

The repo records that the gate returns the same timing for plaintext and for
garbage. That compares **different inputs**. The relevant case was not tested:
take a valid signed container, change 1 byte of a ciphertext block, and measure
whether the rejection changes (error string, USB disconnect timing, bootreason).

If there is any difference dependent on the decrypted plaintext, even if it is
only "header accepted vs. header rejected", there is a padding/format oracle.
With chosen-ciphertext it is possible to recover the plaintext of `boot.img`
byte by byte without the key. The gate uses AES-256-CBC (`aml_file_aes`), which
makes the hypothesis structurally plausible.

Probing cost: 2 or 3 boots with flips at different positions in the container,
comparing the 15-21 s rejection band and the `reboot,fareboot`. Low cost, high
asymmetry if the oracle exists.

Status: not attempted. Speculative.

## 5. The whole-string revert and the bootm rebuild

The trace `round55-fdt-identity-chain/bootm_37e24c00.txt` shows two facts that
the current text does not highlight:

- at `0x37e24dc0`, bootm calls **the same `env_get("bootargs")`** that rounds
  51/52 proved reads the htab;
- the rebuild at `0x37e24e64` is `snprintf` with `%s %s %s` + `verifiedbootstate`,
  followed by `setenv`. It is an append, not a replacement.

Consequence: "bootm rewrote bootargs from scratch" is ruled out also by direct
disasm, and the marker enters the rebuilt value. This increases the value of
the already-planned experiment E1 (`fdt chosen` in a scratch blob + `MREAD`):

- marker present in the blob -> the loss is downstream of `fdt_chosen`;
- marker absent -> the htab read by the diagnosis is not the one `env_get`
  returns at bootm time, which would point to an intermediate `setenv`
  relocating the entry (the entry 262 pointer has already been seen moving
  between rebuilds).

This is not a new closed hypothesis. It is a reframing of the discrimination
point: the experiment remains the cheapest and the only one that does not
require boot.

Status: OFFLINE_ONLY, consistent with `CURRENT_STATE.md`.
