#!/usr/bin/env python3
"""Wrap a CI command: stream stdout/stderr to console and export as OTLP logs + trace span.

Usage:
  ciwrap_logs.py --name "Step name" -- <command>   # wrap a command
  ciwrap_logs.py --init-trace                      # start trace context
  ciwrap_logs.py --finish-trace                    # export job span
"""

import argparse
import os
import subprocess
import sys
import threading
import time

from opentelemetry._logs import LogRecord, SeverityNumber
from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter
from opentelemetry.sdk._logs import LoggerProvider
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.sdk.resources import Resource
from opentelemetry.trace import TraceFlags

import ciwrap_traces as traces


class _ProcessMetricsCollector:
    """Polls a subprocess periodically and records peak CPU, RSS, and cumulative I/O.

    Only instantiated when --process-metrics is passed.  Requires psutil.
    Runs on a daemon thread so it never blocks the main flow.
    """

    def __init__(self, pid, interval=1.0, include_children=False):
        self._pid = pid
        self._interval = interval
        self._include_children = include_children
        self._samples = []  # list of (cpu_percent, rss_bytes, read_bytes, write_bytes)
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def start(self):
        self._thread.start()

    def stop(self):
        self._stop.set()
        self._thread.join(timeout=self._interval * 3 + 2)

    def _live_procs(self):
        import psutil
        try:
            root = psutil.Process(self._pid)
            procs = [root]
            if self._include_children:
                procs += root.children(recursive=True)
            return [p for p in procs if p.is_running()]
        except psutil.NoSuchProcess:
            return []

    def _run(self):
        import psutil
        # First cpu_percent() call always returns 0.0 — it just sets the baseline.
        for p in self._live_procs():
            try:
                p.cpu_percent()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

        while not self._stop.is_set():
            self._stop.wait(self._interval)
            procs = self._live_procs()
            if not procs:
                break
            try:
                cpu = sum(p.cpu_percent() for p in procs)
                rss = sum(p.memory_info().rss for p in procs)
                try:
                    io = psutil.Process(self._pid).io_counters()
                    read_bytes, write_bytes = io.read_bytes, io.write_bytes
                except (psutil.AccessDenied, AttributeError, psutil.NoSuchProcess):
                    read_bytes = write_bytes = None
                self._samples.append((cpu, rss, read_bytes, write_bytes))
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                break

    def summary(self):
        """Return peak/total resource usage as a flat dict ready to merge into span attributes."""
        if not self._samples:
            return {}
        cpu_vals = [s[0] for s in self._samples]
        rss_vals = [s[1] for s in self._samples]
        result = {
            "process.cpu.max_percent": max(cpu_vals),
            "process.memory.rss.max_bytes": max(rss_vals),
        }
        io_samples = [(s[2], s[3]) for s in self._samples if s[2] is not None]
        if len(io_samples) >= 2:
            result["process.disk.read_bytes"] = io_samples[-1][0] - io_samples[0][0]
            result["process.disk.write_bytes"] = io_samples[-1][1] - io_samples[0][1]
        return result


def _create_log_emitter(step_name, trace_id_hex, span_id_hex):
    """Create an OTLP log emitter for a CI step. Returns (emit_fn, shutdown_fn)."""
    service_name = os.environ.get("CI_SERVICE_NAME", "cicd-pipeline")
    job_target = os.environ.get("CI_JOB_TARGET", "")
    resource = Resource.create({"service.name": service_name, "cicd.job.target": job_target})
    provider = LoggerProvider(resource=resource)
    provider.add_log_record_processor(BatchLogRecordProcessor(OTLPLogExporter(timeout=5)))
    logger = provider.get_logger("ci-observability")

    trace_id_int = int(trace_id_hex, 16) if trace_id_hex else 0
    span_id_int = int(span_id_hex, 16) if span_id_hex else 0
    flags = TraceFlags(TraceFlags.SAMPLED) if trace_id_hex else TraceFlags.DEFAULT

    def emit(body, severity="INFO", timestamp_ns=None, extra_attrs=None):
        sev_num = SeverityNumber.ERROR if severity == "ERROR" else SeverityNumber.INFO
        attrs = {"cicd.pipeline.task.name": step_name}
        if extra_attrs:
            attrs.update(extra_attrs)
        logger.emit(LogRecord(
            timestamp=timestamp_ns or time.time_ns(),
            trace_id=trace_id_int,
            span_id=span_id_int,
            trace_flags=flags,
            severity_text=severity,
            severity_number=sev_num,
            body=body,
            attributes=attrs,
        ))

    def shutdown():
        provider.force_flush()
        provider.shutdown()

    return emit, shutdown


def _reader(stream, console, buffer, source):
    """Read lines from stream, write to console in real time, and buffer for later OTLP export."""
    for raw in iter(stream.readline, b""):
        console.write(raw)
        console.flush()
        line = raw.decode("utf-8", errors="replace").rstrip("\n\r")
        if line:
            buffer.append((time.time_ns(), line, source))
    stream.close()


def run_and_tee(cmd, emit, process_metrics_opts=None):
    """Run cmd, stream output to console, buffer logs, then emit with severity based on exit code.

    process_metrics_opts: dict with 'interval' (float, seconds) and 'include_children' (bool),
                          or None to disable process-level metric collection.
    Returns (exit_code, duration, process_metrics_summary).
    """
    t0 = time.monotonic()
    log_buffer = []  # list of (timestamp_ns, body, source)

    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    metrics_collector = None
    if process_metrics_opts is not None:
        metrics_collector = _ProcessMetricsCollector(
            p.pid,
            interval=process_metrics_opts.get("interval", 1.0),
            include_children=process_metrics_opts.get("include_children", False),
        )
        metrics_collector.start()

    t_out = threading.Thread(target=_reader,
                             args=(p.stdout, sys.stdout.buffer, log_buffer, "stdout"))
    t_err = threading.Thread(target=_reader,
                             args=(p.stderr, sys.stderr.buffer, log_buffer, "stderr"))
    t_out.start()
    t_err.start()
    t_out.join()
    t_err.join()

    exit_code = p.wait()

    process_metrics = {}
    if metrics_collector is not None:
        metrics_collector.stop()
        process_metrics = metrics_collector.summary()

    result = "failure" if exit_code != 0 else "success"
    summary_severity = "ERROR" if exit_code != 0 else "INFO"

    # Flush buffered logs — severity based on stream source
    for ts, body, source in log_buffer:
        severity = "ERROR" if source == "stderr" else "INFO"
        emit(body, severity=severity, timestamp_ns=ts,
             extra_attrs={"log.source": source})

    duration = time.monotonic() - t0
    summary = f"__STEP_RESULT__ duration_seconds={duration:.2f} result={result}"
    emit(summary, severity=summary_severity, extra_attrs={
        "log.source": "stdout",
        "cicd.pipeline.task.run.duration": duration, # ! not in OTEL semantic convention
        "cicd.pipeline.task.run.result": result,
    })
    sys.stdout.buffer.write(f"{summary}\n".encode())
    sys.stdout.buffer.flush()

    return exit_code, duration, process_metrics


# CLI dispatch

def cmd_run_step(args):
    """Run a wrapped command, emit logs via OTLP, and export a step span."""
    trace_id, span_id = traces.get_step_ids(args.name)
    if trace_id is None:
        print(f"WARNING: No trace context found for step '{args.name}'. "
              f"Did you forget to run --init-trace?",
              file=sys.stderr)
    emit, shutdown_logs = _create_log_emitter(args.name, trace_id, span_id)

    cmd = args.command
    if cmd[0] == "--":
        cmd = cmd[1:]

    process_metrics_opts = None
    if args.process_metrics:
        try:
            import psutil  # noqa: F401
        except ImportError:
            print("WARNING: --process-metrics requires psutil. "
                  "Run: pip install psutil", file=sys.stderr)
        else:
            process_metrics_opts = {
                "interval": args.process_sample_interval,
                "include_children": args.process_include_children,
            }

    start_ns = time.time_ns()
    exit_code, duration, process_metrics = run_and_tee(cmd, emit, process_metrics_opts)
    end_ns = time.time_ns()

    shutdown_logs()

    traces.export_step_span(args.name, start_ns, end_ns, exit_code, duration, process_metrics)

    return exit_code


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--name", default=None, help="CI step name")
    ap.add_argument("--init-trace", action="store_true",
                    help="Initialize trace context (write trace-context.json)")
    ap.add_argument("--finish-trace", action="store_true",
                    help="Finalize trace and export job span")
    ap.add_argument("--process-metrics", action="store_true",
                    help="Collect peak CPU/RSS/IO for the subprocess (requires psutil)")
    ap.add_argument("--process-include-children", action="store_true",
                    help="Aggregate child processes into process metrics")
    ap.add_argument("--process-sample-interval", type=float, default=1.0, metavar="SECONDS",
                    help="Sampling interval for process metrics in seconds (default: 1.0)")
    ap.add_argument("command", nargs=argparse.REMAINDER)
    args = ap.parse_args()

    if args.init_trace:
        return traces.init_trace()

    if args.finish_trace:
        return traces.finish_trace()

    if not args.name:
        ap.print_usage(sys.stderr)
        return 2

    if not args.command:
        print("Usage: ciwrap_logs.py --name \"Step name\" -- <command>", file=sys.stderr)
        return 2

    return cmd_run_step(args)


if __name__ == "__main__":
    sys.exit(main())
