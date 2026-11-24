#!/usr/bin/env python3
"""Diagnostic only: Enforcing + root listener, to capture the packages.list AVC."""
import hashlib
import pathlib
import shutil
import subprocess
import tempfile

WORK = pathlib.Path(__file__).resolve().parent
BASE = WORK.parent.parent / "odm" / "odm20_ksu3.img"
SRC = WORK / "odm20_ksu_persist.img"
OUT = WORK / "odm20_ksu_avc2.img"

RC = """\
service rootsh /odm/sh /odm/root.sh
    class main
    user root
    group root

on property:sys.boot_completed=1
    insmod /odm/kernelsu.ko
    exec u:r:vendor_init:s0 root root -- /odm/ksu_sepolicy.sh
    exec u:r:su:s0 root root -- /odm/ksud32 allowlist probe
    exec u:r:su:s0 root root -- /odm/ksud32 allowlist load
    exec u:r:su:s0 root root -- /odm/ksud32 boot-completed
    setprop debug.root_service RUNNING
    start rootsh
"""


def main():
    shutil.copy2(SRC, OUT)
    with tempfile.TemporaryDirectory(prefix="ksu-avc-") as tmp:
        d = pathlib.Path(tmp)
        (d / "root.rc").write_text(RC)
        (d / "root.sh").write_bytes(
            subprocess.check_output(["debugfs", "-R", "cat /root.sh", str(BASE)])
        )
        script = d / "cmds"
        script.write_text(
            "rm /etc/init/root.rc\n"
            f"write {d / 'root.rc'} /etc/init/root.rc\n"
            "rm /root.sh\n"
            f"write {d / 'root.sh'} /root.sh\n"
            "sif /root.sh mode 100755\n"
        )
        subprocess.run(["debugfs", "-w", "-f", str(script), str(OUT)],
                       check=True, stdout=subprocess.DEVNULL,
                       stderr=subprocess.PIPE)

    label = WORK / "label_odm_candidate.sh"
    text = label.read_text().replace(
        'echo "labelled files in $IMG"',
        'sudo setfattr -n security.selinux -v \'u:object_r:shell_exec:s0\' "$MNT/root.sh"\n'
        'echo "labelled files in $IMG"'
    ).replace(
        "IMG=$ROOT/work/ksu-lkm-fix/odm20_ksu_persist.img", f"IMG={OUT}"
    )
    with tempfile.NamedTemporaryFile("w", suffix=".sh", dir=WORK,
                                     delete=False) as f:
        f.write(text)
        script = f.name
    subprocess.run(["bash", script], check=True, stdout=subprocess.DEVNULL)
    pathlib.Path(script).unlink()

    print(hashlib.sha256(OUT.read_bytes()).hexdigest(), OUT.name)


if __name__ == "__main__":
    main()
