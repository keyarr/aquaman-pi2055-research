#!/usr/bin/env python3
"""Control ODM image: base ODM with only kernelsu.ko swapped for the control build."""
import hashlib
import pathlib
import shutil
import subprocess
import tempfile

WORK = pathlib.Path(__file__).resolve().parent
ROOT = WORK.parent.parent
SRC = ROOT / "odm" / "odm20_ksu3.img"
OUT = WORK / "odm20_ksu_control.img"
MODULE = WORK / "kernelsu-control.ko"


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    shutil.copy2(SRC, OUT)
    with tempfile.TemporaryDirectory(prefix="ksu-odm-control-") as tmp:
        script = pathlib.Path(tmp) / "cmds"
        script.write_text(
            f"rm /kernelsu.ko\nwrite {MODULE} /kernelsu.ko\n"
            "sif /kernelsu.ko mode 100644\n"
        )
        subprocess.run(
            ["debugfs", "-w", "-f", str(script), str(OUT)],
            check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
        )
    extracted = subprocess.check_output(
        ["debugfs", "-R", "cat /kernelsu.ko", str(OUT)]
    )
    assert hashlib.sha256(extracted).hexdigest() == sha256(MODULE)
    print(sha256(OUT), OUT.name)


if __name__ == "__main__":
    main()
