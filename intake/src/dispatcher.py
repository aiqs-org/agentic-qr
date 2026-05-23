"""Dispatch classified intake content to the appropriate runtime location."""

import json
from datetime import datetime, timezone
from pathlib import Path

from loguru import logger

SHARED_HYPOTHESES = Path("/shared/hypotheses")
SHARED_KNOWLEDGE = Path("/shared/knowledge")
VAULT_BUS = Path("/vault/bus")


def dispatch(route: str, content: str, classification: dict, source_name: str):
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")

    if route == "researcher":
        out_path = SHARED_HYPOTHESES / f"{ts}_intake.json"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "id": f"intake_{ts}",
            "title": classification.get("summary", "")[:80],
            "description": content,
            "source": f"intake:{source_name}",
            "classification": classification,
        }
        out_path.write_text(json.dumps(payload, indent=2))
        logger.success(f"[DISPATCH] -> researcher: {out_path.name}")
        return str(out_path)

    if route == "swe":
        inbox = VAULT_BUS / "strategy-core-inbox"
        inbox.mkdir(parents=True, exist_ok=True)
        out_path = inbox / f"{ts}_new_code.json"
        payload = {
            "event": "new_hypothesis",
            "hypothesis": {
                "id": f"intake_{ts}",
                "title": classification.get("summary", "")[:80],
                "description": content,
                "source": f"intake:{source_name}",
                "type": "code_project",
            },
        }
        out_path.write_text(json.dumps(payload, indent=2))
        logger.success(f"[DISPATCH] -> swe: {out_path.name}")
        return str(out_path)

    if route == "librarian":
        out_path = SHARED_KNOWLEDGE / f"{ts}_{source_name}.md"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        md = f"# {source_name}\n\n"
        md += f"**Ingested:** {datetime.now(timezone.utc).isoformat()}\n"
        md += f"**Summary:** {classification.get('summary', '')}\n\n"
        md += "---\n\n"
        md += content
        out_path.write_text(md)
        logger.success(f"[DISPATCH] -> librarian: {out_path.name}")
        return str(out_path)

    logger.warning(f"[DISPATCH] unknown route: {route}")
    return None
