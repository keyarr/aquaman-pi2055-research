# round61: BL31 plaintext via keyman blobs, and the A113X EL3 port

Date: 2026-11-19. Answer the hypothesis, not fact. No line of
`CURRENT_STATE.md` was promoted. The only reset was the `adb reboot fastboot`
prescribed as entry; no `optimus_reboot.py`. No write commands: no
`keyman write`, `flash`, `erase`, `saveenv`, `efuse`, BootROM, `RUN_IN_ADDR`,
`MODIFY`, `setenv`, `bootm`.

## One-line verdict

The hypothesis died in Phase B. The keyman blobs are not AES key material for
`bootloader.img` or `boot.img`. Without plaintext there is no BL31 to open, so
Phase C was not executed. The 0x69 id of this build is scalar, not a parse entry
point. The published chain has nowhere to enter here.

## Phase A - collection (device, read-only)

Entry: `adb reboot fastboot`, `fastboot oem update 5000`, `1b8e:c003` stage 16
(identify `00 07 00 10`). Baseline and `false`/`true` oracle PASS before and
after the whole session. Tool: `tools/round61_keyman_collect.py`, log
`/tmp/round61-collect-all.log`.

Method: for each DTS name, `keyman read <nome> <dest>` with host-chosen
destination at `0x20000000 + 0x1000*i`, MREAD before and after of 0x400 bytes at
the same destination. The changed prefix is the blob; the size comes from the
secure world and does not return over USB, so it is recovered by differential
read, not guessed.

Result: 16 of 19 reads returned `failed:` (no byte written to the destination).
Three returned `success`:

| name | len | sha256 | initial bytes |
| ---- | --- | ------ | ------------- |
| sn2 | 0x22 (34) | `695c40bba8639ee816d828dd9b1cff09ae38d6735a2d69019ba83676306ee63e` | `33 32 33 36 33 39 33 31 ...` (ASCII hex) |
| bt_rc_mac | 0x12 (18) | `c96f02a209ae0e8ac3b0a6737cb510da7967e22d3f887e9e501b2d44241627b4` | `31 34 3a 41 42 3a 35 36 ...` (MAC ASCII `14:AB:56:E8:32:DB;`) |
| netflix_mgkid | 0x6e (110) | `086b286f180c5ca1286d5934e8dc2840d297087e28ed77ef6c0a24d85e203098` | `4e 46 41 4e 44 52 4f 49 44 ...` (`NFANDROID2-PRV-AQUAMAN-MGK000000...`) |

The remaining 16, with the empty blob sha256 (`e3b0c442...b855`), were:
`sn1`, `hdcp`, `secure_boot_set`, `mn1`, `mn2`, `hdcp2_rx`, `mac_bt`, `mac`,
`mac_wifi`, `widevinekeybox`, `hdcp22_fw_private`, `PlayReadykeybox25`,
`prpubkeybox`, `prprivkeybox`, `attestationkeybox`, `region`.
`secure_boot_set` is refused by a name gate, consistent with
`round24-key-surface/01`.

Phase A conclusion: there is no 32-byte binary blob among the 19.
`unifykey-num=0x13` is live (`[0x37f5e5e8]=0x13`, array at `0x33e35fc0`) and
sharemem is ready (`[0x37fbde50]=1`, IN `0x05000000`, OUT `0x05040000`). The
failure of the 16 is not local initialization: it is the secure world not
returning a blob for these names in this build/mode.

## Phase B - offline key search (stop, no hit)

Tool: `tools/round61_keysearch.py`; output `/tmp/round61-keysearch.log`.
9 candidates, 90 tests, 0 hits.

Candidates per blob, exactly as requested: `key=blob` (or `blob[:32]` /
zero-pad when size is not 0x20), `key=SHA256(blob)`, and the pair
`key=blob[0:0x20]`, `iv=blob[0x20:0x30]` (`key_info` layout from
`round28-fip/05`). Crossed with the reference tail32 of
`round29-bootloader-crypto` sec 3, which is direct key material, not derived
from efuse.

Targets and windows: `firmware/bootloader.img` `0x0000` (stage1 `--bl2enc`),
`0xC000` (header `--bootmk`, where the ToC lives), `0x20000` (BL31 stream);
`firmware/boot.img` `0x800` (amlKernel) and `0x959800` (amlDTB), offsets read
from `parse_amlsecu.py`. For each window: AES-256-CBC with the candidate IV and
1-block ECB (zero IV), checking `@AML`, `AMLSECU!`, `AMLC`, `ARMd`, `ANDROID!`,
FDT, BL31 header and FIP prefix `01 00 64 aa 78 56 34 12`, plus size coherence
with the header.

Discarded candidates (sha256 of effective key):

| candidate | key sha256 | IV |
| --------- | ---------- | -- |
| `bt_rc_mac:blob+zeropad` | `b62aef684a4671a731c8cd528877d49a7a0d8ba48eee6b6779e469b435e8a56e` | 0 |
| `bt_rc_mac:sha256` | `b3e0650d3e4a26468b771167c24b1e940cd8147f3e325b35a96251bc0b9090f0` | 0 |
| `netflix_mgkid:blob[:32]` | `85869dd67d93d358a068ad4f502177e6307e327e5a60a41f185f996c81f68206` | 0 |
| `netflix_mgkid:sha256` | `9ef11b1e42f753fe3fd7e6ac42d42308fd6bd3e9c704b145f1424ce973edaf20` | 0 |
| `netflix_mgkid:key_info` | `85869dd67d93d358a068ad4f502177e6307e327e5a60a41f185f996c81f68206` | `30383033373633392c5a735651616d4a` |
| `sn2:blob[:32]` | `38412aeef9e670a2b39eb46011087934ea10cfc4fb8b69a2037cd15bf9cf4f91` | 0 |
| `sn2:sha256` | `600799647a66fa90cc0a91ae84df520e170db7042b32174242bce328b361984d` | 0 |
| `ref_tail32:direct` | `6bf6bbd660a0ffee64a3e03d1d88340adb4a8e2e935b555ca5dd371e7e9ffab3` | 0 |
| `ref_tail32:sha256` | `9c074260c4be2ab01293ffa33e24a378fa4e961346430e27bef4a0d32f51af43` | 0 |

Example, BL31 CBC stream: no candidate produced magic; the first blocks were
`13 cc 70 64 ...`, `b7 fb a3 51 ...`, `62 89 05 cf ...`,
`63 40 61 3a ...`, `52 b1 35 fc ...`, `88 d6 4b c6 ...`,
`80 1a 45 1d ...`, `c8 c6 57 09 ...`, `10 38 14 9a ...`.

This does not contradict `round29`: the aquaman tail32 is a build file the OEM
did not ship. The test only shows that the DTS blobs are not that file and are
not derived from it.

## Phase C - not executed (no plaintext)

There is no BL31 plaintext, hence no plaintext sha256, header bytes, VAs of
`g_platform_ops`/`g_keys`/`g_data_chunks_head` nor `platform_ops` table to
document. No ATF source was downloaded: `.src/` contains only `linux-amlogic`,
`MiTV_OpenSource` and `u-boot-khadas`, without `arm-trusted-firmware`; finding a
GXL reference without the target binary does not allow binary diffing. The
A113X binary from the internet was not used as ground truth for addresses.

Answer that the existing material allows about the parse id: **in this build
there is no demonstrable host-callable parse entry point, and 0x69 is scalar**.
`round22-storage-reachability/04` proves that the wrapper `0x37e8bcfc` does
`mov w2,w1; mov w1,w0; x0=0x69; b stub`, with a single caller `0x37e8c2a0`
inside `amlkey_init-ish 0x37e8c1dc` (init time, no sharemem).
`round59-el3-arbitrary-access/01` classifies `0x69/0x6a` as NOTIFY_EX/SET_ENCTYPE,
X0=id, X1=value, no host address. The id census in
`round14-bl33-persist/19_id_census.txt` records 1 site of `0x82000069`. That is:
the `parse_param_sector` of the A113X exploit is not reachable by any BL33
command mapped here. This is evidence from the BL33 side; the EL3 handler was
not audited and there is no basis to state what 0x69 does inside it.

## Phase D - offline prediction

Generator: `tools/round61_port_predict.py`. Modes `generate` and `plan` work
without a device; `run` refuses and does not open USB.

Blob C1 at `0x05000000`: exact-Aquaman framing from `round23-keyman/04`
(`u32 namelen`, `u32 datalen`, `u32 flags=0`, name, data) with 65 entries of 0x20
bytes; the index-64 entry carries `value_ptr=0x37800800` and len 0x10. Total
size 0x82f, sha256
`f73e9ad9af778b2633e8a428b6030bebe0e5fd2228e0f8e645e56bc6df2a7fbe`.
The internal `key_entry` layout (stride 0x20, value_ptr at +8, len at +0x10) is
copied from the public A113X description and is marked NOT VERIFIED in the code
and in `plan`. It is not aquaman ground truth.

Predicted sequence, with real aquaman addresses:
`0x82000069` via `0x37e8bcfc` (scalar), `0x82000062` via `0x37e8bd10` with
C1 `0x05000000` / C2 `0x05040000`, and `0x820000ff` via `0x37e19ea8`
(X0=id, X1=cmd, X2=buf, X3=len, X4=opt). Also recorded: BLOCK `0x05080000`,
size `0x40000`, sharemem flag `0x37fbde50` and the bare stub `0x37e8bba0`. The
generated stub is 52 bytes, sha256
`2654db83e8a141a49f18e8f8db7ba09cc62a0db9523c6a2b7de3c176766f4a75`.

Cheap discriminator: sentinel at `0x37800800`, MREAD-visible page separate from
the stub at `0x37800000`. MREAD before and after; a change in the 16 bytes proves
there was an EL3 write to host-chosen non-Secure RAM. It is a harmless target
(scratch RAM, no flash/efuse/env/boot), no brick risk.

**Execution on device is NOT proposed.** The sentinel oracle is usable, but
there is no premise to test: 0x69 is scalar in this build, the parse handler was
not located and `g_platform_ops` has no known VA. Running the sequence would
only measure a write with no known trigger path. Phase A wrote nothing; neither
does this generator.

## Outstanding items

- Aquaman AES-256 key material remains absent; the only legitimate route is the
  OEM-side `aml-user-key.sig` package (`round29/07`).
- If that package appears, Phase C can be resumed with BL31 plaintext and only
  then do binary diffing of SIP dispatcher, `parse_storage`,
  `smc_storage_read/write`, `set_platform_ops`, `g_platform_ops`, `g_keys`,
  `g_data_chunks_head` and share memory constants.
- No CBC oracle test on the SMC (observations sec 4) was done in this round.
