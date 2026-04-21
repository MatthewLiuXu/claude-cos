#!/usr/bin/env python3
"""Claude COS — Chief of Staff CLI. Orchestrates inbox scan via Claude Code."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
import tomllib
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent
DEFAULT_CONFIG_PATH = PROJECT_DIR / "config.toml"


# ── Config ────────────────────────────────────────────────────────────────────


@dataclass
class Config:
    prompt_file: str = "inbox-scan.md"
    max_retries: int = 2
    retry_delay_seconds: int = 10
    timeout_seconds: int = 300
    log_dir: str = "logs"
    retention_days: int = 30
    verbose: bool = False
    claude_command: str = "claude"
    claude_extra_args: list[str] = field(default_factory=list)


def load_config(path: str | Path = DEFAULT_CONFIG_PATH) -> Config:
    path = Path(path)
    cfg = Config()
    if not path.exists():
        return cfg
    with open(path, "rb") as f:
        raw = tomllib.load(f)
    scan = raw.get("scan", {})
    log = raw.get("logging", {})
    claude = raw.get("claude", {})
    cfg.prompt_file = scan.get("prompt_file", cfg.prompt_file)
    cfg.max_retries = scan.get("max_retries", cfg.max_retries)
    cfg.retry_delay_seconds = scan.get("retry_delay_seconds", cfg.retry_delay_seconds)
    cfg.timeout_seconds = scan.get("timeout_seconds", cfg.timeout_seconds)
    cfg.log_dir = log.get("log_dir", cfg.log_dir)
    cfg.retention_days = log.get("retention_days", cfg.retention_days)
    cfg.verbose = log.get("verbose", cfg.verbose)
    cfg.claude_command = claude.get("command", cfg.claude_command)
    cfg.claude_extra_args = claude.get("extra_args", cfg.claude_extra_args)
    return cfg


# ── Summary parsing ───────────────────────────────────────────────────────────


@dataclass
class ParsedSummary:
    emails_found: int = 0
    emails_skipped: int = 0
    emails_read: int = 0
    tasks_created: int = 0
    duplicates_skipped: int = 0
    hygiene_updates: int = 0
    has_errors: bool = False


def _extract_int(pattern: str, text: str) -> int:
    m = re.search(pattern, text)
    return int(m.group(1)) if m else 0


def parse_summary(output: str) -> ParsedSummary | None:
    marker = "INBOX SCAN COMPLETE"
    if marker not in output:
        return None
    block = output[output.index(marker) :]
    return ParsedSummary(
        emails_found=_extract_int(r"Total found:\s+(\d+)", block),
        emails_skipped=_extract_int(r"Skipped \(noise\):\s+(\d+)", block),
        emails_read=_extract_int(r"Read in full:\s+(\d+)", block),
        tasks_created=_extract_int(r"TASKS CREATED\s+\((\d+) new\)", block),
        duplicates_skipped=_extract_int(r"DUPLICATES SKIPPED\s+\((\d+)\)", block),
        hygiene_updates=_extract_int(r"HYGIENE UPDATES\s+\((\d+)", block),
        has_errors="Errors:" in block,
    )


# ── Claude execution ─────────────────────────────────────────────────────────


DRY_RUN_PREAMBLE = (
    "DRY RUN MODE: Do NOT create or update any Notion pages. "
    "Do NOT write to last-scan-timestamp.json. "
    "Instead, go through all phases but only DESCRIBE what you would do. "
    "Still search Gmail and read emails normally.\n\n"
)


@dataclass
class ScanResult:
    exit_code: int
    stdout: str
    stderr: str
    duration_seconds: float
    success: bool
    summary: ParsedSummary | None


def run_claude(config: Config, dry_run: bool = False) -> ScanResult:
    prompt_path = PROJECT_DIR / config.prompt_file
    prompt_text = prompt_path.read_text()
    if dry_run:
        prompt_text = DRY_RUN_PREAMBLE + prompt_text

    cmd = [config.claude_command, "-p", prompt_text, *config.claude_extra_args]
    start = time.monotonic()
    timed_out = False
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=config.timeout_seconds,
            cwd=PROJECT_DIR,
        )
        exit_code = proc.returncode
        stdout, stderr = proc.stdout, proc.stderr
    except subprocess.TimeoutExpired as e:
        exit_code = -1
        stdout = (e.stdout or b"").decode() if isinstance(e.stdout, bytes) else (e.stdout or "")
        stderr = (e.stderr or b"").decode() if isinstance(e.stderr, bytes) else (e.stderr or "")
        timed_out = True
    duration = time.monotonic() - start

    summary = parse_summary(stdout)
    success = exit_code == 0 and not timed_out
    if summary and summary.has_errors:
        success = False

    return ScanResult(
        exit_code=exit_code,
        stdout=stdout,
        stderr=stderr,
        duration_seconds=round(duration, 1),
        success=success,
        summary=summary,
    )


TRANSIENT_PATTERNS = ["rate limit", "timeout", "connection", "econnreset", "overloaded"]


def is_transient(result: ScanResult) -> bool:
    if result.exit_code == -1:  # timeout
        return True
    combined = (result.stdout + result.stderr).lower()
    return any(p in combined for p in TRANSIENT_PATTERNS)


def run_with_retries(config: Config, dry_run: bool = False) -> ScanResult:
    attempts = config.max_retries + 1
    for attempt in range(1, attempts + 1):
        result = run_claude(config, dry_run)
        if result.success:
            return result
        if not is_transient(result) or attempt == attempts:
            return result
        print(f"  Transient failure (attempt {attempt}/{attempts - 1}), retrying in {config.retry_delay_seconds}s...")
        time.sleep(config.retry_delay_seconds)
    return result  # unreachable, but keeps type checker happy


# ── Logging ───────────────────────────────────────────────────────────────────


def save_log(config: Config, result: ScanResult, dry_run: bool) -> Path:
    log_dir = PROJECT_DIR / config.log_dir
    log_dir.mkdir(exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
    prefix = "dry-run-" if dry_run else ""
    filename = f"{prefix}scan-{ts}.json"
    entry = {
        "timestamp": ts,
        "dry_run": dry_run,
        "exit_code": result.exit_code,
        "success": result.success,
        "duration_seconds": result.duration_seconds,
        "summary": asdict(result.summary) if result.summary else None,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }
    path = log_dir / filename
    path.write_text(json.dumps(entry, indent=2))
    return path


def cleanup_old_logs(config: Config) -> int:
    log_dir = PROJECT_DIR / config.log_dir
    if not log_dir.exists():
        return 0
    cutoff = datetime.now(timezone.utc) - timedelta(days=config.retention_days)
    removed = 0
    for f in log_dir.glob("*.json"):
        if datetime.fromtimestamp(f.stat().st_mtime, tz=timezone.utc) < cutoff:
            f.unlink()
            removed += 1
    return removed


# ── Subcommands ───────────────────────────────────────────────────────────────


def cmd_scan(args: argparse.Namespace) -> None:
    config = load_config(args.config)
    if args.verbose:
        config.verbose = True

    label = "[DRY RUN] " if args.dry_run else ""
    print(f"{label}Starting inbox scan...")

    result = run_with_retries(config, dry_run=args.dry_run)
    log_path = save_log(config, result, args.dry_run)
    cleaned = cleanup_old_logs(config)

    if result.success and result.summary:
        s = result.summary
        print(
            f"Done in {result.duration_seconds:.0f}s — "
            f"{s.emails_found} emails found, {s.emails_read} read, "
            f"{s.tasks_created} tasks created"
        )
    elif result.success:
        print(f"Done in {result.duration_seconds:.0f}s (could not parse summary)")
    else:
        print(f"Scan failed (exit code {result.exit_code})")
        if result.stderr:
            print(f"Error: {result.stderr[:500]}")

    if config.verbose:
        print("\n--- Full output ---")
        print(result.stdout)

    print(f"Log saved: {log_path.relative_to(PROJECT_DIR)}")
    if cleaned:
        print(f"Cleaned up {cleaned} old log(s)")

    sys.exit(0 if result.success else 1)


def cmd_logs(args: argparse.Namespace) -> None:
    config = load_config(args.config)
    log_dir = PROJECT_DIR / config.log_dir
    if not log_dir.exists():
        print("No logs yet.")
        return
    files = sorted(log_dir.glob("*.json"), key=lambda f: f.name, reverse=True)
    if not files:
        print("No logs yet.")
        return
    for f in files[: args.last]:
        entry = json.loads(f.read_text())
        status = "OK" if entry["success"] else "FAIL"
        dry = " (dry run)" if entry.get("dry_run") else ""
        summary = entry.get("summary")
        detail = ""
        if summary:
            detail = f" — {summary['emails_found']} emails, {summary['tasks_created']} tasks"
        print(f"  [{status}] {entry['timestamp']}{dry}  {entry['duration_seconds']}s{detail}")


def cmd_config(args: argparse.Namespace) -> None:
    config = load_config(args.config)
    for k, v in asdict(config).items():
        print(f"  {k}: {v}")


# ── Main ──────────────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(prog="cos", description="Claude COS — inbox scan orchestrator")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG_PATH), help="Config file path")
    sub = parser.add_subparsers(dest="command")

    scan_p = sub.add_parser("scan", help="Run inbox scan")
    scan_p.add_argument("--dry-run", action="store_true", help="Preview without creating tasks")
    scan_p.add_argument("--verbose", "-v", action="store_true", help="Print full agent output")

    logs_p = sub.add_parser("logs", help="View scan history")
    logs_p.add_argument("--last", type=int, default=5, help="Show last N scans")

    sub.add_parser("config", help="Show effective configuration")

    args = parser.parse_args()
    match args.command:
        case "scan":
            cmd_scan(args)
        case "logs":
            cmd_logs(args)
        case "config":
            cmd_config(args)
        case _:
            parser.print_help()


if __name__ == "__main__":
    main()
