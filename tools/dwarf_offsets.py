#!/usr/bin/env python3
"""dwarf_offsets.py — extrai offsets de structs do vmlinux via readelf DWARF.

Uso: python3 tools/dwarf_offsets.py build-aq/vmlinux
Le DW_TAG_structure_type / DW_TAG_member do --debug-dump=info em streaming
(sem carregar o dump inteiro). Primeira ocorrencia vale; divergencias
entre CUs sao contadas e reportadas.

So cobre as structs listadas em WANT. Byte order / LP64 assumidos.
"""
import re
import subprocess
import sys

WANT = {
    "task_struct": ["tasks", "prio", "static_prio", "normal_prio", "mm",
                    "real_cred", "cred", "comm", "pi_lock", "pi_waiters",
                    "pi_waiters_leftmost", "pi_blocked_on"],
    "rt_mutex_waiter": ["tree_entry", "pi_tree_entry", "task", "lock",
                        "prio", "deadline"],
    "cred": ["usage", "uid", "gid", "suid", "sgid", "euid", "egid",
             "fsuid", "fsgid", "securebits", "cap_inheritable",
             "cap_permitted", "cap_effective", "cap_bset", "cap_ambient"],
    "mm_struct": [],
    "configfs_buffer": ["count", "pos", "page", "ops", "mutex",
                        "needs_read_fill"],
    "ashmem_area": ["name", "unpinned_list", "file", "size", "prot_mask"],
    "file": ["f_pos", "f_op", "f_path"],
    "file_operations": ["read", "write", "open", "release",
                        "unlocked_ioctl", "compat_ioctl", "mmap"],
    "futex_q": ["list", "task", "lock_ptr", "key", "pi_state", "rt_waiter",
                "requeue_pi_key", "bitset"],
    "rt_mutex": ["wait_lock", "waiters", "waiters_leftmost", "owner"],
    "pipe_buffer": ["page", "offset", "len", "ops", "flags"],
    "files_struct": ["count", "fdt"],
    "fdtable": ["max_fds", "fd"],
    "rb_node": ["__rb_parent_color", "rb_right", "rb_left"],
    "list_head": ["next", "prev"],
}

DIE = re.compile(r"^ <(\d+)><[0-9a-f]+>:\s+Abbrev Number: \d+ \((DW_TAG_\w+)\)")
ATTR = re.compile(r"^\s+<[0-9a-f]+>\s+(DW_AT_\w+)\s*:\s*(.*)$")
LOC_UCONST = re.compile(r"DW_OP_plus_uconst:\s*(\d+)")


def main(path):
    res = {s: {} for s in WANT}
    size = {}
    mismatch = 0
    stack = []  # (depth, tag, struct_name or None)
    cur_struct = None
    cur_member = None
    last_die_tag = None

    p = subprocess.Popen(["readelf", "--debug-dump=info", path],
                         stdout=subprocess.PIPE, text=True,
                         errors="replace", bufsize=1 << 20)
    assert p.stdout
    for line in p.stdout:
        m = DIE.match(line)
        if m:
            depth, tag = int(m.group(1)), m.group(2)
            while stack and stack[-1][0] >= depth:
                stack.pop()
            name = None
            if tag == "DW_TAG_structure_type":
                stack.append((depth, tag, "@pending"))
                cur_struct, cur_member = "@pending", None
            elif tag == "DW_TAG_member":
                # struct dono = struct mais proximo na pilha
                owner = next((s for d, t, s in reversed(stack)
                              if t == "DW_TAG_structure_type"), None)
                cur_struct, cur_member = owner, "@pending"
            else:
                cur_struct, cur_member = None, None
            last_die_tag = tag
            continue
        m = ATTR.match(line)
        if not m:
            continue
        attr, val = m.group(1), m.group(2).strip()
        if attr == "DW_AT_name":
            if cur_struct == "@pending" and stack and stack[-1][2] == "@pending":
                stack[-1] = (stack[-1][0], stack[-1][1], val)
                cur_struct = val
            elif cur_member == "@pending":
                cur_member = val
        elif attr == "DW_AT_byte_size":
            if last_die_tag == "DW_TAG_structure_type" and stack and \
                    stack[-1][2] not in (None, "@pending"):
                try:
                    size.setdefault(stack[-1][2], int(val))
                except ValueError:
                    pass
        elif attr == "DW_AT_data_member_location":
            if (cur_struct in WANT and cur_member in WANT[cur_struct]):
                loc = LOC_UCONST.search(val)
                try:
                    off = int(loc.group(1)) if loc else int(val, 0)
                except ValueError:
                    cur_member = None
                    continue
                old = res[cur_struct].get(cur_member)
                if old is None:
                    res[cur_struct][cur_member] = off
                elif old != off:
                    mismatch += 1
            cur_member = None
    p.wait()

    for s in WANT:
        w = WANT[s]
        got = res[s]
        line = "struct %-16s size=%s" % (
            s, ("0x%x" % size[s]) if s in size else "?")
        print(line)
        for f in w:
            v = got.get(f)
            print("  %-20s %s" % (f, ("0x%x" % v) if v is not None else "MISSING"))
        if not w and s in size:
            pass
        extra = sorted(set(got) - set(w))
        for f in extra:
            print("  %-20s 0x%x (extra)" % (f, got[f]))
    print("mismatches across CUs: %d" % mismatch)


if __name__ == "__main__":
    main(sys.argv[1])
