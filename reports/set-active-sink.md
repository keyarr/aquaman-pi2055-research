# set_active sink — offline verification that `bootm X` is reached RAM-only

claim: `fastboot set_active:;bootm 0x10200000` is dispatched to
cb_set_active, builds the string `set_active_slot ;bootm 0x10200000`,
and Hush runs it as TWO commands. the first dies on argc before any
storage access; the second is a plain RAM-only bootm of the fresh
download buffer. no flash/env/misc write happens on this path.

## 1. dispatch reaches cb_set_active (prefix match)

rx_handler_command matches `strncmp(cmd, buf, strlen(cmd))`
(drivers/usb/gadget/f_fastboot.c:389-394 strcmp_l1, used at :760).
registered cmd is "set_active" (f_fastboot.c:748-750). any buffer
starting with those 10 bytes matches — including
`set_active:;bootm 0x10200000`. so the injection is routed to
cb_set_active, not rejected as unknown command. (there is no `oem run`
handler anywhere in this tree, and no fastboot_bootcmd; this is the
only run_command sink reachable from fastboot.)

## 2. strsep leaves the payload intact

cb_set_active (f_fastboot.c:625-648):
- :627 cmd = req->buf = "set_active:;bootm 0x10200000"
- :633 strsep(&cmd, ":") splits at the FIRST colon: token "set_active"
  discarded, cmd now points at ";bootm 0x10200000" (everything after
  the colon, semicolon included — strsep never strips ';').
- :634-638 if (!cmd) guard: our cmd is non-empty, passes.
- :640 sprintf(str, "set_active_slot %s", cmd) with char str[128]
  (:630) → "set_active_slot ;bootm 0x10200000" (33 bytes, fits; no
  overflow with this fixed short string).
- :642 run_command(str, 0). return value only selects the OKAY/FAIL
  reply (:644-647); the second command already ran by then.

## 3. Hush splits on ';' and runs both (failure does not stop SEQ)

run_command → parse_string_outer(cmd, FLAG_PARSE_SEMICOLON |
FLAG_EXIT_FROM_LOOP) (common/cli.c:27-45, flags at :39).
';' tokenizes as done_word + done_pipe(PIPE_SEQ)
(common/cli_hush.c:3044-3047). run_list_real executes every PIPE_SEQ
element in order (cli_hush.c:1777+ loop via run_pipe_real at :1854);
only PIPE_AND/PIPE_OR short-circuit on rcode (:1897-1899). ';' never
skips. last_return_code records failure (:1886) but the loop continues.
so `set_active_slot` failing does NOT prevent `bootm 0x10200000`.

## 4. first command dies before touching storage (RAM-only proof)

do_SetActiveSlot (common/cmd_bootctl.c:268-314):
- :278-281 prints argv (serial only).
- :283-285 `if (argc != 2) return cmd_usage(cmdtp);`
  our argv = ["set_active_slot"] → argc=1 → returns here.
- storage access starts at :287 boot_info_open_partition (which does
  store_read_ops on "misc" at :187-191) and ends at :311
  boot_info_save → store_write_ops (:211). NEITHER is reached.
  cmd_usage itself just prints usage (common/command.c:124). no
  setenv runs either (:297-305 are after the gate).
hence the sink is RAM-only: zero eMMC/misc/env writes on the argc=1
path. the misc partition is never opened, let alone written.

## 5. second command is plain `bootm 0x10200000`

Hush argv for it: ["bootm", "0x10200000"] → do_bootm parses argv[0] as
number (common/cmd_bootm.c:135-140) → nLoadAddr=0x10200000 → SMC window
check → do_bootm_states on the FRESH bytes at X (see
reports/bootm-test-image.md §1). this bypasses do_bootm_on_complete's
stale load_addr (f_fastboot.c:576) entirely — and `fastboot boot` is
never issued, so the broken default path stays out of the picture.

## 6. residual risks (all accepted, none blocking)

- trailing-response semantics: cb_set_active replies FAIL (ret=1 from
  cmd_usage) AFTER both commands ran; host sees FAIL even on success —
  expected, ignore the reply, watch the clock instead.
- bootm failure (e.g. secure-fused SMC reject) → do_reset path inside
  the normal boot flow, same as any bad image: device reboots to
  Android, nothing persisted. timing baseline (§7 of test plan)
  distinguishes this from execution.
- str[128] sprintf is unbounded in general, but OUR string is 33 bytes.
  no stack smash from this test.
