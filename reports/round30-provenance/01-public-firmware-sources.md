# round30 / 01 — public firmware sources for the exact PI.2055 build

Question: does the exact MiTV-AESP0 / aquaman PI.2055 build exist in public
as a downloadable artifact (OTA zip, dump, mirror, archive)?

## answer block

```text
exact PI.2055 OTA zip public            NO
exact PI.2055 eMMC/bootloader dump public NO
exact build tree public                 NO (dumps.tadiphone tree DEAD live+archive)
nearest public artifacts                this repo's own OTA-payload set
exact bootloader.img sha256 (local)     c7b8eea624f2931cd5d78a513dff407b3ccde4f42202763b32b4758551ef3424
size                                    0x148200 = 1344000
```

## the local artifact set (the reference point)

The repo already carries the PI.2055 OTA payload set, unpacked from the
device's own OTA dumps (README: "the 28 stock .ko, extracted from the OTA
dumps in this repo"). These sha256s are the ground truth any candidate must
match:

```text
7797e3dfbaa403167a8bc5105e239f124d94b8bbcdf34378d582d1b7fc000aad  boot.img
c7b8eea624f2931cd5d78a513dff407b3ccde4f42202763b32b4758551ef3424  bootloader.img
e20992ee200bb608f2ac79e5c63d9b328edbdb906d02a9ac23cd9bec9cda3245  dtbo.img
ea2f4c6523859b1c2b56c14847392ef7900af1e0ce3fdead02411089655a5993  dt.img
7af715b127950b7aa240bfd29245e795c473b201252014875f6996d4de768a2b  vbmeta.img
```

`bootloader.img` == `firmware/bootloader.img` (cmp: identical), 0x148200,
matches every round-28/29 measurement.

## sources searched (all negative for an exact-artifact URL)

| source | result |
|---|---|
| Google (deep): `aquaman PI.2055 zip download` | no archive hit for `aquaman_9_PI_2055.zip`; the filename exists only as a Reddit/XDA reference |
| tweakradje site | confirms build string `PI.2055 release-keys (4.9.113 #1 Tue sep 6 12:53:43 CST 2022)` (received 09 mar 2023, 738 MB) — corroborates the BUILD IDENTITY, "ROM files here" links are Google-sites JS hrefs, no direct URL extractable |
| 4pda topic 998811 | device discussion, PI.2055 mentioned; attachments require forum account; no direct mirror surfaced |
| dumps.tadiphone.dev `/dumps/xiaomi/aquaman` | **"No repository — the repository for this project does not exist"** (live, 2026-09-30) |
| Wayback of the same tree (2026-08-13 snapshot) | **same "No repository" page** — tree was already gone at archive time |
| Telegram @android_dumps | posts exist for `Xiaomi/aquaman/aquaman:9/PI/2055:user/release-keys` with "Git link" (pages 6888/6915/6955 window); the linked tree is the tadiphone repo above = dead |
| GitHub repo search `aquaman xiaomi` | 0 results (API) |
| GitHub `androiddumps/aquaman` | 404 |
| mifirm.net | 404 for mi-tv-stick model page |
| postmarketOS wiki (aquaman) | behind anti-bot; cached snippets only say "no known methods to boot pmOS; stock u-boot can only boot signed images" |
| HalabTech "Mi TV Stick - Firmware" index | paywalled/download-gated, no verifiable artifact visible |
| XDA 4686779 "Seeking U-Boot File for aquaman MDZ-24-AA" (2024) | the same hunt, open since 2024, 403 to fetcher — i.e. the community never landed the artifact either |

## the dts/dtb note (user-confirmed)

The nearest thing to a public "tree" for this build is the **runtime DTB
recovered from RAM** (this repo: `artifacts/aquaman.dtb`, + .dts, from the
round-9 extraction). A mainline patch series also carries an aquaman DTS
(gbmc/6.16 changelog hit), which is upstream-mainline material, not the
Xiaomi 2022 vendor tree. No Xiaomi 2022 kernel/U-Boot source for aquaman is
published anywhere (matches reports/provenance.md verdict).

## classification

```text
OTA payload files (boot/dt/dtbo/vbmeta/bootloader): available LOCALLY,
    origin = device-side dump, hashes pinned above
public copy of the exact OTA zip: NOT FOUND
public copy of the exact bootloader.img: NOT FOUND (only the local one)
build tree: DEAD (tadiphone "No repository", live + Wayback)
```

No artifact found ⇒ no public sha256 comparison is possible this round.
The match class for every external candidate would be UNKNOWN by
construction (no candidate exists to hash).
