"""
telegram_valve.py
-----------------
Polls Telegram for incoming messages and feeds them into the router.
Also used to ask clarification questions back to the user.
"""

import os
import time
import requests
from loguru import logger

TOKEN = os.getenv("TELEGRAM_TOKEN", "")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
BASE_URL = f"https://api.telegram.org/bot{TOKEN}"

_offset = 0


def send(text: str):
    if not TOKEN or not CHAT_ID:
        print(f"[TELEGRAM] {text}")
        return
    try:
        requests.post(f"{BASE_URL}/sendMessage", json={
            "chat_id": CHAT_ID,
            "text": text,
        }, timeout=10)
    except Exception as e:
        logger.error(f"[TELEGRAM] send failed: {e}")


def ask_clarification(question: str) -> str:
    """Send a question and wait for reply. Falls back to terminal if no token."""
    if not TOKEN or not CHAT_ID:
        return input(f"\n[CLARIFY] {question}\n> ").strip()

    send(f"❓ {question}")
    logger.info("[TELEGRAM] waiting for clarification reply...")

    global _offset
    deadline = time.time() + 120  # wait up to 2 min
    while time.time() < deadline:
        try:
            r = requests.get(f"{BASE_URL}/getUpdates", params={"offset": _offset, "timeout": 10}, timeout=15)
            for update in r.json().get("result", []):
                _offset = update["update_id"] + 1
                msg = update.get("message", {})
                if str(msg.get("chat", {}).get("id")) == str(CHAT_ID):
                    reply = msg.get("text", "").strip()
                    if reply:
                        logger.info(f"[TELEGRAM] clarification reply: {reply}")
                        return reply
        except Exception as e:
            logger.error(f"[TELEGRAM] poll failed: {e}")
        time.sleep(2)

    logger.warning("[TELEGRAM] clarification timeout — defaulting to researcher")
    return "researcher"


def poll_messages() -> list[dict]:
    """Return new messages from Telegram."""
    if not TOKEN:
        return []
    global _offset
    messages = []
    try:
        r = requests.get(f"{BASE_URL}/getUpdates", params={"offset": _offset, "timeout": 5}, timeout=10)
        for update in r.json().get("result", []):
            _offset = update["update_id"] + 1
            msg = update.get("message", {})
            if msg.get("text") and str(msg.get("chat", {}).get("id")) == str(CHAT_ID):
                messages.append({"text": msg["text"], "source": "telegram"})
    except Exception as e:
        logger.error(f"[TELEGRAM] poll failed: {e}")
    return messages
