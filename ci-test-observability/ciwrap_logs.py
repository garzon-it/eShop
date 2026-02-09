#!/usr/bin/env python3
import argparse
import os
import shlex
import subprocess
import sys
import threading
import time
from pathlib import Path


def _reader(stream, log_file, prefix, console):
    """Read lines from *stream* and write them to *log_file* and *console*."""
    for raw in iter(stream.readline, b""):
        line = prefix + raw
        log_file.write(line)
        log_file.flush()
        console.write(line)
        console.flush()
    stream.close()


def run_and_tee(cmd, stdout_path, stderr_path, step_name):
    prefix = f"[ci.step={step_name}] ".encode()

    stdout_path.parent.mkdir(parents=True, exist_ok=True)
    stderr_path.parent.mkdir(parents=True, exist_ok=True)

    t0 = time.monotonic()

    with stdout_path.open("wb") as out_f, stderr_path.open("wb") as err_f:
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        t_out = threading.Thread(target=_reader, args=(p.stdout, out_f, prefix, sys.stdout.buffer))
        t_err = threading.Thread(target=_reader, args=(p.stderr, err_f, prefix, sys.stderr.buffer))
        t_out.start()
        t_err.start()
        t_out.join()
        t_err.join()

        exit_code = p.wait()

    duration = time.monotonic() - t0
    summary = f"[ci.step={step_name}] __STEP_RESULT__ duration_seconds={duration:.2f} exit_code={exit_code}\n".encode()
    with stdout_path.open("ab") as out_f:
        out_f.write(summary)
        out_f.flush()
    sys.stdout.buffer.write(summary)
    sys.stdout.buffer.flush()

    return exit_code

def main():
    ap = argparse.ArgumentParser(
        description="Wrap a CI command and tag stdout/stderr with ci.step.name"
    )
    ap.add_argument("--name", required=True, help="CI step name")
    ap.add_argument(
        "--log-dir",
        default="",
        help="Override log dir (default: $GITHUB_WORKSPACE/artifacts/step-logs)",
    )
    ap.add_argument("command", nargs=argparse.REMAINDER)
    args = ap.parse_args()

    if not args.command:
        print("Usage: ciwrap_logs.py --name \"Step name\" -- <command>", file=sys.stderr)
        return 2

    workspace = os.environ.get("GITHUB_WORKSPACE", os.getcwd())
    log_dir = Path(args.log_dir) if args.log_dir else Path(workspace) / "artifacts" / "step-logs"

    step_slug = args.name.lower().replace(" ", "_")
    stdout_path = log_dir / f"{step_slug}.stdout.log"
    stderr_path = log_dir / f"{step_slug}.stderr.log"

    cmd = args.command
    if cmd[0] == "--":
        cmd = cmd[1:]

    return run_and_tee(cmd, stdout_path, stderr_path, args.name)

if __name__ == "__main__":
    sys.exit(main())
