#!/usr/bin/env python3
"""Poll ADB until a device is connected, then save logcat and dmesg output.

Writes:
- logcat.txt: output of `adb logcat -b all`
- dmesg.txt: output of `adb shell dmesg`

If ADB is not found in PATH, this script will also look for `adb` or
`adb.exe` in the same directory as this script.

If the script is run with `-k`, it also pulls `/proc/last_kmsg` to
`last_kmsg.txt`.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path


def find_adb() -> Path | None:
    script_dir = Path(__file__).resolve().parent
    local_adb_paths = [script_dir / "adb", script_dir / "adb.exe"]

    for local_adb in local_adb_paths:
        if local_adb.exists() and local_adb.is_file() and os.access(local_adb, os.X_OK):
            return local_adb

    adb_path = shutil.which("adb") or shutil.which("adb.exe")
    if adb_path:
        return Path(adb_path)

    for local_adb in local_adb_paths:
        if local_adb.exists() and local_adb.is_file():
            return local_adb

    return None


def adb_is_connected(adb: Path) -> bool:
    try:
        result = subprocess.run(
            [str(adb), "shell", "echo", "CONNECTED"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (subprocess.SubprocessError, OSError):
        return False

    if result.returncode != 0:
        return False

    return "CONNECTED" in result.stdout


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Poll ADB until a device is connected, then save logs."
    )
    parser.add_argument(
        "-k",
        action="store_true",
        help="pull /proc/last_kmsg to last_kmsg.txt when adb is connected",
    )
    return parser.parse_args()


def wait_for_adb(adb: Path, interval: float = 2.0) -> None:
    print(f"Waiting for ADB device on {adb}...")
    while True:
        if adb_is_connected(adb):
            print("ADB device connected.")
            return
        print("No device found yet. Retrying in %.1f seconds..." % interval)
        time.sleep(interval)


def collect_dmesg(adb: Path, output_path: Path) -> None:
    print(f"Collecting dmesg to {output_path}")
    try:
        result = subprocess.run(
            [str(adb), "shell", "dmesg"],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except subprocess.SubprocessError as exc:
        print(f"Failed to collect dmesg: {exc}", file=sys.stderr)
        return

    if result.returncode != 0:
        print(
            f"adb shell dmesg returned {result.returncode}: {result.stderr.strip()}",
            file=sys.stderr,
        )

    output_path.write_text(result.stdout, encoding="utf-8")


def collect_last_kmsg(adb: Path, output_path: Path) -> None:
    print(f"Pulling /proc/last_kmsg to {output_path}")
    try:
        result = subprocess.run(
            [str(adb), "pull", "/proc/last_kmsg", str(output_path)],
            capture_output=True,
            text=True,
            timeout=60,
        )
    except subprocess.SubprocessError as exc:
        print(f"Failed to pull last_kmsg: {exc}", file=sys.stderr)
        return

    if result.returncode != 0:
        print(
            f"adb pull /proc/last_kmsg returned {result.returncode}: {result.stderr.strip()}",
            file=sys.stderr,
        )
        return

    print(f"Pulled last_kmsg to {output_path}")


def run_logcat(adb: Path, args: list[str], output_path: Path) -> subprocess.Popen[bytes]:
    print(f"Starting logcat {' '.join(args[1:])} to {output_path}")
    out_file = output_path.open("wb")
    try:
        process = subprocess.Popen(
            [str(adb), *args],
            stdout=out_file,
            stderr=subprocess.PIPE,
        )
    except OSError as exc:
        out_file.close()
        print(f"Failed to launch adb logcat: {exc}", file=sys.stderr)
        raise

    return process


def run_logcats(adb: Path, full_path: Path, filtered_path: Path) -> None:
    full_proc = run_logcat(adb, ["logcat", "-b", "all"], full_path)
    filtered_proc = run_logcat(adb, ["logcat", "-b", "all", "*:W"], filtered_path)

    try:
        while True:
            full_done = full_proc.poll() is not None
            filtered_done = filtered_proc.poll() is not None
            if full_done and filtered_done:
                break
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("Interrupted, stopping logcat processes...")
    finally:
        for proc in (full_proc, filtered_proc):
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()

        for name, proc in (("full", full_proc), ("filtered", filtered_proc)):
            if proc.returncode not in (None, 0):
                stderr = proc.stderr.read() if proc.stderr else b""
                print(
                    f"adb logcat {name} exited with code {proc.returncode}",
                    file=sys.stderr,
                )
                if stderr:
                    print(stderr.decode(errors="replace"), file=sys.stderr)


def main() -> int:
    args = parse_args()
    adb = find_adb()
    if adb is None:
        print("ADB executable not found in PATH or script directory.", file=sys.stderr)
        return 1

    script_dir = Path(__file__).resolve().parent
    last_kmsg_path = script_dir / "last_kmsg.txt"

    wait_for_adb(adb)

    if args.k:
        collect_last_kmsg(adb, last_kmsg_path)
        return 0

    logcat_path = script_dir / "logcat.txt"
    filtered_path = script_dir / "logcat_filtered.txt"
    dmesg_path = script_dir / "dmesg.txt"

    collect_dmesg(adb, dmesg_path)
    run_logcats(adb, logcat_path, filtered_path)
    return 0


if __name__ == "__main__":
    import os

    sys.exit(main())
