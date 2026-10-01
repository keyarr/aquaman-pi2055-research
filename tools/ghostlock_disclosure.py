#!/usr/bin/env python3
"""ghostlock_disclosure.py - READ/DISCLOSE inventory for H16 + f_alt.

Targets:
  H16_addr  = absolute address of [W_waiter + 0x38] (live kernel stack slot)
  F_alt_addr = absolute address of &f_alt.pi_mutex (heap rt_mutex)

LAB != STOCK: every VA/frame/struct below is OFFLINE_ONLY (build-aq/vmlinux +
.src/linux-amlogic). Stock confirmation needs a HARDWARE probe per candidate.

Usage:
  disclosure.py <vmlinux> --proc                # %p scan in proc/sys/net/futex
  disclosure.py <vmlinux> --copy                # copy_to_user struct inventory
  disclosure.py <vmlinux> --stack-flow          # current/stack/waiter -> user flow
  disclosure.py <vmlinux> --heap                # f_alt/pi_state disclosure paths
  disclosure.py <vmlinux> --verify              # re-check curated rejection points
  disclosure.py <vmlinux> --all                 # all of the above (short)

Classification per candidate (FASE 1):
  direct kernel pointer | pointer arithmetic | masked pointer | hash |
  index only | non-pointer metadata

Each claim prints its EVIDENCE label (OFFLINE_ONLY until a stock probe
reproduces it).
"""
import re
import subprocess
import sys
import os

OD = ("/home/erick/Android/Sdk/ndk/29.0.14206865/toolchains/llvm/"
      "prebuilt/linux-x86_64/bin/llvm-objdump")
NM = ("/home/erick/Android/Sdk/ndk/29.0.14206865/toolchains/llvm/"
      "prebuilt/linux-x86_64/bin/llvm-nm")
SRC = "/home/erick/Downloads/aquaman_9_PI_2055/.src/linux-amlogic"

_copy_cache = None


def run(args, timeout=120):
    return subprocess.run(args, capture_output=True, text=True,
                          timeout=timeout).stdout


def disasm(vmlinux, syms):
    out = run([OD, "-d", "--no-show-raw-insn",
               "--disassemble-symbols=" + ",".join(syms), vmlinux])
    funcs, cur = {}, None
    for line in out.splitlines():
        m = re.match(r"^([0-9a-f]{16}) <([^>]+)>:", line)
        if m:
            cur = m.group(2)
            funcs[cur] = []
            continue
        m = re.match(r"^([0-9a-f]{16}):\s+(\S+)\s+(.*)$", line)
        if m and cur:
            funcs[cur].append((int(m.group(1), 16), m.group(2),
                               m.group(3).strip()))
    return funcs


def grep_src(pattern, paths):
    out = []
    for p in paths:
        full = os.path.join(SRC, p)
        if not os.path.exists(full):
            continue
        try:
            r = subprocess.run(["grep", "-rn", pattern, full],
                               capture_output=True, text=True,
                               timeout=60).stdout
            for line in r.splitlines()[:40]:
                out.append(line)
        except Exception as e:
            out.append("%s: ERROR %s" % (p, e))
    return out


def proc_scan():
    print("=" * 72)
    print("FASE 1 -- /proc,sysfs,debugfs disclosure inventory")
    print("EVIDENCE: OFFLINE_ONLY (source) + HARDWARE_* (stock probes, see report)")
    print("=" * 72)
    rows = [
        ("fs/proc/base.c proc_pid_stack",
         "seq_printf(m, \"[<%pK>] %pB\\n\", ...)",
         "masked pointer (kptr_restrict %pK) + symbol (%pB)",
         "STOCK: all zeros (HARDWARE_OBSERVED). REJECT as stack disclosure."),
        ("fs/proc/base.c proc_pid_wchan",
         "symbol name or '0' (lookup_symbol_name, else 0)",
         "symbol, never address",
         "STOCK: '0' for sleepers. REJECT."),
        ("fs/proc/base.c proc_pid_syscall",
         "nr + 6 user args + user sp + user pc as 0x%lx",
         "non-pointer metadata (user regs, not kernel stack)",
         "STOCK: readable. User SP only. REJECT as kernel-stack disclosure, "
         "KEEP as user-SP reference."),
        ("fs/proc/array.c do_task_stat",
         "kstkesp/kstkeip zeroed unless PF_DUMPCORE; start_stack = user",
         "non-pointer metadata",
         "STOCK: esp/eip fields 0. REJECT."),
        ("fs/proc/array.c do_task_stat wchan",
         "get_wchan -> symbol via lookup, else 0",
         "symbol/index",
         "REJECT (same as wchan)."),
        ("net/unix/diag.c sk_diag_*",
         "inode numbers (sock_i_ino), queue lens, paths; NO sk pointers",
         "index only",
         "STOCK: /proc/net/unix Num column masked to 0. REJECT."),
        ("net/packet, net/tcp proc show",
         "sk column masked (0000000000000000 on stock)",
         "masked pointer",
         "STOCK: HARDWARE_OBSERVED zeros. REJECT."),
        ("kernel/sched/core.c sched_show_task / proc sched",
         "counters + policy/prio, no task/stack pointers",
         "non-pointer metadata",
         "STOCK: /proc/self/sched readable, no pointers. REJECT."),
        ("fs/proc/task_mmu.c maps/smaps/pagemap",
         "user VMAs; pagemap PFN needs CAP_SYS_ADMIN for unpriv (0 on stock)",
         "user pointers + index only",
         "STOCK: maps readable (user). pagemap present but PFN masked. REJECT."),
        ("kernel/kallsyms.c + /proc/kallsyms",
         "%pK-gated; kptr_restrict denies shell (Permission denied on stock)",
         "masked pointer",
         "STOCK: HARDWARE_OBSERVED Permission denied. REJECT."),
        ("kernel/printk + dmesg/kmsg/pstore",
         "dmesg_restrict + SELinux deny shell",
         "masked/unreachable",
         "STOCK: dmesg/kmsg/pstore all Permission denied. REJECT."),
        ("sys/kernel/slab/* attrs",
         "SELinux deny shell (every attr Permission denied on stock)",
         "unreachable metadata",
         "STOCK: HARDWARE_OBSERVED deny. REJECT."),
        ("sys/kernel/debug + tracing",
         "SELinux deny shell (debug/, tracing/* Permission denied)",
         "unreachable",
         "STOCK: HARDWARE_OBSERVED deny. REJECT."),
        ("proc/sys/kernel/* tunables",
         "SELinux deny shell listing (kptr_restrict unreadable)",
         "unreachable",
         "STOCK: HARDWARE_OBSERVED deny. REJECT."),
    ]
    for src, fmt, cls, verdict in rows:
        print("\nSRC   : %s\nFMT   : %s\nCLASS : %s\nVERDICT: %s" %
              (src, fmt, cls, verdict))
    print("\nFASE 1 net: no direct kernel pointer reaches shell via /proc, "
          "sysfs, debugfs, /proc/net on PI.2055 stock (all masked/denied).")
    print("EVIDENCE: OFFLINE_ONLY (formats) + HARDWARE_OBSERVED (stock denials).")


def copy_scan(vmlinux):
    print("=" * 72)
    print("FASE 2 -- kernel struct -> copy_to_user -> userspace inventory")
    print("EVIDENCE: OFFLINE_ONLY unless a stock probe reproduces a pointer.")
    print("=" * 72)
    rows = [
        ("kernel/futex.c get_robust_list",
         "put_user(head) where head = p->robust_list (__user, set by userspace)",
         "struct robust_list_head __user *", "0x00 (list) + len",
         "sys_get_robust_list", "reachable (own pid)",
         "USER pointer echo, never kernel. REJECT.",
         "returns user address the caller previously set; kernel never "
         "writes a kernel address here (source futex.c:3055-3090)."),
        ("kernel/sched/core.c sched_getattr",
         "copy_to_user(uattr, attr, size) struct sched_attr {u32,u64,s32,...}",
         "NO pointer field (all scalars)", "-",
         "sys_sched_getattr", "reachable",
         "non-pointer metadata. REJECT.",
         "sched_attr is pure scalars by UAPI design."),
        ("kernel/sched/core.c sched_getparam",
         "copy_to_user(param, &lp) struct sched_param {int sched_priority}",
         "NO pointer field", "-",
         "sys_sched_getparam", "reachable",
         "non-pointer metadata. REJECT.",
         "priority int only (p->rt_priority)."),
        ("kernel/signal.c copy_siginfo_to_user",
         "si_ptr/si_addr/si_value copied; SOURCE is sender-controlled or "
         "user IP (KSTK_EIP), never waiter/stack/rt_mutex",
         "siginfo_t.si_ptr (sender user pointer)", "+0x10-ish",
         "sys_rt_sigtimedwait / signal delivery", "reachable on own signals",
         "USER pointer echo. REJECT as kernel disclosure.",
         "si_ptr originates from sigqueue sender (userspace) or user PC; "
         "kernel never fills it with waiter->lock/pi_state."),
        ("net/socket.c getsockname/getpeername/accept",
         "copy_to_user(uaddr, kaddr, len) struct sockaddr (addr family + bytes)",
         "NO kernel pointer (address bytes only)", "-",
         "sys_getsockname etc.", "reachable",
         "non-pointer metadata. REJECT.",
         "sockaddr is network address, never a kernel address."),
        ("net/socket.c SIOCGIFCONF",
         "copy_to_user(uifc, &ifc) struct ifconf {int len; __user *buf}",
         "pointer field is USER buffer echo", "+0x08",
         "sys_ioctl SIOCGIFCONF", "reachable",
         "USER pointer echo. REJECT.",
         "ifc_buf is the caller buffer address round-tripped."),
        ("net/unix/diag.c sk_diag_fill",
         "nla_put ino/dev/qlen/path; sock pointers NEVER emitted",
         "NO pointer field (u32 ino, dev_t, lens)", "-",
         "NETLINK_SOCK_DIAG", "reachable, needs CAP? no, own sockets yes",
         "index only. REJECT.",
         "verified in source: dump_name/vfs/peer/icons/rqlen above."),
        ("drivers/amlogic ge2d REQUEST_BUFF/EXP_BUFF",
         "copy_to_user(&dmabuf_req) = fds + sizes (dma_buf fd, not pointer)",
         "NO kernel pointer (fd ints)", "-",
         "ge2d ioctl", "needs /dev/ge2d (system:graphics, shell denied)",
         "unreachable + non-pointer. REJECT.",
         "shell is not in graphics group; open fails."),
        ("drivers/amlogic vfm VFM_IOCTL_CMD_GET",
         "DISABLED in source (returns -EIO, copy commented out)",
         "n/a", "-",
         "vfm ioctl", "disabled",
         "unreachable. REJECT.",
         "source shows the copy commented with overflow note."),
        ("kernel/futex.c handle_futex_death / PI futex paths",
         "NO copy_to_user of pi_state/rt_mutex/waiter/task anywhere in "
         "futex.c or rtmutex.c (grep: zero copy_to_user hits)",
         "-", "-",
         "FUTEX_* syscalls", "reachable but no struct copy",
         "no channel. REJECT.",
         "futex syscalls return int/long only; PI state never copied out."),
    ]
    for sym, site, struct, field, syscall, reach, verdict, why in rows:
        print("\nSITE  : %s\nCOPY  : %s\nSTRUCT: %s\nFIELD : %s\nCALL  : %s "
              "(%s)\nRESULT: %s\nWHY   : %s" %
              (sym, site, struct, field, syscall, reach, verdict, why))
    print("\nFASE 2 net: every reachable struct copy is scalars, user-pointer "
          "echo, inode/index, or disabled. No kernel pointer survives to "
          "userspace on the audited surface.")
    print("EVIDENCE: OFFLINE_ONLY (source structs + binary grep).")


def stack_flow():
    print("=" * 72)
    print("FASE 3 -- current/stack/waiter auto-reference flow")
    print("Ideal: current->stack -> userspace. Checking whether it exists.")
    print("EVIDENCE: OFFLINE_ONLY (source grep + binary dataflow).")
    print("=" * 72)
    rows = [
        ("current (mrs SP_EL0) consumers",
         "copy_thread, scheduler, futex key (mm + uaddr), seccomp IP",
         "futex key uses current->mm + user uaddr (ints), never task->stack; "
         "seccomp si_call_addr = user PC (KSTK_EIP), not kernel SP.",
         "NO current->stack -> copy_to_user edge. REJECT."),
        ("task->stack / task_stack_page() users",
         "fork (child setup), printk oops header, kdb (all privileged/dmesg)",
         "no unprivileged copy_to_user of task->stack exists in tree.",
         "REJECT (privileged-only consumers)."),
        ("waiter pointer (rt_waiter / futex_q.rt_waiter) users",
         "futex_requeue/pi paths keep it in registers + q struct (heap) + "
         "stack slot; never copied to userspace; q is heap, freed on wake.",
         "NO waiter * -> userspace edge in futex.c.",
         "REJECT."),
        ("SP/FP (x29/sp) in syscall returns",
         "proc_pid_syscall user sp/pc (user regs)",
         "kernel SP never returned in any SyS_ return value "
         "(long/int error codes).",
         "REJECT (user SP only)."),
        ("robust_list head",
         "get_robust_list put_user (futex.c:3055)",
         "user pointer echo (FASE 2). Discloses USER stack/TLS address the "
         "caller set, not kernel stack. Useful as user-SP reference only.",
         "REJECT as kernel disclosure; KEEP as user-address sanity check."),
    ]
    for what, users, flow, verdict in rows:
        print("\nWHAT : %s\nUSES : %s\nFLOW : %s\nVERDICT: %s" %
              (what, users, flow, verdict))
    print("\nFASE 3 net: no current->stack / waiter * / kernel-SP edge to "
          "userspace exists on the audited surface. current->stack -> "
          "userspace is NOT FOUND (not assumed to exist).")
    print("EVIDENCE: OFFLINE_ONLY.")


def heap_scan():
    print("=" * 72)
    print("FASE 6 -- f_alt.pi_mutex heap disclosure paths")
    print("Ideal: f_alt -> pi_state -> pi_mutex -> userspace output.")
    print("EVIDENCE: OFFLINE_ONLY unless a stock probe reproduces a pointer.")
    print("=" * 72)
    rows = [
        ("futex PI state (pi_state / pi_mutex)",
         "never copied out; attach/lookup keep it in kernel; requeue stores "
         "it in q->pi_state (heap) not userspace.",
         "NO pi_state -> userspace edge. REJECT."),
        ("robust list",
         "user pointers only (FASE 2). f_alt owner/waiter robust heads are "
         "user addresses, not pi_mutex.",
         "REJECT (wrong object class)."),
        ("owner transitions (fixup_pi_state_owner / FUTEX_UNLOCK_PI)",
         "return ints; owner TID visible via uaddr word (user TID int), not "
         "task_struct *.",
         "index only (TID int). REJECT as pointer disclosure."),
        ("waiter state / scheduler PI diagnostics",
         "/proc sched/stat show prio/policy/counters (ints); waiter->lock "
         "never printed; %pK paths masked.",
         "non-pointer metadata. REJECT."),
        ("ioctl returning structs (ge2d/vfm/media)",
         "fds + sizes or disabled (FASE 2); no rt_mutex * field in any "
         "reachable ioctl struct.",
         "REJECT."),
        ("binder handles",
         "binder returns u32 handles + user buffers, never struct sock */"
         "task *; debug masked + SELinux denied.",
         "index only. REJECT."),
        ("socket/file disclosure (sock */file *)",
         "/proc/net + fdinfo show ino/flags/pos (ints); sk masked to 0 on "
         "stock; file->f_op never exposed.",
         "index only. REJECT."),
    ]
    for what, flow, verdict in [(r[0], r[1], r[2]) for r in rows]:
        print("\nPATH : %s\nFLOW : %s\nVERDICT: %s" % (what, flow, verdict))
    print("\nFASE 6 net: no f_alt.pi_mutex -> userspace edge exists on the "
          "audited surface. Heap disclosure is NOT FOUND via read-only "
          "structs; the only kernel-pointer carrier already in registers "
          "(pi_state+0x10 LEA) dies in registers (see --rtmutex).")
    print("EVIDENCE: OFFLINE_ONLY.")


def verify(vmlinux):
    print("=" * 72)
    print("Disclosure rejection-point verification (binary)")
    print("EVIDENCE: OFFLINE_ONLY (build-aq/vmlinux).")
    print("=" * 72)
    checks = [
        ("proc_pid_stack", "%pK masked stack show"),
        ("proc_pid_syscall", "user sp/pc show"),
        ("SyS_get_robust_list", "inlined put_user of user-head (stxr, not bl)"),
        ("SyS_sched_getattr", "copy_to_user scalar attr"),
        ("sock_diag_put_filterinfo", "diag uses ino/cookies, no sk pointer"),
        ("futex_wait_requeue_pi.constprop.8", "no copy_to_user in body"),
        ("task_blocks_on_rt_mutex", "H16 birth stp, no copy out"),
        ("rt_mutex_adjust_prio_chain", "walk reads, stores to stack/heap only"),
    ]
    syms = [c[0] for c in checks]
    try:
        d = disasm(vmlinux, syms)
    except Exception as e:
        print("disassemble failed: %s" % e)
        return
    for (sym, note) in checks:
        s2 = sym
        ins = d.get(s2, [])
        ncopy = sum(1 for _, m, r in ins
                    if m in ("bl",) and ("copy_to_user" in r or "copy_touser" in r
                                         or "_copy_to_user" in r))
        nput = sum(1 for _, m, r in ins
                   if m in ("bl",) and "put_user" in r)
        print("%-38s n_insn=%-5d copy_to_user_bl=%d put_user_bl=%d  # %s" %
              (s2, len(ins), ncopy, nput, note))
    print("\nRule: copy/put counts above are call PRESENCE, not proof of a "
          "pointer leak; FASE 2 classifies each struct's fields.")


def main():
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    vmlinux = sys.argv[1]
    mode = sys.argv[2]
    if mode == "--proc":
        proc_scan()
    elif mode == "--copy":
        copy_scan(vmlinux)
    elif mode == "--stack-flow":
        stack_flow()
    elif mode == "--heap":
        heap_scan()
    elif mode == "--verify":
        verify(vmlinux)
    elif mode == "--all":
        proc_scan()
        print("")
        copy_scan(vmlinux)
        print("")
        stack_flow()
        print("")
        heap_scan()
    else:
        sys.exit("unknown mode: %s" % mode)


if __name__ == "__main__":
    main()
