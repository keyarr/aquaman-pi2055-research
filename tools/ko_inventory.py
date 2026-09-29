#!/usr/bin/env python3
"""Inventory of vendor .ko files: modinfo fields + ELF arch + srcversion.

usage: ko_inventory.py <dir-with-.ko> [--json out.json] [--md out.md]
Only stdlib + /usr/bin/modinfo, no root, no device.
"""
import json
import os
import re
import struct
import subprocess
import sys

KEEP = ("filename", "alias", "license", "author", "description", "depends",
        "vermagic", "srcversion", "intree", "retpoline", "name", "version")


def elf_info(path):
    with open(path, "rb") as f:
        head = f.read(64)
    if head[:4] != b"\x7fELF":
        return {"arch": "not-elf"}
    bits = {1: 32, 2: 64}[head[4]]
    endian = "little" if head[5] == 1 else "big"
    machine = struct.unpack_from("<H" if endian == "little" else ">H", head, 18)[0]
    return {
        "arch": "%s-bit elf, machine 0x%x%s" % (bits, machine,
                                                " (aarch64)" if machine == 0xb7 else ""),
        "endian": endian,
    }


def modinfo(path):
    out = subprocess.run(["modinfo", path], capture_output=True, text=True)
    info = {}
    for line in out.stdout.splitlines():
        if ":" not in line:
            continue
        key, _, val = line.partition(":")
        key, val = key.strip(), val.strip()
        if key in KEEP:
            info[key] = val
    return info


def main():
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    root = sys.argv[1]
    mods = {}
    for name in sorted(os.listdir(root)):
        if not name.endswith(".ko"):
            continue
        path = os.path.join(root, name)
        entry = {"size": os.path.getsize(path)}
        entry.update(elf_info(path))
        entry.update(modinfo(path))
        mods[name] = entry

    vermagics = sorted({m.get("vermagic", "?") for m in mods.values()})
    archs = sorted({m.get("arch", "?") for m in mods.values()})

    if "--json" in sys.argv:
        with open(sys.argv[sys.argv.index("--json") + 1], "w") as f:
            json.dump(mods, f, indent=2, sort_keys=True)

    if "--md" in sys.argv:
        rows = []
        for name, m in mods.items():
            rows.append("| %s | %d | %s | %s | %s |" % (
                name, m["size"], m.get("vermagic", "?"),
                "arm64" if "aarch64" in m.get("arch", "") else m.get("arch", "?"),
                m.get("srcversion", "-")))
        with open(sys.argv[sys.argv.index("--md") + 1], "w") as f:
            f.write("| module | size | vermagic | arch | srcversion |\n")
            f.write("|---|---|---|---|---|\n")
            f.write("\n".join(rows) + "\n")

    print("modules: %d" % len(mods))
    print("vermagic: %s" % ", ".join(vermagics))
    print("arch: %s" % ", ".join(archs))
    for name, m in sorted(mods.items()):
        print("  %-22s %8d  %s" % (name, m["size"], m.get("depends", "-")))


if __name__ == "__main__":
    main()
