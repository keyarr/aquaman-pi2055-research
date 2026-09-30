# round30 / 02 — exact build matching: local artifact vs public artifacts

Question: can any public bootloader.bin/img be compared byte-wise against
the local `bootloader.img` (sha256 c7b8eea6…, 0x148200)?

## answer block

```text
public bootloader candidates found      0
EXACT MATCH                             n/a (no candidate)
SAME BUILD / DIFFERENT WRAPPER          n/a
DIFFERENT BUILD                         n/a
UNKNOWN                                 n/a
comparison performed                    NO — impossible without a candidate
```

## what the brief asked for, and what a candidate WOULD have been compared on

Prepared comparison protocol (kept here so a future candidate can be run
through it mechanically):

```text
1  size                      == 0x148200?
2  sha256                    == c7b8eea624f2931cd5d78a513dff407b3ccde4f42202763b32b4758551ef3424?
3  first/last 0x4000         byte-wise vs local
4  record128                 128B record at 0xC080/0x10080/0x20080/0x4C080/0x8C080
                             identical at all five sites, and equal to the local record?
5  stream offsets            0xC000 / 0x10000 / 0x20000 / 0x4C000 / 0x8C000 present,
                             0x8C000+0xBC200 == size
6  ctrl-copy / plaintext     no AMLC at 0xC00C/0xFE00+0x0C plaintext, no 0x12348765,
                             no LZ4C, chi2 uniform
7  metadata                  vendor date strings, "AMLG", build stamps in the
                             first 0x4000
```

Classes:

```text
EXACT MATCH                 same sha256 (or same size + all seven structural pins)
SAME BUILD / DIFF WRAPPER   record128 equal + stream map equal, wrapper differs
DIFFERENT BUILD             anything structurally divergent
UNKNOWN                     cannot hash (URL dead, paywall, no file)
```

## outcome

The 01 sweep found **zero** downloadable bootloader artifacts for aquaman
in any public location (OTA mirrors dead, tadiphone dump tree dead live and
archived, eMMC dumps not public, XDA/U-Boot request thread from 2024 still
unresolved). There was literally no candidate to hash.

Corollary that matters for the key question: the artifact that would
re-enter the round-28/29 pipeline (a second copy of the exact bootloader
ciphertext) also does not exist publicly. The only existing copy of the
ciphertext remains the one in this repo.
