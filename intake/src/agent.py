"""
agent.py — intake router main loop

Two valves:
  1. Drop folder (/intake/drop/) — watches for new files
  2. Telegram — polls for new messages

Both feed into classifier → dispatcher.
Clarification requests go back via Telegram or terminal.
"""

import os
import time
import shutil
from pathlib import Path
from datetime import datetime, timezone

from loguru import logger
from dotenv import load_dotenv

from reader import extract_text
from classifier import classify
from dispatcher import dispatch
from telegram_valve import poll_messages, ask_clarification, send

load_dotenv()

INTAKE_DROP = Path(os.getenv("INTAKE_DROP", "/intake/drop"))
INTAKE_PROCESSED = Path(os.getenv("INTAKE_PROCESSED", "/intake/processed"))
VAULT_LOGS = Path(os.getenv("VAULT_LOGS", "/vault/logs"))

INTAKE_DROP.mkdir(parents=True, exist_ok=True)
INTAKE_PROCESSED.mkdir(parents=True, exist_ok=True)
VAULT_LOGS.mkdir(parents=True, exist_ok=True)


def process_content(text: str, source_name: str):
    """Classify and dispatch a piece of content."""
    if not text.strip():
        logger.warning(f"[AGENT] empty content from {source_name}, skipping")
        return

    logger.info(f"[AGENT] classifying: {source_name}")
    classification = classify(text, source_name)
    route = classification.get("route", "clarify")
    summary = classification.get("summary", "")
    confidence = classification.get("confidence", 0)

    # If ambiguous or low confidence, ask for clarification
    if route == "clarify" or confidence < 0.6:
        question = classification.get("clarify_question") or \
            f"Where should '{source_name}' be routed?\nSummary: {summary}\nOptions: researcher / swe / librarian"
        reply = ask_clarification(question)
        # Parse reply
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

    # Notify via Telegram
    send(f"✅ Routed '{source_name}' → {route.upper()}\n{summary}")
    logger.success(f"[AGENT] {source_name} → {route} → {out_path}")


def process_drop_folder():
    """Check drop folder for new files."""
    for file_path in sorted(INTAKE_DROP.iterdir()):
        if file_path.is_file() and not file_path.name.startswith("."):
            logger.info(f"[DROP] found: {file_path.name}")
            text = extract_text(file_path)
            process_content(text, file_path.stem)
            # Move to processed
            dest = INTAKE_PROCESSED / f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}_{file_path.name}"
            shutil.move(str(file_path), str(dest))


def process_telegram():
    """Check Telegram for new messages."""
    for msg in poll_messages():
        text = msg["text"]
        # Skip commands for now
        if text.startswith("/"):
            continue
        process_content(text, f"telegram_{datetime.now(timezone.utc).strftime('%H%M%S')}")


def main():
    logger.info("=== intake router starting ===")
    logger.info(f"[DROP] watching {INTAKE_DROP}")
    send("🟢 Intake router online. Drop files or send messages to route them.")

    while True:
        try:
            process_drop_folder()
            process_telegram()
        except Exception as e:
            logger.error(f"[AGENT] loop error: {e}")
        time.sleep(2)


if __name__ == "__main__":
    main()
