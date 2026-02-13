#!/usr/bin/env python3
"""Wrap a CI command: stream stdout/stderr to console and export as OTLP logs + trace span.

Usage:
  ciwrap_logs.py --name "Step name" -- <command>   # wrap a command
  ciwrap_logs.py --init-trace                      # start trace context
  ciwrap_logs.py --finish-trace                    # export job span
"""

import argparse
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


def _create_log_emitter(step_name, trace_id_hex, span_id_hex):
    """Create an OTLP log emitter for a CI step. Returns (emit_fn, shutdown_fn)."""
    resource = Resource.create({"service.name": "ci-observability"})
    provider = LoggerProvider(resource=resource)
    provider.add_log_record_processor(BatchLogRecordProcessor(OTLPLogExporter()))
    logger = provider.get_logger("ci-observability")

    trace_id_int = int(trace_id_hex, 16) if trace_id_hex else 0
    span_id_int = int(span_id_hex, 16) if span_id_hex else 0
    flags = TraceFlags(TraceFlags.SAMPLED) if trace_id_hex else TraceFlags.DEFAULT

    def emit(body, severity="INFO", extra_attrs=None):
        sev_num = SeverityNumber.ERROR if severity == "ERROR" else SeverityNumber.INFO
        attrs = {"cicd.pipeline.task.name": step_name}
        if extra_attrs:
            attrs.update(extra_attrs)
        logger.emit(LogRecord(
            timestamp=time.time_ns(),
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


def _reader(stream, console, emit, severity, source):
    """Read lines from stream, write to console, and emit OTLP log records."""
    for raw in iter(stream.readline, b""):
        console.write(raw)
        console.flush()
        line = raw.decode("utf-8", errors="replace").rstrip("\n\r")
        if line:
            emit(line, severity=severity, extra_attrs={"log.source": source})
    stream.close()


def run_and_tee(cmd, emit):
    """Run cmd, stream output to console, and emit each line as an OTLP log record."""
    t0 = time.monotonic()

    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    t_out = threading.Thread(target=_reader,
                             args=(p.stdout, sys.stdout.buffer, emit, "INFO", "stdout"))
    t_err = threading.Thread(target=_reader,
                             args=(p.stderr, sys.stderr.buffer, emit, "ERROR", "stderr"))
    t_out.start()
    t_err.start()
    t_out.join()
    t_err.join()

    exit_code = p.wait()
    result = "failure" if exit_code != 0 else "success"

    duration = time.monotonic() - t0
    summary = f"__STEP_RESULT__ duration_seconds={duration:.2f} result={result}"
    emit(summary, extra_attrs={
        "log.source": "stdout",
        "cicd.pipeline.task.run.duration": duration, # ! not in OTEL semantic convention
        "cicd.pipeline.task.run.result": result,
    })
    sys.stdout.buffer.write(f"{summary}\n".encode())
    sys.stdout.buffer.flush()

    return exit_code, duration


# CLI dispatch

def cmd_run_step(args):
    """Run a wrapped command, emit logs via OTLP, and export a step span."""
    trace_id, span_id = traces.get_step_ids(args.name)
    emit, shutdown_logs = _create_log_emitter(args.name, trace_id, span_id)

    cmd = args.command
    if cmd[0] == "--":
        cmd = cmd[1:]

    start_ns = time.time_ns()
    exit_code, duration = run_and_tee(cmd, emit)
    end_ns = time.time_ns()

    shutdown_logs()

    traces.export_step_span(args.name, start_ns, end_ns, exit_code, duration)

    return exit_code


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--name", default=None, help="CI step name")
    ap.add_argument("--init-trace", action="store_true",
                    help="Initialize trace context (write trace-context.json)")
    ap.add_argument("--finish-trace", action="store_true",
                    help="Finalize trace and export job span")
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
