#!/usr/bin/env python3
"""Server runtime health check for Agentic QR.

This script is intended to run on the server from the repository root. It does
not read or print secret files. It summarizes container state, recent runtime
log warnings, tracked Python syntax, and zeroclaw update status.
"""

from __future__ import annotations

import argparse
import ast
import json
import shutil
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path


DEFAULT_ROOT = Path(__file__).resolve().parents[1]
ROOT = DEFAULT_ROOT
CONTAINERS = (
    "caveman-intake",
    "caveman-strategy-core",
    "caveman-quant-lib",
    "infisical-backend",
    "infisical-db",
    "infisical-dev-redis",
)
LOG_PATTERNS = (
    "backtest failed",
    "unsupported operand",
    "UPSTREAM_ERROR",
    "Upstream provider returned 404",
    "orders rejected",
    "no market",
    "classifier error",
    "poll failed",
)


@dataclass
class Finding:
    level: str
    area: str
    message: str


def run(cmd: list[str], check: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=ROOT,
        check=check,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def sudo_prefix() -> list[str]:
    if shutil.which("sudo"):
        return ["sudo", "-n"]
    return []


def docker_cmd(args: list[str]) -> list[str]:
    return [*sudo_prefix(), "docker", *args]


def git_cmd() -> str:
    found = shutil.which("git")
    return found or "git"


def tracked_python_files() -> list[Path]:
    result = run([git_cmd(), "ls-files", "*.py"], check=True)
    return [ROOT / line for line in result.stdout.splitlines() if line.strip()]


def syntax_findings() -> list[Finding]:
    findings: list[Finding] = []
    try:
        files = tracked_python_files()
    except Exception as exc:
        return [Finding("error", "source", f"Could not list tracked Python files: {exc}")]

    for path in files:
        try:
            ast.parse(path.read_text(encoding="utf-8"), filename=str(path.relative_to(ROOT)))
        except SyntaxError as exc:
            rel = path.relative_to(ROOT)
            findings.append(Finding("error", "source", f"{rel}:{exc.lineno}:{exc.offset}: {exc.msg}"))

    if not findings:
        findings.append(Finding("ok", "source", f"Python syntax OK: {len(files)} tracked files"))
    return findings


def container_findings() -> list[Finding]:
    findings: list[Finding] = []
    for name in CONTAINERS:
        result = run(docker_cmd(["inspect", name]))
        if result.returncode != 0:
            findings.append(Finding("warn", "docker", f"{name}: not found"))
            continue

        data = json.loads(result.stdout)[0]
        state = data.get("State", {})
        config = data.get("Config", {})
        image = config.get("Image", data.get("Image", "unknown"))
        status = state.get("Status", "unknown")
        exit_code = state.get("ExitCode")
        oom = state.get("OOMKilled")
        finished = state.get("FinishedAt")

        if status == "running":
            findings.append(Finding("ok", "docker", f"{name}: running ({image})"))
        else:
            details = f"{name}: {status} ({image}), exit={exit_code}, oom_killed={oom}"
            if finished:
                details += f", finished={finished}"
            findings.append(Finding("error", "docker", details))
    return findings


def log_findings(tail: int) -> list[Finding]:
    findings: list[Finding] = []
    for name in ("caveman-intake", "caveman-strategy-core", "caveman-quant-lib"):
        result = run(docker_cmd(["logs", "--tail", str(tail), name]))
        if result.returncode != 0:
            findings.append(Finding("warn", "logs", f"{name}: logs unavailable"))
            continue

        combined = f"{result.stdout}\n{result.stderr}"
        matched = [pattern for pattern in LOG_PATTERNS if pattern.lower() in combined.lower()]
        if matched:
            findings.append(Finding("warn", "logs", f"{name}: matched {', '.join(matched)}"))
        else:
            findings.append(Finding("ok", "logs", f"{name}: no known error patterns in last {tail} lines"))
    return findings


def zeroclaw_findings() -> list[Finding]:
    binary = shutil.which("zeroclaw") or "/home/gram/.cargo/bin/zeroclaw"
    if not Path(binary).exists() and shutil.which("zeroclaw") is None:
        return [Finding("warn", "zeroclaw", "zeroclaw binary not found")]

    version = run([binary, "--version"])
    if version.returncode != 0:
        return [Finding("warn", "zeroclaw", "could not read zeroclaw version")]

    update = run([binary, "update", "--check"])
    message = version.stdout.strip()
    if update.returncode == 0:
        update_text = (update.stdout + update.stderr).strip().splitlines()
        update_summary = update_text[-1] if update_text else "update check returned no text"
        return [Finding("ok", "zeroclaw", f"{message}; {update_summary}")]
    return [Finding("warn", "zeroclaw", f"{message}; update check failed")]


def model_config_findings() -> list[Finding]:
    files = [
        ROOT / "strategy-core" / ".env",
        ROOT / "verbose" / ".env",
        ROOT / "quant-lib" / ".env",
        ROOT / "intake" / ".env",
    ]
    findings: list[Finding] = []
    for path in files:
        if path.exists():
            findings.append(Finding("ok", "config", f"{path.relative_to(ROOT)} exists"))
        else:
            findings.append(Finding("warn", "config", f"{path.relative_to(ROOT)} missing"))
    return findings


def print_text(findings: list[Finding]) -> int:
    width = max(len(f.area) for f in findings) if findings else 0
    exit_code = 0
    for finding in findings:
        if finding.level == "error":
            exit_code = 1
        label = finding.level.upper()
        print(f"[{label:5}] {finding.area:<{width}}  {finding.message}")
    return exit_code


def main() -> int:
    global ROOT
    parser = argparse.ArgumentParser(description="Check Agentic QR server runtime health.")
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT, help="Repository root to inspect.")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    parser.add_argument("--log-tail", type=int, default=80, help="Recent log lines to scan per runtime container.")
    args = parser.parse_args()
    ROOT = args.root.resolve()

    findings = [
        *syntax_findings(),
        *container_findings(),
        *log_findings(args.log_tail),
        *model_config_findings(),
        *zeroclaw_findings(),
    ]

    if args.json:
        print(json.dumps([asdict(f) for f in findings], indent=2))
        return 1 if any(f.level == "error" for f in findings) else 0
    return print_text(findings)


if __name__ == "__main__":
    raise SystemExit(main())
