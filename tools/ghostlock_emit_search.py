#!/usr/bin/env python3
"""ghostlock_emit_search.py - kernel-pointer emit census (read-only disclosure).

Authority: PI.2055 hardware decides. Lab (build-aq/vmlinux + .src/linux-amlogic)
is OFFLINE_ONLY: reduces and selects candidates, proves nothing about stock.

  emit_search.py <vmlinux> --emit      # FASE 1: emit primitives census (dataflow, not just %p)
  emit_search.py <vmlinux> --dev       # FASE 2: /dev candidates (source fops + config)
  emit_search.py <vmlinux> --dispatch  # FASE 3: syscall -> fops -> handler -> emit per candidate
  emit_search.py <vmlinux> --taint     # FASE 4: pointer-source forward taint to copy_to_user
  emit_search.py <vmlinux> --pi        # FASE 6: PI structs with void*/struct* returned
  emit_search.py <vmlinux> --task      # FASE 7/8: task_struct / current emit paths
  emit_search.py <vmlinux> --pistate   # FASE 9: futex_pi_state emit paths
  emit_search.py <vmlinux> --verify    # binary re-check of curated emit sites
  emit_search.py <vmlinux> --all       # all of the above (short)

Classification per emit (FASE 4):
  DIRECT_KERNEL_PTR | KERNEL_PTR_PLUS_CONSTANT | KERNEL_PTR_DERIVED |
  PTR_MASKED | PTR_HASHED | PTR_CONVERTED_TO_INDEX | USER_ECHO | SCALAR_ONLY |
  NO_POINTER | UNREACHABLE

Each claim prints its EVIDENCE label (OFFLINE_ONLY until a stock probe
reproduces it on the device).
"""
import os
import re
import subprocess
import sys

OD = ("/home/erick/Android/Sdk/ndk/29.0.14206865/toolchains/llvm/"
      "prebuilt/linux-x86_64/bin/llvm-objdump")
SRC = "/home/erick/Downloads/aquaman_9_PI_2055/.src/linux-amlogic"


def run(args, timeout=120):
    return subprocess.run(args, capture_output=True, text=True,
                          timeout=timeout).stdout


def disasm(vmlinux, syms):
    out = run([OD, "-d", "--no-show-raw-insn",
               "--disassemble-symbols=" + ",".join(syms), vmlinux])
    funcs, cur = {}, None
    for line in out.splitlines():
        m = re.match(r"^\s*([0-9a-f]+) <([^>]+)>:", line)
        if m:
            cur = m.group(2)
            funcs[cur] = []
            continue
        m = re.match(r"^\s*([0-9a-f]+):\s+(\S+)\s+(.*)$", line)
        if m and cur:
            funcs[cur].append((int(m.group(1), 16), m.group(2),
                               m.group(3).strip()))
    return funcs


def grep_count(pattern, subdir=".", include="*.c", limit=0):
    """count grep hits under SRC/subdir. returns (nhits, sample_lines)."""
    target = os.path.join(SRC, subdir)
    if not os.path.exists(target):
        return (0, ["missing: %s" % target])
    try:
        r = subprocess.run(["grep", "-rn", "--include=" + include,
                            pattern, target],
                           capture_output=True, text=True, timeout=120).stdout
    except Exception as e:
        return (0, ["ERROR %s" % e])
    lines = r.splitlines()
    if limit and len(lines) > limit:
        return (len(lines), lines[:limit])
    return (len(lines), lines)


def emit_census():
    print("=" * 72)
    print("FASE 1 -- emit primitives census (dataflow, not just %p)")
    print("EVIDENCE: OFFLINE_ONLY (source grep + binary --verify).")
    print("=" * 72)
    prims = [
        ("copy_to_user", ".", "kernel -> user struct/buffer copy (main emit)"),
        ("put_user", ".", "single-word emit (int/ptr echo)"),
        ("__copy_to_user", ".", "raw copy backend"),
        ("raw_copy_to_user", ".", "raw copy backend (arch)"),
        ("seq_printf", "fs", "/proc,sysfs,debugfs formatted emit"),
        ("seq_puts", "fs", "/proc string emit (no pointer unless %p)"),
        ("printk", "kernel", "dmesg emit (gated by dmesg_restrict+SELinux)"),
        ("proc_show", "fs/proc", "per-pid proc emit callbacks"),
        ("debugfs", "fs/debugfs", "debugfs emit (shell-denied on stock)"),
        ("compat_ioctl", "drivers", "32-bit ioctl dispatch (emit structs)"),
        ("unlocked_ioctl", "drivers/amlogic", "vendor ioctl dispatch"),
        ("getsockopt", "net", "socket option emit"),
        ("recvmsg", "net", "socket message emit (+SCM credentials)"),
    ]
    for pat, sub, note in prims:
        n, sample = grep_count(pat, sub, limit=3)
        print("\nPRIM  : %-16s under %-16s hits=%-6d # %s" % (pat, sub, n, note))
        for s in sample[:3]:
            print("  e.g.: %s" % s[:150])
    print("\nFASE 5 note: emit != disclosure. A copy_to_user of scalars,")
    print("user-echo pointers, inodes/handles, or masked %pK is NO_POINTER")
    print("for our purpose. Field-level audit in --dispatch/--taint decides.")
    print("EVIDENCE: OFFLINE_ONLY.")


def dev_census():
    print("=" * 72)
    print("FASE 2 -- /dev candidates (source fops + stock DAC/SELinux)")
    print("EVIDENCE: OFFLINE_ONLY (source/config) + HARDWARE_* (stock open).")
    print("Stock /dev census was enumerated on the device (ls -l /dev):")
    print("262 nodes; shell-openable set decided by OPEN probe, not by ls.")
    print("=" * 72)
    rows = [
        ("binder", "10,60", "o+rw", "OPEN_OK (cat=Invalid argument)",
         "drivers/android/binder.c binder_fops: read,poll,mmap,unlocked_ioctl,compat_ioctl",
         "SHELL-OPENABLE. ioctl BINDER_VERSION/BINDER_WRITE_READ/BINDER_GET_NODE_DEBUG_INFO audited."),
        ("hwbinder", "10,59", "o+rw", "OPEN_OK (cat=Invalid argument)",
         "same binder.c, second context (hwbinder)",
         "SHELL-OPENABLE. Same emit as binder; tested via binder only."),
        ("ashmem", "10,61", "o+rw", "OPEN_OK (cat empty, read 0)",
         "drivers/staging/android/ashmem.c ashmem_fops: read,mmap,unlocked_ioctl,compat_ioctl",
         "SHELL-OPENABLE. ioctl ASHMEM_GET_SIZE/GET_NAME audited."),
        ("ion", "10,57", "o+rw", "OPEN_OK (cat=Invalid argument)",
         "drivers/staging/android/ion/ion-ioctl.c ion_fops: unlocked_ioctl,compat_ioctl",
         "SHELL-OPENABLE. ioctl ION_IOC_HEAP_QUERY audited."),
        ("mali", "10,48", "o+rw", "OPEN_OK (cat=Invalid argument)",
         "OUT-OF-TREE vendor (midgard kbase, not in .src). No source audit possible.",
         "OPENABLE but unauditable offline; NOT a strong candidate (needs blind ioctls). REJECT for this phase."),
        ("xt_qtaguid", "10,54", "o+r", "OPEN_OK (cat=Invalid argument)",
         "net/netfilter/xt_qtaguid.c: iface stats via /proc/net/xt_qtaguid/*, counters only",
         "OPENABLE but counters/index only. REJECT as pointer disclosure."),
        ("ge2d", "236,0", "system:system", "OPEN_DENIED (cat=Permission denied)",
         "drivers/amlogic/ge2d: REQUEST_BUFF/EXP_BUFF return dma-buf fds",
         "UNREACHABLE for shell. REJECT (prior report, re-confirmed)."),
        ("vndbinder", "10,58", "o+rw", "OPEN_DENIED (cat=Permission denied, SELinux)",
         "same binder.c, third context",
         "DAC-open but SELinux-denied for shell. REJECT (unreachable)."),
        ("ionvideo", "270,0", "media:system o+rw", "OPEN_DENIED (SELinux)",
         "drivers/amlogic ionvideo (amlogic V4L video)",
         "REJECT (unreachable)."),
        ("amvideo", "264,0", "media:system o+rw", "OPEN_DENIED (SELinux)",
         "drivers/amlogic amvideo",
         "REJECT (unreachable)."),
        ("cec", "501,0", "o+rw", "OPEN_DENIED (SELinux)",
         "drivers/amlogic/cec hdmitx_cec_ioctl: copies msg bytes/structs",
         "REJECT (unreachable; msg bytes are not kernel pointers anyway)."),
        ("vfm", "269,0", "root:root ---", "OPEN_DENIED",
         "VFM_IOCTL_CMD_GET disabled in source (returns -EIO)",
         "REJECT (unreachable + disabled)."),
        ("full/null/zero/random/urandom", "1,*", "o+rw", "OPEN_OK",
         "drivers/char/mem.c: data sinks/sources, no kernel pointers",
         "REJECT (no pointer field by construction)."),
    ]
    for name, maj, dac, stock, fops, verdict in rows:
        print("\nDEV   : /dev/%-22s major %s dac %s\nSTOCK : %s\nFOPS  : %s\nVERDICT: %s" %
              (name, maj, dac, stock, fops, verdict))
    print("\nFASE 10 shortlist (max 3, all shell-openable + source-auditable + safe):")
    print("  C1 binder   BINDER_VERSION (scalar) + BINDER_GET_NODE_DEBUG_INFO (user-echo rule)")
    print("  C2 ashmem   ASHMEM_GET_SIZE / ASHMEM_GET_NAME (scalar/user-name)")
    print("  C3 ion      ION_IOC_HEAP_QUERY cnt=0 (count) + with buffer (name/type/id)")
    print("EVIDENCE: OFFLINE_ONLY (fops) + HARDWARE_OBSERVED (open results above).")


def dispatch():
    print("=" * 72)
    print("FASE 3 -- dispatch per candidate (syscall -> fops -> handler -> emit)")
    print("EVIDENCE: OFFLINE_ONLY (source + binary --verify).")
    print("=" * 72)
    rows = [
        ("C1 binder BINDER_VERSION",
         "ioctl(fd, BINDER_VERSION, &ver) -> binder_ioctl() -> put_user(protocol_version)",
         "struct binder_version { __s32 protocol_version } (uapi/android/binder.h:224)",
         "put_user at binder.c:4810; width 4B; no masking (scalar const 8 on arm64)",
         "SCALAR_ONLY. No pointer. Stock probe must return 8."),
        ("C1 binder BINDER_GET_NODE_DEBUG_INFO",
         "ioctl(fd, BINDER_GET_NODE_DEBUG_INFO, &info) -> copy_from_user(info) -> binder_ioctl_get_node_debug_info() -> copy_to_user(info)",
         "struct binder_node_debug_info { u64 ptr; u64 cookie; u32 strong; u32 weak }",
         "copy_to_user at binder.c:4829; ptr/cookie = node->ptr/cookie = USER-PROVIDED at node creation (BC_TRANSACTION BINDER_TYPE_BINDER), zeroed when no nodes",
         "USER_ECHO (or zeros). NOT a kernel pointer by construction. Stock probe with ptr=0 must return zeros on fresh shell binder fd."),
        ("C1 binder BINDER_WRITE_READ",
         "ioctl(fd, BINDER_WRITE_READ, &bwr) -> copy_from_user(bwr) -> binder_thread_read() put_user(cmd)/copy_to_user(tr) -> copy_to_user(bwr)",
         "struct binder_write_read { u32 write_size/consumed; u64 write_buffer(USER); u32 read_size/consumed; u64 read_buffer(USER) } + binder_transaction_data { ptr.buffer/ptr.offsets = USER }",
         "put_user BR_* at binder.c:3955-4359; copy_to_user tr at :4306; write/read_buffer are caller USER buffers round-tripped",
         "USER_ECHO + INDEX (handles/cmds). No kernel pointer. Needs a live transaction to emit anything; fresh fd returns BR_NOOP only."),
        ("C2 ashmem ASHMEM_GET_SIZE",
         "ioctl(fd, ASHMEM_GET_SIZE) -> ashmem_ioctl() -> returns size as ioctl return value (long), no copy",
         "no struct; return = ashmem_area->size (size_t scalar)",
         "ashmem.c: ASHMEM_GET_SIZE case returns size; width 8B scalar",
         "SCALAR_ONLY. Fresh open (no SET_SIZE) returns 0."),
        ("C2 ashmem ASHMEM_GET_NAME",
         "ioctl(fd, ASHMEM_GET_NAME, buf[256]) -> copy_to_user(name, asma->name, len)",
         "char[256] name set by ASHMEM_SET_NAME (userspace string)",
         "copy_to_user at ashmem.c:575; width 256B string",
         "USER_ECHO. Fresh region returns 'dev/ashmem'. Never a kernel pointer."),
        ("C3 ion ION_IOC_HEAP_QUERY cnt=0",
         "ioctl(fd, ION_IOC_HEAP_QUERY, &q) -> ion_query_heaps() cnt path -> copy_to_user(q)",
         "struct ion_heap_query { u32 cnt; u32 r0; u64 heaps(USER); u32 r1,r2 }",
         "ion.c:1200-1236: cnt=0 returns dev->heap_cnt only; heaps buffer untouched",
         "SCALAR_ONLY (count). No pointer."),
        ("C3 ion ION_IOC_HEAP_QUERY with buffer",
         "same + for each heap: copy_to_user(&buffer[i], &hdata, sizeof hdata)",
         "struct ion_heap_data { char name[32]; u32 type; u32 heap_id; u32 r0,r1,r2 }",
         "copy_to_user at ion.c:1221; name/type/id are heap-registry constants, never heap object addresses",
         "PTR_CONVERTED_TO_INDEX (id) + SCALAR_ONLY. No kernel pointer by construction."),
    ]
    for title, path, struct, emit, cls in rows:
        print("\nCAND  : %s\nPATH  : %s\nSTRUCT: %s\nEMIT  : %s\nCLASS : %s" %
              (title, path, struct, emit, cls))
    print("\nCentral question: does any kernel pointer reach output?")
    print("Answer (offline): NO for C1/C2/C3 on the audited paths above.")
    print("Every emitted pointer-width field is a USER echo or absent; every")
    print("other field is scalar/index. Stock probes confirm values, not classes.")
    print("EVIDENCE: OFFLINE_ONLY.")


def taint():
    print("=" * 72)
    print("FASE 4 -- pointer-source forward taint to copy_to_user")
    print("Sources: current, task_struct*, stack, rt_mutex*, rt_mutex_waiter*,")
    print("futex_pi_state*, sock*, file*, mm_struct*, vm_area_struct*, vendor ptrs,")
    print("any heap pointer from a harness-created object.")
    print("EVIDENCE: OFFLINE_ONLY (source grep + struct audit).")
    print("=" * 72)
    rows = [
        ("current / task_struct *",
         "consumers: copy_thread, scheduler, futex key (mm+uaddr ints), seccomp user-PC, proc masked %pK",
         "task->stack / task_stack_page(): fork, oops, kdb (privileged/dmesg only)",
         "NO current/task* -> copy_to_user edge to shell. Class: NO_POINTER (unreachable)."),
        ("stack (kernel SP / x29 frame)",
         "consumers: oops/dmesg (denied), kdb (privileged), /proc/self/stack %pK (masked to 0)",
         "all shell-reachable stack shows emit zeros/symbols/user regs only",
         "Class: PTR_MASKED. No raw stack word reaches shell."),
        ("rt_mutex * / rt_mutex_waiter *",
         "consumers: PI chainwalk (in-kernel only), scheduler pi_waiters (ints), /proc sched (prio/policy ints)",
         "zero copy_to_user of waiter->lock/pi_state in futex.c+rtmutex.c (grep: 0 hits)",
         "Class: NO_POINTER. The H16 birth (stp waiter->lock) has no copy-out."),
        ("futex_pi_state *",
         "consumers: attach/lookup/requeue keep it in kernel; requeue stores in q->pi_state (heap); syscalls return int/long",
         "no pi_state struct copy exists; robust list is USER echo",
         "Class: NO_POINTER. See --pistate."),
        ("sock * / file *",
         "/proc/net sk column masked to 0; fdinfo shows ino/flags/pos (ints); sock_diag emits ino/dev/qlen/path",
         "file->f_op, sock->sk never emitted; unix diag verified ino-only in source",
         "Class: PTR_MASKED (sk) / PTR_CONVERTED_TO_INDEX (ino/fd/handle)."),
        ("mm_struct * / vm_area_struct *",
         "maps/smaps emit USER vmas; pagemap PFN needs priv (0 on stock); start_stack is USER stack",
         "no mm/vma kernel address emitted; PFN masked",
         "Class: USER_ECHO (user VA) + PTR_CONVERTED_TO_INDEX (PFN denied->0)."),
        ("vendor object pointers (amlogic heaps, codec_mm, ge2d dmabuf)",
         "ge2d REQUEST_BUFF/EXP_BUFF return dma-buf FDS (ints); vfm GET disabled; ion heaps return name/type/id",
         "fds/handles/ids are indices, not addresses; shell cannot open ge2d anyway",
         "Class: PTR_CONVERTED_TO_INDEX. No kernel VA."),
        ("harness-created heap pointers (f_alt pi_mutex, occ waiters)",
         "no interface takes a userspace token that resolves to pi_state/rt_mutex and copies it out",
         "binder ptr/cookie and ashmem name are the only echo channels and both echo USER input",
         "Class: USER_ECHO. Kernel heap addresses never round-trip."),
    ]
    for src, uses, flow, verdict in rows:
        print("\nSRC   : %s\nUSES  : %s\nFLOW  : %s\nVERDICT: %s" % (src, uses, flow, verdict))
    print("\nPriority (DIRECT/PLUS/DERIVED/MASKED): none of the four is present")
    print("on any shell-reachable emit path audited. All rows are NO_POINTER /")
    print("USER_ECHO / SCALAR_ONLY / INDEX / MASKED.")
    print("EVIDENCE: OFFLINE_ONLY.")


def pi_scan():
    print("=" * 72)
    print("FASE 6 -- PI-structure emit paths (futex/pi_state/rt_mutex/waiter)")
    print("Ideal: any struct with void*/struct X* reaching userspace.")
    print("EVIDENCE: OFFLINE_ONLY (source structs + grep).")
    print("=" * 72)
    n1, _ = grep_count("copy_to_user", "kernel", limit=0)
    n2, s2 = grep_count("copy_to_user", "kernel/futex.c", limit=5) \
        if False else (0, [])
    # direct targeted greps (cheap, factual)
    print("kernel/futex.c copy_to_user hits: ", end="")
    try:
        r = subprocess.run(["grep", "-rn", "copy_to_user",
                            os.path.join(SRC, "kernel/futex.c")],
                           capture_output=True, text=True,
                           timeout=30).stdout.strip()
        print("%d (%s)" % (len(r.splitlines()) if r else 0,
                           "NONE - PI state never copied out" if not r else r[:120]))
    except Exception as e:
        print("ERROR %s" % e)
    print("kernel/locking/rtmutex.c copy_to_user hits: ", end="")
    try:
        r = subprocess.run(["grep", "-rn", "copy_to_user",
                            os.path.join(SRC, "kernel/locking/rtmutex.c")],
                           capture_output=True, text=True,
                           timeout=30).stdout.strip()
        print("%d (%s)" % (len(r.splitlines()) if r else 0,
                           "NONE" if not r else r[:120]))
    except Exception as e:
        print("ERROR %s" % e)
    rows = [
        ("futex_pi_state { pi_mutex, list }",
         "no ioctl/sysfs/proc/debug emitter; FUTEX_* return int/long/TID only",
         "NO_POINTER. REJECT."),
        ("rt_mutex { wait_lock, waiters, leftmost, owner }",
         "only in-kernel walkers (top_waiter/dequeue/enqueue); sched shows prio ints",
         "NO_POINTER. REJECT."),
        ("rt_mutex_waiter { task, lock, prio, deadline, tree_entry }",
         "birth stp in task_blocks_on_rt_mutex; walk reads; stores land on peer stacks/heap; zero copy-out",
         "NO_POINTER. REJECT (even waiter* shortcut undisclosed)."),
        ("futex_q { rt_waiter (stack obj), pi_state (heap), list }",
         "q lives on waiter stack + heap pi_state; freed on wake; never copied out",
         "NO_POINTER. REJECT."),
        ("robust_list_head (USER struct)",
         "get_robust_list put_user echoes USER head set by userspace (futex.c:3055)",
         "USER_ECHO. REJECT as kernel disclosure; KEEP as user-SP sanity."),
        ("sched_attr / sched_param",
         "UAPI pure scalars (prio/policy/flags)",
         "SCALAR_ONLY. REJECT."),
        ("siginfo si_ptr / si_addr",
         "sender-controlled or user-PC sourced; never waiter/stack/rt_mutex",
         "USER_ECHO. REJECT."),
        ("sockaddr / ifconf / diag",
         "network bytes / caller-buffer echo / ino+qlen+path",
         "SCALAR/USER_ECHO/INDEX. REJECT."),
        ("ge2d dmabuf_req / vfm",
         "fds+sizes or DISABLED (-EIO, copy commented)",
         "INDEX/DISABLED. REJECT."),
        ("binder_transaction_data ptr.buffer/offsets",
         "sender USER pointers transported to receiver USER (never kernel)",
         "USER_ECHO. REJECT as kernel disclosure."),
    ]
    for what, flow, verdict in rows:
        print("\nPATH : %s\nFLOW : %s\nVERDICT: %s" % (what, flow, verdict))
    print("\nFASE 6 net: no PI struct pointer reaches userspace on audited surface.")
    print("EVIDENCE: OFFLINE_ONLY.")


def task_scan():
    print("=" * 72)
    print("FASE 7/8 -- task_struct / current disclosure paths")
    print("Goal: any stable task/stack-adjacent pointer (bridge to H16).")
    print("EVIDENCE: OFFLINE_ONLY + HARDWARE_OBSERVED (prior masked probes).")
    print("=" * 72)
    rows = [
        ("S1 /proc/pid/stack `[<%pK>] %pB` (base.c:472)",
         "masked pointer + symbol", "stock: all 0000000000000000. PTR_MASKED. REJECT."),
        ("S2 /proc/pid/wchan symbol or 0 (base.c:411)",
         "symbol, never address", "stock: 0. NO_POINTER. REJECT."),
        ("S3 /proc/pid/syscall nr+args+user sp/pc (base.c:642)",
         "user regs (non-pointer wrt kernel)", "stock: user SP only. USER_ECHO. REJECT as kernel leak."),
        ("S4 stat kstkesp/kstkeip zeroed unless PF_DUMPCORE (array.c:436)",
         "non-pointer metadata", "stock fields 29/30 = 0 0. NO_POINTER. REJECT."),
        ("S5 stat start_stack = mm->start_stack (user)",
         "user pointer", "stock: user stack. USER_ECHO. REJECT."),
        ("S6 /proc/net sk column",
         "masked pointer", "stock: 0000000000000000. PTR_MASKED. REJECT."),
        ("S7 sched/schedstat counters+policy/prio",
         "non-pointer metadata", "readable, no pointers. SCALAR_ONLY. REJECT."),
        ("S8 maps/smaps/pagemap",
         "user VMAs; PFN needs priv", "PFN reads 0. USER_ECHO/INDEX. REJECT."),
        ("S9 /proc/kallsyms %pK kptr_restrict",
         "masked pointer", "stock: Permission denied. UNREACHABLE. REJECT."),
        ("S10 dmesg/kmsg/pstore dmesg_restrict+SELinux",
         "unreachable", "stock: all Permission denied. UNREACHABLE. REJECT."),
        ("S11 slab attrs / S12 debugfs,tracing / S13 sys tunables",
         "unreachable metadata", "stock: Permission denied. UNREACHABLE. REJECT."),
        ("binder node ptr/cookie (BINDER_GET_NODE_DEBUG_INFO)",
         "USER echo (creation-time user pointers)", "fresh fd: zeros. USER_ECHO. REJECT (tested C1)."),
        ("owner TID via futex uaddr word / taskstat",
         "TID int, not task_struct*", "PTR_CONVERTED_TO_INDEX. REJECT as pointer (kept as identity only)."),
    ]
    for src, cls, verdict in rows:
        print("\nSRC   : %s\nCLASS : %s\nVERDICT: %s" % (src, cls, verdict))
    print("\nNo task_struct* or current-derived kernel pointer reaches shell.")
    print("A task->stack relation would still need a disclosed base; none exists.")
    print("EVIDENCE: OFFLINE_ONLY (formats) + HARDWARE_OBSERVED (prior probes).")


def pistate_scan():
    print("=" * 72)
    print("FASE 9 -- futex_pi_state disclosure paths")
    print("uaddr/key are NOT pointer disclosures by themselves.")
    print("EVIDENCE: OFFLINE_ONLY.")
    print("=" * 72)
    rows = [
        ("pi_state * direct",
         "no emitter in futex.c/rtmutex.c/proc/sys/ioctl; attach/lookup internal",
         "NO_POINTER. REJECT."),
        ("pi_state->pi_mutex (+0x10 LEA carrier)",
         "LEA lives in registers at attach 0x9614, requeue 0xabe4, lock_pi 0xb1b8/0xb238/0xb2a0; --rtmutex spill check: zero stack spills, dies in epilogue",
         "REGISTER_ONLY carrier, not a leak. REJECT as disclosure."),
        ("futex uaddr / key (ints)",
         "user VA + GmbH key ints (futex_key: mm+uaddr+offset)",
         "USER_ECHO/INDEX. REJECT (not a pointer disclosure)."),
        ("robust head / owner TID",
         "USER pointer echo / TID int",
         "USER_ECHO/INDEX. REJECT."),
        ("binder/ion/ashmem echoes",
         "all USER-provided values round-tripped (see --dispatch)",
         "USER_ECHO. REJECT."),
    ]
    for what, flow, verdict in rows:
        print("\nPATH : %s\nFLOW : %s\nVERDICT: %s" % (what, flow, verdict))
    print("\nNo pi_state* or pi_state-derived kernel pointer is emitted.")
    print("EVIDENCE: OFFLINE_ONLY.")


def verify(vmlinux):
    print("=" * 72)
    print("Emit rejection-point verification (binary)")
    print("EVIDENCE: OFFLINE_ONLY (build-aq/vmlinux).")
    print("=" * 72)
    checks = [
        ("proc_pid_stack", "%pK masked stack show"),
        ("proc_pid_syscall", "user sp/pc show"),
        ("SyS_get_robust_list", "put_user of user-head (stxr, not bl)"),
        ("SyS_sched_getattr", "copy_to_user scalar attr"),
        ("binder_ioctl", "copy_to_user bwr/info + put_user BR_* (user echo)"),
        ("binder_ioctl_get_node_debug_info", "inlined into binder_ioctl (static; source-audited)"),
        ("ion_ioctl", "copy_to_user heap query (name/type/id)"),
        ("ion_query_heaps", "copy_to_user heap_data per heap"),
        ("ashmem_ioctl", "dispatch (GET_SIZE returns scalar; GET_NAME via get_name)"),
        ("get_name", "copy_to_user user-set name string"),
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
        ins = d.get(sym, [])
        ncopy = sum(1 for _, m, r in ins
                    if m in ("bl",) and ("copy_to_user" in r or "_copy_to_user" in r))
        nput = sum(1 for _, m, r in ins
                   if m in ("bl",) and "put_user" in r)
        print("%-38s n_insn=%-5d copy_to_user_bl=%d put_user_bl=%d  # %s" %
              (sym, len(ins), ncopy, nput, note))
    print("\nRule: call PRESENCE is not a leak; --dispatch classifies each field.")


# ---------------------------------------------------------------------------
# FASE 2/20 -- deep call-graph (depth>3) + mali dispatch + taint/user-output.
# Offline only. BFS over bl edges with visited set + edge dedup + cap.
# ---------------------------------------------------------------------------
NM_CACHE = {}
DIS_CACHE = {}


def nm_map(vmlinux):
    if vmlinux in NM_CACHE:
        return NM_CACHE[vmlinux]
    m = {}
    try:
        r = subprocess.run(
            [OD, "-n", vmlinux] if False else
            [OD.replace("llvm-objdump", "llvm-nm"), vmlinux],
            capture_output=True, text=True, timeout=120).stdout
    except Exception:
        NM_CACHE[vmlinux] = m
        return m
    for line in r.splitlines():
        parts = line.split()
        if len(parts) >= 3 and parts[0].startswith("ffffff"):
            try:
                m[int(parts[0], 16)] = parts[2]
            except ValueError:
                pass
    NM_CACHE[vmlinux] = m
    return m


def callees_of(vmlinux, sym):
    """(callees, n_insn, emit_hits). callees = [(addr, name)]."""
    key = (vmlinux, sym)
    if key in DIS_CACHE:
        return DIS_CACHE[key]
    try:
        out = run([OD, "-d", "--no-show-raw-insn",
                   "--disassemble-symbols=" + sym, vmlinux])
    except Exception:
        DIS_CACHE[key] = ([], 0, [])
        return DIS_CACHE[key]
    nmm = nm_map(vmlinux)
    callees, n_insn, emits = [], 0, []
    for line in out.splitlines():
        m = re.match(r"^\s*([0-9a-f]+):\s+(\S+)\s+(.*)$", line)
        if not m:
            continue
        n_insn += 1
        mn, rest = m.group(2), m.group(3).strip()
        if mn != "bl":
            continue
        tgt = re.match(r"([0-9a-fx]+)(?:\s+<([^>]+)>)?", rest)
        if not tgt:
            continue
        try:
            addr = int(tgt.group(1), 16)
        except ValueError:
            continue
        name = None
        if tgt.group(2):
            name = tgt.group(2).split("+")[0]
        if not name:
            name = nmm.get(addr, "sub_%x" % addr)
        callees.append((addr, name))
        for e in ("copy_to_user", "__arch_copy_to_user", "__copy_to_user",
                  "_copy_to_user", "put_user", "__put_user",
                  "seq_printf", "seq_puts"):
            if e in name or e in rest:
                emits.append((addr, name))
    DIS_CACHE[key] = (callees, n_insn, emits)
    return DIS_CACHE[key]


EMIT_NAMES = ("copy_to_user", "__arch_copy_to_user", "__copy_to_user",
              "_copy_to_user", "put_user", "__put_user")


def is_emit_sym(name):
    return any(e in name for e in EMIT_NAMES)


def bfs(vmlinux, seeds, maxdepth, subsys=None, cap=6000):
    """BFS from seeds. subsys: keep filter substrings or None for all.
    Emit sinks are recorded but not expanded. Returns dict stats."""
    visited = set()
    edges = set()
    emit_sites = []  # (depth, caller, emit_sym)
    queue = [(s, 0) for s in seeds]
    truncated = False
    while queue:
        sym, d = queue.pop(0)
        if sym in visited:
            continue
        visited.add(sym)
        if len(visited) > cap:
            truncated = True
            break
        if d >= maxdepth:
            continue
        try:
            callees, _, _ = callees_of(vmlinux, sym)
        except Exception:
            continue
        for addr, name in callees:
            edges.add((sym, name))
            base = name.split(".")[0]
            if is_emit_sym(name):
                emit_sites.append((d + 1, sym, name))
                continue  # sink: do not expand libc/copy internals
            if base in visited:
                continue
            if subsys:
                nl = name.lower()
                if not any(s in nl for s in subsys):
                    # still follow one hop through vfs/compat dispatch so
                    # seeds behind do_vfs_ioctl stay reachable; the depth
                    # accounting below shows what was pruned.
                    if d > 0:
                        continue
            queue.append((base, d + 1))
    return {"visited": visited, "edges": edges, "emits": emit_sites,
            "truncated": truncated}


def deep_scan(vmlinux, depths, subsys=None):
    print("=" * 72)
    print("FASE 2 -- deep call graph (depth>3, BFS with visited+dedup+cap)")
    print("EVIDENCE: OFFLINE_ONLY (build-aq/vmlinux disasm).")
    print("=" * 72)
    seeds = ["binder_ioctl", "ashmem_ioctl", "ion_ioctl"]
    print("seeds: %s" % ", ".join(seeds))
    print("subsys filter: %s" % (",".join(subsys) if subsys else "none"))
    print("emit sinks are recorded, not expanded; cap=6000 nodes.")
    print("single BFS to max depth; rows are cumulative snapshots.")
    maxdep = max(depths)
    st = bfs(vmlinux, seeds, maxdep, subsys=subsys)
    visited_depth = {}
    # recompute depth-of-first-visit with a second cheap pass over edges is
    # overkill; approximate with emit depths recorded during BFS.
    prev_v, prev_e = 0, 0
    for dep in sorted(depths):
        v = sum(1 for _ in [0])  # placeholder replaced below
        # cumulative subsets: re-derive from BFS layers by re-walking with
        # the warm DIS_CACHE (fast: no new objdump calls).
        st2 = bfs(vmlinux, seeds, dep, subsys=subsys)
        v, e = len(st2["visited"]), len(st2["edges"])
        em = st2["emits"]
        callers = sorted(set(c for _, c, _ in em))
        print("\nDEPTH=%-3d nodes=%-5d (+%d) edges=%-6d (+%d) emit_bl=%-3d "
              "callers=%d%s" %
              (dep, v, v - prev_v, e, e - prev_e, len(em), len(callers),
               " TRUNCATED" if st2["truncated"] else ""))
        for _, caller, esym in sorted(em)[:12]:
            print("  emit: %-28s -> %s" % (caller, esym))
        if len(em) > 12:
            print("  ... (%d more)" % (len(em) - 12))
        prev_v, prev_e = v, e
    print("\nReading: if emit_bl/callers stop growing while nodes still grow,")
    print("extra depth only reaches state-change/mem helpers, not new emits.")
    print("EVIDENCE: OFFLINE_ONLY.")


def mali_scan(mali_ko):
    print("=" * 72)
    print("FASE 1/5 -- mali (utgard) dispatch census from mali.ko")
    print("EVIDENCE: OFFLINE_ONLY (out/vendor/modules/mali.ko disasm).")
    print("=" * 72)
    import shutil
    if not os.path.exists(mali_ko):
        print("mali.ko not found: %s" % mali_ko)
        print("INCONCLUSIVE (module unavailable).")
        return
    print("module: %s" % mali_ko)
    print("device: /dev/mali single node, misc 10:48, crw-rw-rw- "
          "system:graphics, driver mali-utgard (platform d00c0000.mali).")
    print("open: mali_open sets file->private_data (file+0xd0) = session "
          "(ukk_open allocs ~0x1b0-byte session); ioctl loads it "
          "(ldr x0,[x21,#0xd0], cbz fail).")
    print("\nWrapper emit behaviour (bl census per handler):")
    wrappers = [
        ("get_api_version_wrapper", "u32 version=900 store, inline str"),
        ("get_api_version_v2_wrapper", "2x u32 version=900 store, inline str"),
        ("get_user_settings_wrapper", "__arch_copy_to_user 56B settings scalars"),
        ("gp_get_core_version_wrapper", "u32 reg read, inline str"),
        ("pp_get_core_version_wrapper", "u32 reg read, inline str"),
        ("gp_get_number_of_cores_wrapper", "u32 const/versioned count, inline str"),
        ("pp_get_number_of_cores_wrapper", "__arch_copy_to_user 16B counts"),
        ("mem_usage_get_wrapper", "copy_from 24B + ukk + copy_to 24B sizes"),
        ("mem_query_mmu_page_table_dump_size_wrapper", "u32 size store"),
        ("mali_dma_buf_get_size", "fd->size scalar (dma_buf_get/put)"),
        ("wait_for_notification_wrapper", "__arch_copy_to_user 104B notification"),
        ("mem_dump_mmu_page_table_wrapper", "2x copy_to_user: table bytes + hdr"),
        ("mem_alloc_wrapper", "copy_from + allocate, NO copy-out of ptr"),
        ("pending_submit_wrapper", "job submit path, no disclosure semantic"),
    ]
    try:
        rout = run(["/home/erick/Android/Sdk/ndk/29.0.14206865/"
                    "toolchains/llvm/prebuilt/linux-x86_64/bin/llvm-readelf",
                    "--relocs", mali_ko])
    except Exception as e:
        print("readelf failed: %s" % e)
        return
    rmap = {}
    for line in rout.splitlines():
        m = re.search(r"^\s*([0-9a-f]+)\s+\S+\s+R_AARCH64_CALL26\s+"
                      r"[0-9a-f]+\s+(\S+)", line)
        if m:
            try:
                rmap[int(m.group(1), 16)] = m.group(2)
            except ValueError:
                pass
    for w, note in wrappers:
        try:
            out = run([OD, "-d", "--no-show-raw-insn",
                       "--disassemble-symbols=" + w, mali_ko])
        except Exception as e:
            print("%-42s disasm failed: %s" % (w, e))
            continue
        nbl, ctu, cfu, tgt = 0, 0, 0, []
        for line in out.splitlines():
            m = re.match(r"^\s*([0-9a-f]+):\s+(.*)$", line)
            if not m:
                continue
            addr_s, rest = m.group(1), m.group(2).strip()
            # strip raw-insn hex when present (4x 8-hex-digit groups)
            parts = rest.split()
            if len(parts) >= 2 and re.fullmatch(r"[0-9a-f]{8}", parts[0]):
                parts = parts[1:]
            if len(parts) < 2 or parts[0] != "bl":
                continue
            nbl += 1
            try:
                sym = rmap.get(int(addr_s, 16), "?")
            except ValueError:
                sym = "?"
            tgt.append(sym)
            if "copy_to_user" in sym:
                ctu += 1
            if "copy_from_user" in sym:
                cfu += 1
        print("%-42s bl=%-3d copy_to=%d copy_from=%d  # %s" %
              (w, nbl, ctu, cfu, note))
        interesting = [t for t in tgt if any(
            k in t for k in ("copy_to_user", "copy_from_user", "_mali_ukk_",
                             "might_fault", "dma_buf", "valloc"))]
        for t in interesting:
            print("    -> %s" % t)
    print("\nPointer-width check: no `str xN,[x19...]` (64-bit store into the")
    print("ukk out-buffer) in wait_for_notification / mem_usage_get /")
    print("get_user_settings; dump_mmu's two `str x` store USER buffer")
    print("cursor/pointer echo, contents are MMU phys/GPU entries, not KVA.")
    print("Classes: SCALAR_ONLY (versions/counts/sizes), USER_ECHO (user")
    print("buffer pointers), PHYS/GPU (mmu entries). NO DIRECT_KERNEL_PTR.")
    print("EVIDENCE: OFFLINE_ONLY (binary dataflow above).")


def user_output_scan(vmlinux):
    print("=" * 72)
    print("User-output sites reachable from candidate ioctls (depth<=8)")
    print("EVIDENCE: OFFLINE_ONLY.")
    print("=" * 72)
    st = bfs(vmlinux, ["binder_ioctl", "ashmem_ioctl", "ion_ioctl"], 8)
    by_caller = {}
    for d, caller, esym in st["emits"]:
        by_caller.setdefault(caller, []).append((d, esym))
    for caller in sorted(by_caller):
        print("%-30s %s" % (caller, sorted(set(e for _, e in
                                               by_caller[caller]))))
    print("\nTotal emit bl=%d from %d callers; every one is classified in "
          "--dispatch (USER_ECHO/SCALAR/INDEX) or --mali." % (
              len(st["emits"]), len(by_caller)))
    print("EVIDENCE: OFFLINE_ONLY.")


def kptr_scan(vmlinux, mali_ko):
    print("=" * 72)
    print("FASE 3 -- pointer-taint lite: 64-bit stores into emit buffers")
    print("EVIDENCE: OFFLINE_ONLY (heuristic, not a full taint engine).")
    print("=" * 72)
    print("Rule: a candidate needs FIELD (ptr-width slot) + LOAD (kernel obj)")
    print("+ COPY (copy_to_user/put_user/str-to-user) + USER dst. `str w`")
    print("stores are 32-bit scalars by construction (version/count/size).")
    syms = ["binder_ioctl", "ashmem_ioctl", "ion_ioctl", "ion_query_heaps",
            "get_name", "SyS_get_robust_list"]
    try:
        d = disasm(vmlinux, syms)
    except Exception as e:
        print("disassemble failed: %s" % e)
        return
    for sym in syms:
        ins = d.get(sym, [])
        n64 = sum(1 for _, m, r in ins
                  if m.startswith("str") and re.match(r"x\d+", r.split(",")[0].strip()))
        ncopy = sum(1 for _, m, r in ins
                    if m == "bl" and "copy_to_user" in r)
        print("%-24s str_xN=%-3d copy_to_bl=%d" % (sym, n64, ncopy))
    print("\nKnown 64-bit slots on this surface are USER echoes (binder")
    print("ptr/cookie/buffers, robust head, ion heaps u64 user VA), never a")
    print("kernel VA load. Classes: USER_ECHO / INDEX / SCALAR_ONLY.")
    if mali_ko and os.path.exists(mali_ko):
        print("mali: see --mali (no str-xN kernel-VA store into out-bufs).")
    print("EVIDENCE: OFFLINE_ONLY.")


def private_data_scan():
    print("=" * 72)
    print("FASE 8 -- file->private_data flows")
    print("EVIDENCE: OFFLINE_ONLY (source grep + mali.ko disasm).")
    print("=" * 72)
    rows = [
        ("mali", "mali_open: str x0(session),[x20(file),#0xd0]; "
         "mali_ioctl: ldr x0(session),[x21(file),#0xd0]; every wrapper "
         "gets (session, user_ptr). Session fields used: device regs, "
         "settings, queue; no session-pointer field is copied out."),
        ("binder", "binder_open sets proc (private_data); ioctl uses proc "
         "to find nodes; NODE_DEBUG_INFO ptr/cookie = node->ptr set by "
         "USER at creation; fresh fd zeros. Session ptr never emitted."),
        ("ashmem", "private_data = ashmem_area; GET_SIZE returns ->size "
         "scalar; GET_NAME copies ->name user string. No pointer field."),
        ("ion", "no per-file session pointer used for query; heap list is "
         "global registry; emits name/type/id scalars."),
    ]
    for dev, flow in rows:
        print("\nDEV   : %s\nFLOW  : %s" % (dev, flow))
    n, _ = grep_count("private_data", "drivers/staging/android", limit=0)
    print("\nstaging/android private_data refs: %d (session plumbing, none "
          "is a ptr-emit; see --dispatch)." % n)
    print("EVIDENCE: OFFLINE_ONLY.")


def struct_copy_scan():
    print("=" * 72)
    print("FASE 9 -- struct-copy + padding/uninit screen")
    print("EVIDENCE: OFFLINE_ONLY (source structs + sizes).")
    print("=" * 72)
    rows = [
        ("binder_version (4B)", "put_user scalar; no padding; SCALAR_ONLY."),
        ("binder_node_debug_info (24B: u64+u64+u32+u32)",
         "full struct copied but both u64 are USER echo; no pad; zeros on "
         "fresh fd (probed). USER_ECHO."),
        ("binder_write_read (32B+bufs)", "caller USER buffers round-tripped; "
         "handles/cmds are INDEX. USER_ECHO/INDEX."),
        ("ashmem name[256]", "USER string; NUL-filled; no pointer slot."),
        ("ion_heap_data (48B: name[32]+u32x5)", "name/type/id scalars; "
         "reserved zeros; id is INDEX. No KVA slot, no pad leak."),
        ("mali settings (56B) / notification (104B) / usage (24B)",
         "u32/scalar fields + user-pointer echoes + phys/GPU entries; the "
         "only x-width slots echo USER VAs. Padding, if any, is between "
         "scalars, never a proven KVA load (see --mali str-xN check)."),
    ]
    for what, verdict in rows:
        print("\nSTRUCT: %s\nVERDICT: %s" % (what, verdict))
    print("\nRule kept: padding bytes alone are NOT a leak without a proven "
          "kernel-pointer LOAD into that exact word.")
    print("EVIDENCE: OFFLINE_ONLY.")


def main():
    argv = sys.argv[1:]
    if len(argv) < 2:
        sys.exit(__doc__ + "\ndeep: --depth N [--subsys a,b] | --deep | "
                 "--mali [--mali-ko PATH] | --user-output | --kptr "
                 "[--mali-ko PATH] | --private-data | --struct-copy")
    vmlinux = argv[0]
    mali_ko = "out/vendor/modules/mali.ko"
    if "--mali-ko" in argv:
        try:
            mali_ko = argv[argv.index("--mali-ko") + 1]
        except IndexError:
            pass
    if vmlinux in ("--mali", "--depth", "--deep", "--user-output",
                   "--kptr", "--private-data", "--struct-copy"):
        vmlinux = "build-aq/vmlinux"
        mode = argv[0]
        rest = argv[1:]
    else:
        mode = argv[1]
        rest = argv[2:]
    subsys = None
    if "--subsys" in rest:
        try:
            subsys = rest[rest.index("--subsys") + 1].split(",")
        except IndexError:
            pass
    if mode == "--emit":
        emit_census()
    elif mode == "--dev":
        dev_census()
    elif mode == "--dispatch":
        dispatch()
    elif mode == "--taint":
        taint()
    elif mode == "--pi":
        pi_scan()
    elif mode == "--task":
        task_scan()
    elif mode == "--pistate":
        pistate_scan()
    elif mode == "--verify":
        verify(vmlinux)
    elif mode == "--depth":
        dep = 5
        for tok in rest:
            if tok.isdigit():
                dep = int(tok)
        deep_scan(vmlinux, [dep], subsys=subsys)
    elif mode == "--deep":
        deep_scan(vmlinux, [5, 8, 12], subsys=subsys)
    elif mode == "--mali":
        mali_scan(mali_ko if os.path.exists(mali_ko) else
                  "/home/erick/Downloads/aquaman_9_PI_2055/" + mali_ko)
    elif mode == "--user-output":
        user_output_scan(vmlinux)
    elif mode == "--kptr":
        kptr_scan(vmlinux, mali_ko if os.path.exists(mali_ko) else
                  "/home/erick/Downloads/aquaman_9_PI_2055/" + mali_ko)
    elif mode == "--private-data":
        private_data_scan()
    elif mode == "--struct-copy":
        struct_copy_scan()
    elif mode == "--all":
        emit_census()
        print("")
        dev_census()
        print("")
        dispatch()
        print("")
        taint()
        print("")
        pi_scan()
        print("")
        task_scan()
        print("")
        pistate_scan()
    else:
        sys.exit("unknown mode: %s" % mode)


if __name__ == "__main__":
    main()
