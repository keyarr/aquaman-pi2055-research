#!/usr/bin/env python3
"""Build the ODM candidate from odm20_ksu3.img without touching recovery."""
import hashlib
import pathlib
import shutil
import subprocess
import tempfile

WORK = pathlib.Path(__file__).resolve().parent
ROOT = WORK.parent.parent
SRC = ROOT / "odm" / "odm20_ksu3.img"
OUT = WORK / "odm20_ksu_persist.img"
MODULE = WORK / "kernelsu-persist.ko"
KSUD = WORK / "ksud-arm32"
SU_HELPER = WORK / "su-helper"

ROOT_RC = """\
on property:sys.boot_completed=1
    insmod /odm/kernelsu.ko
    exec u:r:su:s0 root root -- /odm/ksud32 allowlist probe
    exec u:r:su:s0 root root -- /odm/ksud32 allowlist load
    exec u:r:su:s0 root root -- /odm/ksud32 boot-completed
"""


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def debugfs(image, commands):
    with tempfile.TemporaryDirectory(prefix="ksu-odm-cmds-") as tmp:
        script = pathlib.Path(tmp) / "cmds"
        script.write_text("\n".join(commands) + "\n")
        subprocess.run(
            ["debugfs", "-w", "-f", str(script), str(image)],
            check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
        )


def main():
    shutil.copy2(SRC, OUT)
    with tempfile.TemporaryDirectory(prefix="ksu-odm-") as tmp:
        rc = pathlib.Path(tmp) / "root.rc"
        rc.write_text(ROOT_RC)

        # Remove the permissive module and the TCP 4444 root listener, then
        # install the control-free candidate module and the 32-bit ksud.
        debugfs(OUT, [
            "rm /etc/init/root.rc",
            f"write {rc} /etc/init/root.rc",
            "sif /etc/init/root.rc mode 100644",
            "rm /kernelsu.ko",
            f"write {MODULE} /kernelsu.ko",
            "sif /kernelsu.ko mode 100644",
            "rm /seflip.ko",
            "rm /root.sh",
            f"write {KSUD} /ksud32",
            "sif /ksud32 mode 100755",
            "mkdir /bin",
            f"write {SU_HELPER} /bin/su",
            "sif /bin/su mode 100755",
        ])

    with tempfile.TemporaryDirectory(prefix="ksu-odm-verify-") as tmp:
        ko = pathlib.Path(tmp) / "kernelsu.ko"
        extracted = subprocess.check_output(
            ["debugfs", "-R", "cat /kernelsu.ko", str(OUT)]
        )
        ko.write_bytes(extracted)
        assert sha256(ko) == sha256(MODULE), "module mismatch in ODM image"
        actual_rc = subprocess.check_output(
            ["debugfs", "-R", "cat /etc/init/root.rc", str(OUT)], text=True
        )
        assert actual_rc == ROOT_RC, "root.rc mismatch in ODM image"
        listings = subprocess.check_output(
            ["debugfs", "-R", "ls -l /", str(OUT)], text=True
        )
        assert "ksud32" in listings, "ksud32 missing in ODM image"

    lines = [
        f"# ODM candidate ({ROOT_RC.count(chr(10))} rc lines)",
        f"{sha256(OUT)}  {OUT.name}",
        f"{sha256(SRC)}  {SRC.name} (base, unchanged)",
    ]
    # debugfs rm+write creates unlabelled inodes; restore the stock SELinux
    # labels so insmod works with SELinux enforcing.
    subprocess.check_call(["bash", str(WORK / "label_odm_candidate.sh")])

    with open(WORK / "HASHES.txt", "a") as f:
        f.write("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
