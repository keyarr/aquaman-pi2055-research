# round24-key-surface 03: backend resolution (key -> vector -> impl)

vectors dumped this round (file qwords, link-time constants):

```text
0x37f5e478 (secure/normal), flag +0x38 = 1:
+0x00 0x37e75e44  init
+0x08 0x37e75e74  stub (mov w0,#0; ret)
+0x10 0x37e75e7c  keymanage_secukey_write (-> bl 0x37e8c450 amlkey_write, SMC 0x62 + VERIFY 0x64)
+0x18 0x37e76078  b -> 0x37e8c374 (-> 0x37e8bfe0, SMC TELL 0x63)
+0x20 0x37e7607c  b -> 0x37e8c2ec (-> 0x37e8be98, SMC QUERY 0x60)
+0x28 0x37e76080  exist-bool (bl 0x37e8c35c, cset)
+0x30 0x37e7609c  keymanage_secukey_read (-> bl 0x37e8c3e4 amlkey_read, SMC 0x61)
+0x38 0x00000001  skip exist gate on write

0x37f5e4b8 (efuse), flag +0x38 = 0:
+0x00 0x37e76154  init
+0x08 0x37e761e8  stub
+0x10 0x37e761f0  efuse write (strcmp secure_boot_set -> setenv else bl 0x37e72ca4)
+0x18 0x37e76268  size (-> 0x37e72c40 DTS cfg size)
+0x20 0x37e7637c  exist (strcmp secure_boot_set branch)
+0x28 0x37e762cc  exist-negation (strcmp secure_boot_set, cset ne)
+0x30 0x37e762f4  efuse read (-> 0x37e72d98 backend, size check b.hi 0x97)
+0x38 0x00000000  run exist gate on write
```

dispatch (re-disassembled):

```text
device_write 0x37e73880: x20=bl 0x37e73380(name); cbz->0x107;
  ldr w0,[x20,#0x38]; cbnz->[x20,#0x10] blr (secure direct);
  else [x20,#0x20] blr exist gate (efuse), cbz-ok else 0x10f, then [+0x10] blr.
device_read 0x37e7394c: x20=bl 0x37e73380; cbz->0x128;
  [x20,#0x20] blr (query/exist) else 0x12e; [x20,#0x28] blr else 0x134;
  [x20,#0x18] blr -> len; cmp len,w21 else 0x13a (unless expected==0);
  [x20,#0x30] blr (real read).
len_lookup 0x37e73aa0: same lookup, [+0x28] gate (0x150 on fail), [+0x18] size.
```

## 3.1 per-key resolution

```text
key -> class -> 0x37e73380 -> vector -> blr slot -> impl -> class tag
sn1            3 -> 0x37f5e478 -> read[+0x30]/write[+0x10] -> 0x37e7609c/0x37e75e7c -> normal generic
sn2            3 -> 0x37f5e478 -> same -> same -> normal generic
hdcp           2 -> 0x37f5e478 -> same -> same -> secure generic (sha1-typed)
secure_boot_set 1 -> 0x37f5e4b8 -> read[+0x30]->0x37e762f4 (refused by [+0x28] gate) /
                                          write[+0x10]->0x37e761f0 (diverted) -> efuse (special-cased)
mn1,mn2        3 -> 0x37f5e478 -> 0x37e7609c/0x37e75e7c -> normal generic
hdcp2_rx       3 -> 0x37f5e478 -> same -> normal generic (raw; hdcp2 TYPE id not involved)
mac_bt/mac/mac_wifi 1 -> 0x37f5e4b8 -> 0x37e762f4/0x37e761f0 -> efuse
widevinekeybox, hdcp22_fw_private, PlayReadykeybox25, prpubkeybox, prprivkeybox,
  attestationkeybox  2 -> 0x37f5e478 -> 0x37e7609c/0x37e75e7c -> secure generic
bt_rc_mac, netflix_mgkid, region  3 -> 0x37f5e478 -> same -> normal generic
```

no key resolves to UNKNOWN: every DTS device string maps to 1/2/3, every
class maps to a dumped vector, every blr slot holds an in-image function.
the only special handling is `secure_boot_set` (strcmp in all three efuse
slots) and the mac/sha1 validators upstream of the vector (type_resolve
`0x37e7414c` + jump table `@0x37ebea34`: mac `0x37e743d8`, sha1
`0x37e74668`, hdcp2 `0x37e74790`, raw `0x37e74840`).

## 3.2 proof notes (this round)

* `0x37e7609c` calls `bl 0x37e8c3e4` (amlkey_read) after exist gate;
  `0x37e75e7c` calls `bl 0x37e8c450` (amlkey_write) + verify. so the generic
  path reaches SMC 0x61/0x62 through one blr hop + one direct bl. the
  round23 wording "generic hop never touches amlkey" is REFUTED at the
  implementation level; dispatch is still runtime-selected.
* `0x37e762f4` tail-branches `b 0x37e72d98` (efuse backend) after
  `bl 0x37e76268` size check; `0x37e761f0` branches to `0x37e72ca4`
  except for the `secure_boot_set` setenv divert. disasm above.
* type list `@0x37eb5058` = `{mac@0x37ebf6e2, sha1@0x37ed1722,
  hdcp2@0x37ed72f7, raw@0x37ed793c}`; raw+name overrides
  (`mac/mac_bt/mac_wifi->0`, `hdcp2->2` via csel `@0x37e74260`) verified.
  on this DTS the `hdcp2` override never fires (no key named `hdcp2`).

classification summary: secure generic 7 keys, normal generic 8 keys,
efuse 3 keys + 1 diverted, HDCP2 special 0 DTS keys, unknown 0.
