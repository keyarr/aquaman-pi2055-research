#!/usr/bin/env python3
"""Static compatibility checks for the KernelSU LKM candidates."""
import pathlib
import re
import subprocess
import sys

WORK = pathlib.Path(__file__).resolve().parent
MODULES = [
    WORK / "ref" / "kernelsu_stock_from_odm.ko",
    WORK / "ref" / "kernelsu_stock_img.ko",
    WORK / "kernelsu-control.ko",
    WORK / "kernelsu-persist.ko",
]
SYMVERS = WORK / "kernel-obj" / "Module.symvers"


def readelf_symbols(ko):
    out = subprocess.check_output(["readelf", "-sW", str(ko)], text=True)
    funcs, undefined = set(), set()
    for line in out.splitlines():
        parts = line.split()
        if len(parts) < 8 or not parts[0].rstrip(":").isdigit():
            continue
        name = parts[7]
        if parts[3] == "FUNC" and parts[6] != "UND":
            funcs.add(name)
        if parts[6] == "UND":
            undefined.add(name)
    return funcs, undefined


def version_crcs(ko):
    raw = WORK / "versions.bin"
    subprocess.check_call(
        ["/home/erick/Android/Sdk/ndk/28.2.13676358/toolchains/llvm/prebuilt/linux-x86_64/bin/llvm-objcopy",
         "--dump-section", f"__versions={raw}", str(ko)]
    )
    data = raw.read_bytes()
    result = {}
    # struct modversion_info { unsigned long crc; char name[56]; } = 64 bytes.
    for off in range(0, len(data) - 63, 64):
        entry = data[off : off + 64]
        crc = entry[:4][::-1].hex()
        name = entry[8:].split(b"\0")[0].decode("ascii", "replace")
        if name:
            result[name] = crc
    raw.unlink()
    return result


def main():
    symvers = {}
    for line in SYMVERS.read_text().splitlines():
        parts = line.split("\t")
        if len(parts) >= 2:
            symvers[parts[1]] = parts[0]

    ok = True
    functions = {}
    for ko in MODULES:
        funcs, undefined = readelf_symbols(ko)
        functions[ko.name] = funcs
        crcs = version_crcs(ko)
        missing = sorted(s for s in undefined if s not in symvers)
        bad_crc = sorted(
            n for n, crc in crcs.items() if n in symvers and symvers[n] != crc
        )
        unresolved = sorted(s for s in crcs if s not in symvers)
        print(f"{ko.name}: funcs={len(funcs)} undefined={len(undefined)} "
              f"versions={len(crcs)}")
        print(f"  missing symbols: {missing or 'none'}")
        print(f"  CRC mismatch: {bad_crc or 'none'}")
        print(f"  no symvers entry: {unresolved or 'none'}")
        if missing or bad_crc or unresolved:
            ok = False

    stock = functions[MODULES[0].name]
    control = functions[MODULES[2].name]
    persist = functions[MODULES[3].name]
    print(f"control-only funcs vs stock: {sorted(control - stock) or 'none'}")
    print(f"stock-only funcs vs control: {sorted(stock - control) or 'none'}")
    print(f"persist-only funcs vs control: {sorted(persist - control) or 'none'}")
    print(f"control-only funcs vs persist: {sorted(control - persist) or 'none'}")

    required = {
        "ksu_allowlist_blob_size",
        "ksu_allowlist_blob_read",
        "ksu_allowlist_blob_write",
        "ksu_allowlist_save_pending",
        "ksu_allowlist_probe_open",
    }
    if not required <= persist:
        print(f"FAIL: missing protocol symbols: {sorted(required - persist)}")
        ok = False
    if "do_save_allow_list" in persist or "do_load_allow_list" in persist:
        print("FAIL: kernel file I/O still compiled into persist candidate")
        ok = False

    print("STATIC_CHECK:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
