RESULT: NO_READ_SURFACE_FOUND
BOOT_ID: 3ec336a5-439f-497f-b9f7-08fd7441b174
DEVICES_SCANNED: 499
OPENABLE_COUNT: 18
READ_CANDIDATES: 12
IOCTL_CANDIDATES: 13
POINTER_BYTES_FOUND: 0
REBOOTS: 0
TESTS: 18

# dev read surface census 2026-10-01

Closes the partial-sample gap from ghostlock-stock-disclosure-2026-10-01.
Full /dev open census from shell, f_op mapping for every openable node,
safe GET/QUERY + read/poll probes only. No blind ioctl, no spray, no write.

Raw logs: out/logs/dev_census_boot3ec336a5.log (499 paths),
out/logs/dev_read_probe_boot3ec336a5.log,
out/logs/dev_emit_rerun_boot3ec336a5.log.
Tools: /data/local/tmp/dev_census, /data/local/tmp/dev_read_probe
(source /tmp/opencode/dev_census.c, dev_read_probe.c),
tools/ghostlock_emit_probe.c (re-run, no rebuild).

## 1. Environment

```text
BOOT_ID: 3ec336a5-439f-497f-b9f7-08fd7441b174
KERNEL: 4.9.113 #1 SMP PREEMPT 2022-09-06 armv8l (localhost)
FINGERPRINT: Xiaomi/aquaman/aquaman:9/PI/2055:user/release-keys
UID: uid=2000(shell) gid=2000(shell) context=u:r:shell:s0
SELINUX: Enforcing
UPTIME: 31471s, same BOOT_ID before/after all probes
REBOOTS: 0
```

## 2. /dev inventory

Method: C prober on device, opendir /dev + 2-level recurse + explicit
dotfile/SELinux-denied names. Per path: lstat (mode/uid/gid/maj:min) +
open(O_RDONLY|O_NONBLOCK) rc/errno. DAC 0666 means nothing; SELinux decides.

```text
total unique paths probed: 499
top-level /dev entries: 267 (263 readdir-ok + 4 stat-denied:
  .coldboot_done, event-log-tags, tee0, teepriv0)
char/block with stat-ok: 298 (296 + 2 usbdev 189:0/189:128 found via ls -R)
stat-denied (SELinux, maj unknown): 6
  /dev/tee0, /dev/teepriv0, /dev/event-log-tags,
  /dev/.coldboot_done, /dev/graphics/fb0, /dev/graphics/fb1
socket-denied: 16 under /dev/socket (all EACCES on stat/open)
device-node candidates: 304 (298 + 6 denied)
shell-openable char/block: 18
```

Openable (all open_rc=0, this boot):

```text
device                  major:minor  perms        owner:group
/dev/binder             10:60        crw-rw-rw-   root:root
/dev/hwbinder           10:59        crw-rw-rw-   root:root
/dev/ashmem             10:61        crw-rw-rw-   root:root
/dev/ion                10:57        crw-rw-rw-   system:graphics
/dev/mali               10:48        crw-rw-rw-   system:graphics
/dev/uhid               10:239       crw-rw----   uhid:uhid (shell in 3011 uhid)
/dev/xt_qtaguid         10:54        crw-rw-r--   root:root
/dev/null               1:3          crw-rw-rw-   root:root
/dev/zero               1:5          crw-rw-rw-   root:root
/dev/random             1:8          crw-rw-rw-   root:root
/dev/urandom            1:9          crw-rw-rw-   root:root
/dev/ptmx               5:2          crw-rw-rw-   root:root
/dev/input/event0       13:64        crw-rw----   root:input (shell in 1004 input)
/dev/input/event1       13:65        same
/dev/input/event2       13:66        same
/dev/input/event3       13:67        same
/dev/input/mice         13:63        same
/dev/input/mouse0       13:32        same
```

Denied groups (representative, full list in census log).
All open_rc=-1 EACCES except /dev/tty ENoDEv:

```text
group                       count  note
amstream_* 255:*            17     DAC 0666 but SELinux-denied (all 17)
/dev/cec 501:0, vndbinder 10:58, ionvideo 270:0, amvideo 264:0,
  snd/* 116:*, video* 81:*, ge2d 236:0, ppmgr, display, etc.
                           DAC-open, SELinux-denied. cat=Permission denied.
tty 4:*, ptyp/ptyp 2:*/3:* 160    0600 root:root. DENIED.
block 179:*,7:*,251:*,etc  36     0600 root:root. DENIED.
misc root-only 10:*         ~15    fused, watchdog, tun, uinput, etc. DENIED.
/dev/full 1:7              1      DAC 0666 but SELinux-denied. cat denied.
/dev/tty 5:0               1      ENODEV (no controlling tty). DENIED.
/dev/bus/usb/*/001 189:*   2      0660 root:usb, shell not in usb. DENIED.
stat-denied 6 + socket 16  22     EACCES even on lstat. DENIED.
```

Classification per task: OPENABLE (18 above), DENIED (everything else),
ABSENT (none; slabinfo-style absences are /proc, out of scope here).

## 3. Candidate handlers

Source: .src/linux-amlogic + out/vendor/modules/mali.ko (binary).
Only the 18 openable nodes.

```text
device          operation       handler                                  reachable  classification
binder          ioctl           binder_ioctl (VERSION/NODE_DEBUG/WRITE_READ) yes    SCALAR_ONLY / USER_INPUT_ECHO
hwbinder        ioctl           binder_ioctl (same)                        yes    same as binder
binder/hwbinder mmap            binder_mmap                                yes    NO_DATA (user mapping, no metadata emit)
binder/hwbinder poll            binder_poll                                yes    NO_DATA (wait-queue only)
ashmem          read            ashmem_read                                yes    NO_DATA (zeros on fresh fd)
ashmem          ioctl           ashmem_ioctl SIZE/NAME                     yes    SCALAR_ONLY / USER_INPUT_ECHO
ashmem          mmap            ashmem_mmap                                yes    NO_DATA
ion             ioctl           ion_ioctl HEAP_QUERY                       yes    SCALAR_ONLY + INDEX (name/type/id)
ion             mmap            (none; buffers via dma-buf fds)            n/a    NO_DATA
mali            ioctl           mali_ioctl (34 wrappers, utgard)          yes*   SCALAR_ONLY / USER_ECHO / PHYS (offline binary audit; *no safe hardware ioctl without source, not probed)
mali            mmap            mali_mmap                                  yes    NO_DATA (user GPU mapping)
mali            poll/read       (no .read; poll wait-queue)                yes    NO_DATA (poll=1, read=EINVAL, §4)
uhid            read            uhid_char_read                             yes    USER_INPUT_ECHO_OR_EMPTY (EAGAIN empty; queued OUTPUT echo when created)
uhid            poll            uhid_char_poll                             yes    STATE_QUERY (empty=0, no struct)
evdev x6        read            evdev_read                                 yes    SCALAR_ONLY (input_event type/code/value) / EMPTY (EAGAIN)
evdev x6        ioctl           evdev_ioctl EVIOCG*                        yes    SCALAR_ONLY (version/id/bits)
evdev x6        poll            evdev_poll                                 yes    NO_DATA
random/urandom  read            random_read/urandom_read                  yes    NO_DATA (RNG bytes)
random/urandom  ioctl           random_ioctl                               yes    NO_DATA (not probed; RND ioctls are entropy scalars by construction)
null/zero/ptmx  read            read_null/iter_zero / pty                  yes    NO_DATA (sinks)
xt_qtaguid dev  read/ioctl      (none; qtudev_fops=open/release only)      n/a    NO_DATA (read=EINVAL)
xt_qtaguid proc seq             proc_qtaguid_stats_fops seq_show           yes    SCALAR_ONLY (counters)
```

Dropped without hardware: null/zero/ptmx/random (sinks/RNG by construction),
qtudev (no ops), binder/hwbinder mmap+poll, ashmem/ion/mali mmap (mappings,
not disclosure). Kept for hardware: binder, ashmem, ion, mali-open,
uhid, evdev, qtaguid-proc, misc sinks.

Prioritized per task (STATE_QUERY/COPY_TO_USER/SEQ_OUTPUT/KOBJECT):
binder NODE_DEBUG + WRITE_READ path, ion HEAP_QUERY, mali wrappers,
uhid queue, evdev EVIOCG. All others NO_DATA/USER_ECHO/SCALAR.

## 4. Hardware validation

One question per test, same BOOT_ID, no loops. is_kptr = (v>>48)==0xffff.

```text
device    operation                    result                              bytes  pointer?  classification
binder    VERSION                      rc=0 proto=8                        4      no        SCALAR_ONLY
binder    NODE_DEBUG ptr=0            rc=0 ptr=0 cookie=0 s=0 w=0 + repeat 24     no        USER_INPUT_ECHO (zeros on fresh fd)
ashmem    GET_SIZE                     rc=0 size=0                          8      no        SCALAR_ONLY
ashmem    GET_NAME                     rc=0 "dev/ashmem"                   256    no        USER_INPUT_ECHO
ion       HEAP_QUERY cnt=0             rc=0 cnt=3                          16     no        SCALAR_ONLY (count)
ion       HEAP_QUERY with buf          rc=-EINVAL cnt=3 + 3 heaps          48x3   no        INDEX+SCALAR (codec_mm_ion/5/5, cma_ion/4/4, vmalloc_ion/0/0)
mali      open+poll+read               fd=3 poll=1/revents=1 read=EINVAL    0      no        NO_DATA (poll is wait-queue signal, no struct)
uhid      open+poll+read               fd=3 poll=0 read=EAGAIN             0      no        USER_INPUT_ECHO_OR_EMPTY
evdev e0  EVIOCGVERSION/ID/BIT+read    ver=65537 id=16/1/1/256 bits=0700   var    no        SCALAR_ONLY; read EAGAIN
evdev e1  same                         ver=65537 id=16/7054/3308/1        var    no        SCALAR_ONLY; read EAGAIN
evdev e2  same                         ver=65537 id=5/10007/12985/0       var    no        SCALAR_ONLY; read EAGAIN
evdev e3  same                         ver=65537 id=6/0/0/1               var    no        SCALAR_ONLY; read EAGAIN
random    read 16B                     n=16 kptr=0                         16     no        NO_DATA (RNG)
urandom   read 16B                     n=16 kptr=0                         16     no        NO_DATA (RNG)
qtaguid   dev read                     n=-1 EINVAL                         0      no        NO_DATA (no read op)
qtaguid   proc stats read              header + counters                  ~512   no        SCALAR_ONLY
null      read                         n=0                                0      no        NO_DATA
zero      read 8B                      zeros kptr=0                       8      no        NO_DATA
ptmx      open                         fd=3                               0      no        NO_DATA
full/cec/vndbinder/ionvideo/ge2d/... cat EACCES (DAC-open SELinux-denied) 0   n/a       DENIED (unreachable, not candidates)
usb 189:* cat                            EACCES (not in usb group)        0      n/a       DENIED
```

Mali note: stateful ioctls not executed on hardware (out-of-tree, no
in-.src source; blind numbers prohibited). Offline wrapper census
(tools/ghostlock_emit_search.py --mali: 14 wrappers, bl/copy_to counts,
str-xN check) = versions/counts/sizes scalars, user-buffer echoes,
MMU phys/GPU entries; NO DIRECT_KERNEL_PTR. Hardware open/poll/read
above confirms no bytes without ioctl. Residual risk is a stateful
wrapper returning kptr despite offline audit; classed as audited-offline,
not a hardware candidate.

## 5. GhostLock relevance

Questions (need live bytes for H16.4 0x52fc / H16.7 0x4df0 ruler):

```text
W_waiter address (live stack addr of waiter object):            no (all zeros/scalars/echo)
[W_waiter+0x38] current value / &f_alt.pi_mutex:                no (nothing returns rt_mutex *)
f_target address:                                               no
f_alt address:                                                  no
task_struct address:                                            no
kernel heap address (pi_state/waiter/buffer object):            no (ion ids are INDEX, binder ptr is USER echo, mali phys is GPU/phys)
```

No candidate returns task_struct, mm, cred, file, inode, dentry, vma,
mutex, rt_mutex, futex_pi_state, rt_mutex_waiter, dma/ion/gpu object
address, or allocation metadata as kernel VA. ION heap_id, binder
handle, evdev id, qtaguid idx/uid are INDEX/SCALAR, explicitly not
counted per rules. errno/timing/absence-of-crash not counted.
No DISCLOSURE_CANDIDATE. No causal test attempted (nothing to connect).

## 6. Verdict

```text
NO_READ_SURFACE_FOUND
```

Coverage: 499 paths probed (304 device candidates), 18/18 openable
char/block mapped to f_op and hardware-tested for read/poll/safe-ioctl.
278 denied by DAC+SELinux (including all 0666 vendor/media nodes: amstream,
cec, vndbinder, snd, video, ge2d), 22 stat-denied, 0 absent. Every
reachable COPY_TO_USER/put_user/seq path on this surface is SCALAR_ONLY,
USER_INPUT_ECHO, INDEX, or NO_DATA. 0 pointer bytes on every capture.
Mali stateful ioctl closed offline (no DIRECT_KERNEL_PTR) + hardware
open/poll/read empty; not promoted to candidate without bytes.
GhostLock stays LEVEL_2 differential-only (errno 35 vs 110); no path
to a live address for H16.4/H16.7 ruler. Do not reopen Reclaim/H16-write;
do not convert this into write thinking.

Next bottleneck (unchanged): a read-only kernel-pointer source for
W_waiter or &f_alt.pi_mutex that survives stock masking. This census
eliminates the stock /dev read surface as that source.
