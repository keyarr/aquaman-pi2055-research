# round30 / 04 — build reuse across PI.998 / PI.1241 / PI.1727 / PI.2055

Question: when artifacts of sibling builds exist, can we tell whether the
same key/package was reused across releases, or whether the key rotated?

## answer block

```text
sibling-build bootloader artifacts public (998/1241/1727)   NO
key-reuse determination                                     UNKNOWN (undeterminable in public)
bootloader.img per build                                    only PI.2055 exists (local)
build-identity table                                        below, from public strings only
```

## public build-identity table (strings, not artifacts)

From tweakradje's changelog (the only public place that records all four
builds with their kernel stamps):

```text
build     kernel stamp (public record)                          artifact public?
PI.998    4.9.113 #1 SMP PREEMPT Tue Feb 23 02:04:52 CST 2021   NO
PI.1241   4.9.113 #1 SMP PREEMPT Thu May 27 11:54:42 CST 2021   NO
PI.1727   4.9.113 #1 SMP PREEMPT Fri Dec 17 14:48:06 CST 2021   NO
PI.2055   4.9.113 #1 Tue Sep  6 12:53:43 CST 2022               LOCAL ONLY
          (same sublevel 4.9.113 across ALL releases; only the
           build timestamp moves)
```

Note the stamp format change between PI.1727 and PI.2055 (`SMP PREEMPT`
drops from the local-unversioned string in the 2022 record) — consistent
with the same tree rebuilt, no sublevel bump in 20 months of releases.

## the reuse question

The rule-5 table (build | bootloader hash | package hash | tail32 relation
| evidence) is **unfillable from public data**: not one sibling release's
bootloader or key package exists publicly. The only facts addable:

```text
build    | bootloader hash | package hash | tail32 relation | evidence
PI.998   | —               | —            | —               | none
PI.1241  | —               | —            | —               | none
PI.1727  | —               | —            | —               | none
PI.2055  | c7b8eea6… (local)| —           | —               | local file
```

Even the vendor-side reasoning cannot fill it: the aeskey is a build-time
file (round 29), so reuse-or-rotate is a pure OEM policy question. Industry
default is long-lived per-product keys (superbird's package, one product,
one vintage — is the same single example that exists), but for aquaman this
is UNDETERMINABLE, not assumed either way.

## what would answer it

A bootloader.img from ANY second release (any of 998/1241/1727), or the
dump of any sibling MiTV board of the same generation. Then:
same record128 across builds ⇒ same key; different record128 ⇒ rotated (or
re-branded); oracle cross-test closes it in one block. None exists today.
