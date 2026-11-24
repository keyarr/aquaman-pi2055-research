#!/usr/bin/env python3
"""Diagnostic-only ODM: persistence module + seflip + 4444, to exercise Manager UI."""
import hashlib
import pathlib
import shutil
import subprocess
import tempfile

WORK = pathlib.Path(__file__).resolve().parent
ROOT = WORK.parent.parent
BASE = ROOT / "odm" / "odm20_ksu3.img"
SRC = WORK / "odm20_ksu_persist.img"
OUT = WORK / "odm20_ksu_persist_diag.img"

RC = """\
service rootsh /odm/sh /odm/root.sh
    class main
    user root
    group root

on property:sys.boot_completed=1
    insmod /odm/seflip.ko
    insmod /odm/kernelsu.ko
    exec u:r:vendor_init:s0 root root -- /odm/ksu_sepolicy.sh
    exec u:r:su:s0 root root -- /odm/ksud32 allowlist probe
    exec u:r:su:s0 root root -- /odm/ksud32 allowlist load
    exec u:r:su:s0 root root -- /odm/ksud32 boot-completed
    setprop debug.root_service RUNNING
    start rootsh
"""


def run(cmd, **kw):
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL,
                   stderr=subprocess.PIPE, **kw)


def main():
    shutil.copy2(SRC, OUT)
    with tempfile.TemporaryDirectory(prefix="ksu-diag-") as tmp:
        d = pathlib.Path(tmp)
        rc = d / "root.rc"
        rc.write_text(RC)
        for name in ("seflip.ko", "root.sh"):
            (d / name).write_bytes(
                subprocess.check_output(
                    ["debugfs", "-R", f"cat /{name}", str(BASE)]
                )
            )
        script = d / "cmds"
        script.write_text(
            "rm /etc/init/root.rc\n"
            f"write {rc} /etc/init/root.rc\n"
            "sif /etc/init/root.rc mode 100644\n"
            f"write {d / 'seflip.ko'} /seflip.ko\n"
            "sif /seflip.ko mode 100644\n"
            f"write {d / 'root.sh'} /root.sh\n"
            "sif /root.sh mode 100755\n"
        )
        run(["debugfs", "-w", "-f", str(script), str(OUT)])

    # Reuse the labelling step, plus the two diagnostic files.
    label = WORK / "label_odm_candidate.sh"
    text = label.read_text().replace(
        'echo "labelled files in $IMG"',
        'sudo setfattr -n security.selinux -v \'u:object_r:vendor_file:s0\' "$MNT/seflip.ko"\n'
        'sudo setfattr -n security.selinux -v \'u:object_r:shell_exec:s0\' "$MNT/root.sh"\n'
        'echo "labelled files in $IMG"'
    )
    with tempfile.NamedTemporaryFile("w", suffix=".sh", dir=WORK,
                                     delete=False) as f:
        f.write(text.replace(
            "IMG=$ROOT/work/ksu-lkm-fix/odm20_ksu_persist.img",
            f"IMG={OUT}",
        ))
        tmp_script = f.name
    run(["bash", tmp_script])
    pathlib.Path(tmp_script).unlink()

    extracted = subprocess.check_output(
        ["debugfs", "-R", "cat /kernelsu.ko", str(OUT)]
    )
    expected = (WORK / "kernelsu-persist.ko").read_bytes()
    assert hashlib.sha256(extracted).digest() == hashlib.sha256(expected).digest()
    print(hashlib.sha256(OUT.read_bytes()).hexdigest(), OUT.name)


if __name__ == "__main__":
    main()
