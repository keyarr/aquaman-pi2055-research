#!/usr/bin/env python3
"""fastboot_probe.py - safe read-only fastboot probing for aquaman.
Only runs GETVAR + safe OEM read-only commands by default.
No flash/erase/format/saveenv/setenv. Fuzzing requires --fuzz flag
and still never writes flash.
Usage:
  python3 fastboot_probe.py            # safe getvar table
  python3 fastboot_probe.py --oem      # + safe oem echo/printenv/version/help
  python3 fastboot_probe.py --fuzz --start 513 --stop 1056 --step list
"""
import subprocess, sys, time

def run(cmd, timeout=10):
    t0 = time.time()
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        out = (p.stdout + p.stderr).strip()
        return out, time.time() - t0, p.returncode
    except subprocess.TimeoutExpired:
        return "TIMEOUT", time.time() - t0, -1

def getvar(v):
    out, dt, rc = run(["fastboot", "getvar", v])
    # fastboot prints "v: value" on stderr merged
    return out, dt, rc

SAFE_GETVARS = ["product", "version-bootloader", "version", "unlocked", "secure",
                "max-download-size", "serialno", "version-baseband", "bootloader-version"]

# read-only OEM: echo/printenv/version/help run no flash writes.
# NOTE: on aquaman, 'oem X' is passthrough to U-Boot run_command(X).
# echo, printenv, version, help are safe. NEVER add setenv/saveenv here.
SAFE_OEMS = ["echo probe_hello", "printenv lock", "version", "help"]

def main():
    oem = "--oem" in sys.argv
    print("cmd | response | duration_s")
    print("--- | --- | ---")
    for v in SAFE_GETVARS:
        out, dt, rc = getvar(v)
        one = " | ".join(out.splitlines()[:3]).replace("|", "/")[:160]
        print(f"getvar {v} | {one} | {dt:.2f}")
    if oem:
        for c in SAFE_OEMS:
            out, dt, rc = run(["fastboot", "oem", c])
            one = " | ".join(out.splitlines()[:4]).replace("|", "/")[:200]
            print(f"oem {c} | {one} | {dt:.2f}")
    # checkpoint
    print("\ncheckpoint: expect unlocked: yes / secure: no")

if __name__ == "__main__":
    main()
