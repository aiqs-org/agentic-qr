"""Intake router main loop.

Inputs:
- Drop folder at /intake/drop/
- Telegram messages

Both inputs flow through classifier -> dispatcher -> intake trace receipt.
Clarification requests go back via Telegram or terminal.
"""

import json
import os
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from loguru import logger

from classifier import classify
from dispatcher import dispatch
from reader import extract_text
from telegram_valve import ask_clarification, poll_messages, send

load_dotenv()

INTAKE_DROP = Path(os.getenv("INTAKE_DROP", "/intake/drop"))
INTAKE_PROCESSED = Path(os.getenv("INTAKE_PROCESSED", "/intake/processed"))
VAULT_LOGS = Path(os.getenv("VAULT_LOGS", "/vault/logs"))
VAULT_INTAKE_TRACE = Path(os.getenv("VAULT_INTAKE_TRACE", "/vault/intake-trace"))
ENABLE_TELEGRAM = os.getenv("ENABLE_TELEGRAM", "true").lower() in {"1", "true", "yes", "on"}

INTAKE_DROP.mkdir(parents=True, exist_ok=True)
INTAKE_PROCESSED.mkdir(parents=True, exist_ok=True)
VAULT_LOGS.mkdir(parents=True, exist_ok=True)
VAULT_INTAKE_TRACE.mkdir(parents=True, exist_ok=True)


def source_kind(source_name: str) -> str:
    if source_name.startswith("telegram_"):
        return "telegram"
    return "drop"


def write_trace(
    *,
    source_name: str,
    text: str,
    classification: dict,
    route: str,
    out_path: str | None,
) -> Path:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
    trace_id = f"{source_name}_{ts}"
    trace_path = VAULT_INTAKE_TRACE / f"{trace_id}.json"
    payload = {
        "trace_id": trace_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "source": source_kind(source_name),
        "source_name": source_name,
        "route": route,
        "confidence": classification.get("confidence"),
        "reason": classification.get("reason"),
        "summary": classification.get("summary", ""),
        "classification": classification,
        "dispatch_target": out_path,
        "status": "dispatched" if out_path else "not_dispatched",
        "text_preview": text[:1000],
    }
    trace_path.write_text(json.dumps(payload, indent=2))
    logger.info(f"[TRACE] wrote {trace_path}")
    return trace_path


def process_content(text: str, source_name: str):
    """Classify, dispatch, trace, and acknowledge a piece of content."""
    if not text.strip():
        logger.warning(f"[AGENT] empty content from {source_name}, skipping")
        return

    logger.info(f"[AGENT] classifying: {source_name}")
    classification = classify(text, source_name)
    route = classification.get("route", "clarify")
    summary = classification.get("summary", "")
    confidence = classification.get("confidence", 0)

    if route == "clarify" or confidence < 0.6:
        question = classification.get("clarify_question") or (
            f"Where should '{source_name}' be routed?\n"
            f"Summary: {summary}\n"
            "Options: researcher / swe / librarian"
        )
        reply = ask_clarification(question)
        reply_lower = reply.lower()
        if "swe" in reply_lower or "engineer" in reply_lower or "code" in reply_lower:
            route = "swe"
        elif "lib" in reply_lower or "archive" in reply_lower or "reference" in reply_lower:
            route = "librarian"
        else:
            route = "researcher"
        classification["route"] = route
        classification["clarified_by_human"] = True

    out_path = dispatch(route, text, classification, source_name)
    trace_path = write_trace(
        source_name=source_name,
        text=text,
        classification=classification,
        route=route,
        out_path=out_path,
    )

    target = Path(out_path).name if out_path else "none"
    send(
        "Routed intake message\n"
        f"source: {source_name}\n"
        f"route: {route}\n"
        f"confidence: {confidence}\n"
        f"target: {target}\n"
        f"trace: {trace_path.name}\n"
        f"summary: {summary[:500]}"
    )
    logger.success(f"[AGENT] {source_name} -> {route} -> {out_path} trace={trace_path.name}")


def process_drop_folder():
    """Check drop folder for new files."""
    for file_path in sorted(INTAKE_DROP.iterdir()):
        if file_path.is_file() and not file_path.name.startswith("."):
            logger.info(f"[DROP] found: {file_path.name}")
            text = extract_text(file_path)
            process_content(text, file_path.stem)
            dest = INTAKE_PROCESSED / f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}_{file_path.name}"
            shutil.move(str(file_path), str(dest))


def process_telegram():
    """Check Telegram for new messages."""
    for msg in poll_messages():
        text = msg["text"]
        if text.startswith("/"):
            continue
        process_content(text, f"telegram_{datetime.now(timezone.utc).strftime('%H%M%S')}")


def main():
    logger.info("=== intake router starting ===")
    logger.info(f"[DROP] watching {INTAKE_DROP}")
    logger.info(f"[TELEGRAM] enabled={ENABLE_TELEGRAM}")
    if ENABLE_TELEGRAM:
        send("Intake router online. Drop files or send messages to route them.")

    while True:
        try:
            process_drop_folder()
            if ENABLE_TELEGRAM:
                process_telegram()
        except Exception as e:
            logger.error(f"[AGENT] loop error: {e}")
        time.sleep(2)


if __name__ == "__main__":
    main()
