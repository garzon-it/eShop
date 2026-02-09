#!/usr/bin/env python3
import argparse
import os
import subprocess
import sys
from pathlib import Path

# Marker used to signal that a CI step has fully finished
DONE_MARKER = "__CIWRAP_DONE__"

def _write_marker(file_path: Path, step_name: str):
    """
    Writes an explicit end-of-step marker to the given log file.
    """
    marker_line = f"[ci.step={step_name}] {DONE_MARKER}\n".encode()
    with file_path.open("ab") as f:
        f.write(marker_line)
        f.flush()


def run_and_tee(cmd, stdout_path, stderr_path, step_name):
    """
    Executes a command, prefixes each output line with the CI step name,
    and writes stdout/stderr both to the console and to log files.
    """
    prefix = f"[ci.step={step_name}] ".encode()

    stdout_path.parent.mkdir(parents=True, exist_ok=True)
    stderr_path.parent.mkdir(parents=True, exist_ok=True)

    with stdout_path.open("ab") as out_f, stderr_path.open("ab") as err_f:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        while True:
            out_line = process.stdout.readline() if process.stdout else b""
            err_line = process.stderr.readline() if process.stderr else b""

            if not out_line and not err_line and process.poll() is not None:
                break

            if out_line:
                line = prefix + out_line
                out_f.write(line); out_f.flush()
                sys.stdout.buffer.write(line); sys.stdout.buffer.flush()

            if err_line:
                line = prefix + err_line
                err_f.write(line); err_f.flush()
                sys.stderr.buffer.write(line); sys.stderr.buffer.flush()

        return_code = process.wait()

    # Emit completion markers after the process has fully exited
    _write_marker(stdout_path, step_name)
    _write_marker(stderr_path, step_name)

    return return_code


def main():
    parser = argparse.ArgumentParser(
        description="Wraps a CI command and annotates its logs with a CI step name."
    )
    parser.add_argument("--name", required=True, help="CI step name")
    parser.add_argument(
        "--log-dir",
        default="",
        help="Optional log directory (defaults to $GITHUB_WORKSPACE/artifacts/step-logs)"
    )
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()

    if not args.command:
        print(
            'Usage: ciwrap_logs.py --name "Step name" -- <command>',
            file=sys.stderr
        )
        return 2

    # Resolve workspace path for GitHub-hosted and self-hosted runners
    workspace = os.environ.get("GITHUB_WORKSPACE", os.getcwd())
    log_dir = (
        Path(args.log_dir)
        if args.log_dir
        else Path(workspace) / "artifacts" / "step-logs"
    )

    # Create deterministic file names per CI step
    step_slug = args.name.lower().replace(" ", "_")
    stdout_path = log_dir / f"{step_slug}.stdout.log"
    stderr_path = log_dir / f"{step_slug}.stderr.log"

    cmd = args.command
    if cmd and cmd[0] == "--":
        cmd = cmd[1:]

    return run_and_tee(cmd, stdout_path, stderr_path, args.name)


if __name__ == "__main__":
    sys.exit(main())
