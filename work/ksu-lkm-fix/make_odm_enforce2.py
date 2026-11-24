#!/usr/bin/env python3
"""Enforcing candidate: init-domain execs, sepolicy patch before insmod."""
import hashlib
import pathlib
import shutil
import subprocess
import tempfile

WORK = pathlib.Path(__file__).resolve().parent
SRC = WORK / "odm20_ksu_persist.img"
OUT = WORK / "odm20_ksu_enforce2.img"

RC = """\
on property:sys.boot_completed=1
    exec root root -- /odm/ksu_sepolicy.sh
    insmod /odm/kernelsu.ko
    exec root root -- /odm/ksud32 allowlist probe
    exec root root -- /odm/ksud32 allowlist load
    exec root root -- /odm/ksud32 boot-completed
"""

POLICY = """\
#!/system/bin/sh
/odm/ksud32 sepolicy patch "allow init system_data_file:file read;"
/odm/ksud32 sepolicy patch "permissive su;"
"""


def main():
    shutil.copy2(SRC, OUT)
    with tempfile.TemporaryDirectory(prefix="ksu-enforce2-") as tmp:
        d = pathlib.Path(tmp)
        (d / "root.rc").write_text(RC)
        (d / "ksu_sepolicy.sh").write_text(POLICY)
        script = d / "cmds"
        script.write_text(
            "rm /etc/init/root.rc\n"
            f"write {d / 'root.rc'} /etc/init/root.rc\n"
            "sif /etc/init/root.rc mode 100644\n"
            "rm /ksu_sepolicy.sh\n"
            f"write {d / 'ksu_sepolicy.sh'} /ksu_sepolicy.sh\n"
            "sif /ksu_sepolicy.sh mode 100755\n"
        )
        subprocess.run(["debugfs", "-w", "-f", str(script), str(OUT)],
                       check=True, stdout=subprocess.DEVNULL,
                       stderr=subprocess.PIPE)

    label = WORK / "label_odm_candidate.sh"
    text = label.read_text().replace(
        'echo "labelled files in $IMG"',
        'sudo setfattr -n security.selinux -v \'u:object_r:shell_exec:s0\' "$MNT/ksud32"\n'
        'sudo setfattr -n security.selinux -v \'u:object_r:shell_exec:s0\' "$MNT/ksu_sepolicy.sh"\n'
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
