#!/usr/bin/env python3
"""Report current backtest state from shared files and the strategy bus."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DEFAULT_ROOT = Path(__file__).resolve().parents[1]


@dataclass
class FileRecord:
    path: Path
    payload: dict[str, Any]


def read_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"_read_error": str(exc)}


def newest_json(paths: list[Path]) -> FileRecord | None:
    if not paths:
        return None
    path = max(paths, key=lambda p: p.stat().st_mtime)
    return FileRecord(path=path, payload=read_json(path))


def pending_hypotheses(root: Path) -> list[FileRecord]:
    hyp_dir = root / "shared" / "hypotheses"
    if not hyp_dir.exists():
        return []
    records = []
    for path in sorted(hyp_dir.glob("*.json")):
        if ".done" in path.name:
            continue
        records.append(FileRecord(path=path, payload=read_json(path)))
    return records


def latest_result(root: Path) -> FileRecord | None:
    result_dir = root / "shared" / "backtesting" / "results"
    if not result_dir.exists():
        return None
    return newest_json(sorted(result_dir.glob("*.json")))


def latest_outbox(root: Path) -> FileRecord | None:
    outbox = root / "vault" / "bus" / "strategy-core-outbox"
    if not outbox.exists():
        return None
    return newest_json(sorted(outbox.glob("*_backtest_complete.json")))


def stats_summary(result: dict[str, Any]) -> dict[str, Any]:
    stats = result.get("stats") or {}
    usd = stats.get("USD") or {}
    return {
        "pnl_total": usd.get("PnL (total)"),
        "pnl_percent": usd.get("PnL% (total)"),
        "win_rate": usd.get("Win Rate"),
        "expectancy": usd.get("Expectancy"),
        "profit_factor": usd.get("Profit Factor"),
    }


def build_status(root: Path) -> dict[str, Any]:
    pending = pending_hypotheses(root)
    latest = latest_result(root)
    outbox = latest_outbox(root)

    latest_payload = latest.payload if latest else None
    outbox_payload = outbox.payload if outbox else None
    outbox_result = outbox_payload.get("result") if isinstance(outbox_payload, dict) else None

    return {
        "pending_hypotheses": [
            {
                "file": record.path.name,
                "id": record.payload.get("id"),
                "title": record.payload.get("title"),
            }
            for record in pending
        ],
        "latest_result": {
            "file": latest.path.name,
            "status": latest_payload.get("status"),
            "hypothesis_id": latest_payload.get("hypothesis_id"),
            "strategy_path": latest_payload.get("strategy_path") or latest_payload.get("strategy"),
            "summary": stats_summary(latest_payload),
            "error": latest_payload.get("backtest_error") or latest_payload.get("generation_error"),
        }
        if latest and isinstance(latest_payload, dict)
        else None,
        "latest_backtest_event": {
            "file": outbox.path.name,
            "event": outbox_payload.get("event"),
            "hypothesis_id": outbox_payload.get("hypothesis_id")
            or (outbox_result or {}).get("hypothesis_id"),
            "status": (outbox_result or {}).get("status"),
            "summary": stats_summary(outbox_result or {}),
            "error": (outbox_result or {}).get("backtest_error")
            or (outbox_result or {}).get("generation_error"),
        }
        if outbox and isinstance(outbox_payload, dict)
        else None,
    }


def format_value(value: Any, percent: bool = False) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, float):
        text = f"{value:.4g}"
    else:
        text = str(value)
    return f"{text}%" if percent else text


def render_text(status: dict[str, Any]) -> str:
    lines = []
    pending = status["pending_hypotheses"]
    latest = status["latest_result"]
    event = status["latest_backtest_event"]

    if pending:
        lines.append("Pending hypotheses:")
        for item in pending:
            lines.append(f"- {item.get('id') or item['file']}: {item.get('title') or 'untitled'}")
    else:
        lines.append("Pending hypotheses: none")

    if latest:
        summary = latest["summary"]
        lines.append("")
        lines.append(f"Latest result: {latest['file']}")
        lines.append(f"- status: {latest.get('status')}")
        if latest.get("hypothesis_id"):
            lines.append(f"- hypothesis: {latest['hypothesis_id']}")
        if latest.get("error"):
            lines.append(f"- error: {latest['error']}")
        lines.append(f"- PnL: {format_value(summary.get('pnl_total'))}")
        lines.append(f"- PnL%: {format_value(summary.get('pnl_percent'), percent=True)}")
        lines.append(f"- win rate: {format_value(summary.get('win_rate'))}")
        lines.append(f"- expectancy: {format_value(summary.get('expectancy'))}")
    else:
        lines.append("")
        lines.append("Latest result: none")

    if event:
        lines.append("")
        lines.append(f"Latest bus event: {event['file']}")
        lines.append(f"- event: {event.get('event')}")
        if event.get("hypothesis_id"):
            lines.append(f"- hypothesis: {event['hypothesis_id']}")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Report latest strategy backtest status.")
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT, help="Repository root.")
    parser.add_argument("--json", action="store_true", help="Emit JSON.")
    args = parser.parse_args()

    status = build_status(args.root.resolve())
    if args.json:
        print(json.dumps(status, indent=2, default=str))
    else:
        print(render_text(status))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
