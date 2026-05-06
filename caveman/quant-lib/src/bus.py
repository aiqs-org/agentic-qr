"""
bus.py — vault/bus interface for quant-lib.
Reads trigger messages from vault/bus/quant-lib-inbox/
Writes output events to vault/bus/quant-lib-outbox/
"""

import json
import time
from pathlib import Path
from datetime import datetime, timezone
from loguru import logger

VAULT_BUS = Path("/vault/bus")
INBOX = VAULT_BUS / "quant-lib-inbox"
OUTBOX = VAULT_BUS / "quant-lib-outbox"


def init_bus():
    INBOX.mkdir(parents=True, exist_ok=True)
    OUTBOX.mkdir(parents=True, exist_ok=True)


def publish(event: dict):
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
    out_path = OUTBOX / f"{ts}_{event.get('event', 'event')}.json"
    out_path.write_text(json.dumps(event, indent=2))
    logger.info(f"[BUS] published → {out_path.name}")


def poll_inbox() -> list[dict]:
    messages = []
    for msg_file in sorted(INBOX.glob("*.json")):
        try:
            msg = json.loads(msg_file.read_text())
            messages.append(msg)
            msg_file.rename(msg_file.with_suffix(".json.done"))
        except Exception as e:
            logger.error(f"[BUS] failed to read {msg_file.name}: {e}")
    return messages


def watch_inbox(callback, poll_interval: float = 2.0):
    logger.info(f"[BUS] watching inbox at {INBOX}")
    while True:
        for msg in poll_inbox():
            callback(msg)
        time.sleep(poll_interval)
