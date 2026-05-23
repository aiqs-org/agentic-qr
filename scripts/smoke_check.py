#!/usr/bin/env python3
"""Non-network smoke checks for tracked Python source.

This script intentionally avoids importing project modules and avoids writing
bytecode. It is safe to run on a server with secrets present because it only
parses tracked Python files.
"""

from __future__ import annotations

import ast
import os
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def git_command() -> str:
    found = shutil.which("git")
    if found:
        return found
    if os.name == "nt":
        candidate = Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Git" / "cmd" / "git.exe"
        if candidate.exists():
            return str(candidate)
    return "git"


def tracked_python_files() -> list[Path]:
    result = subprocess.run(
        [git_command(), "ls-files", "*.py"],
        cwd=ROOT,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
    )
    return [ROOT / line for line in result.stdout.splitlines() if line.strip()]


def main() -> int:
    failures: list[str] = []
    files = tracked_python_files()
    for path in files:
        rel = path.relative_to(ROOT)
        try:
            ast.parse(path.read_text(encoding="utf-8"), filename=str(rel))
        except SyntaxError as exc:
            failures.append(f"{rel}:{exc.lineno}:{exc.offset}: {exc.msg}")

    if failures:
        print("Python syntax check failed:")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print(f"Python syntax OK: {len(files)} tracked files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
