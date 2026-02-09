#!/usr/bin/env python3
import argparse
import os
import shlex
import subprocess
import sys
from pathlib import Path

def run_and_tee(cmd, stdout_path, stderr_path, step_name):
    prefix = f"[ci.step={step_name}] "

    stdout_path.parent.mkdir(parents=True, exist_ok=True)
    stderr_path.parent.mkdir(parents=True, exist_ok=True)

    with stdout_path.open("wb") as out_f, stderr_path.open("wb") as err_f:
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        while True:
            o = p.stdout.readline() if p.stdout else b""
            e = p.stderr.readline() if p.stderr else b""
            if not o and not e and p.poll() is not None:
                break

            if o:
                line = prefix.encode() + o
                out_f.write(line)
                out_f.flush()
                sys.stdout.buffer.write(line)
                sys.stdout.buffer.flush()

            if e:
                line = prefix.encode() + e
                err_f.write(line)
                err_f.flush()
                sys.stderr.buffer.write(line)
                sys.stderr.buffer.flush()

        return p.wait()

def main():
    ap = argparse.ArgumentParser(
        description="Wrap a CI command and tag stdout/stderr with ci.step.name"
    )
    ap.add_argument("--name", required=True, help="CI step name")
    ap.add_argument(
        "--log-dir",
        default="",
        help="Override log dir (default: $GITHUB_WORKSPACE/artifacts/logs)",
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
