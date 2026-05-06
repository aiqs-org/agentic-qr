"""
agent.py — quant-lib main loop
Model: Kimi K2.6 via OpenRouter
Role: Object factory + catalog enrichment + bus responder
"""

import os
import json
from pathlib import Path
from datetime import datetime, timezone

from openai import OpenAI
from loguru import logger
from dotenv import load_dotenv

from object_factory import run_object_factory
from bus import init_bus, publish, watch_inbox

load_dotenv()

client = OpenAI(
    api_key=os.getenv("OPENROUTER_API_KEY"),
    base_url=os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
)
MODEL = os.getenv("KIMI_MODEL", "moonshotai/kimi-k2")

SHARED_MODELS = Path(os.getenv("SHARED_MODELS", "/shared/models"))
SHARED_KNOWLEDGE = Path(os.getenv("SHARED_KNOWLEDGE", "/shared/knowledge"))
VAULT_LOGS = Path(os.getenv("VAULT_LOGS", "/vault/logs"))
VAULT_LOGS.mkdir(parents=True, exist_ok=True)

SYSTEM_PROMPT = """You are the quant-lib Research Ops agent in the caveman trading system.
Your role is the OBJECT FACTORY layer only.
- You build NautilusTrader instrument and bar objects from pipeline data
- You maintain a typed catalog of available objects
- You annotate catalogs with researcher findings
- You do NOT build features, signals, or strategy logic
Output: structured JSON for machines, brief markdown for humans. Never raw code."""


def load_researcher_knowledge() -> str:
    if not SHARED_KNOWLEDGE.exists():
        return "No researcher knowledge available yet."
    files = sorted(SHARED_KNOWLEDGE.glob("*.md"))[-5:]
    return "\n\n".join(f"### {f.name}\n{f.read_text()[:2000]}" for f in files) or "No researcher knowledge available yet."


def annotate_catalog(catalog: dict) -> dict:
    knowledge = load_researcher_knowledge()
    if "No researcher knowledge" in knowledge:
        return catalog
    try:
        response = client.chat.completions.create(
            model=MODEL,
            max_tokens=1500,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"Enrich this catalog with research_context per instrument.\nCatalog:\n{json.dumps(catalog, indent=2)}\n\nResearch:\n{knowledge}\n\nReturn ONLY valid JSON."},
            ],
        )
        content = response.choices[0].message.content.strip().replace("```json", "").replace("```", "").strip()
        return json.loads(content)
    except Exception as e:
        logger.warning(f"[AGENT] catalog enrichment failed: {e}")
        return catalog


def handle_inbox_message(msg: dict):
    event = msg.get("event", "")
    logger.info(f"[BUS] received: {event}")
    if event in ("pipeline_data_updated", "rebuild_objects"):
        run_and_publish()
    elif event == "query_object_catalog":
        catalog_path = SHARED_MODELS / "instruments.json"
        macro_path = SHARED_MODELS / "macro_catalog.json"
        publish({
            "event": "object_catalog_response",
            "query_id": msg.get("query_id"),
            "instruments": json.loads(catalog_path.read_text()) if catalog_path.exists() else {},
            "macro": json.loads(macro_path.read_text()) if macro_path.exists() else {},
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })


def run_and_publish():
    logger.info("[AGENT] running object factory...")
    result = run_object_factory()

    catalog_path = SHARED_MODELS / "instruments.json"
    if catalog_path.exists():
        enriched = annotate_catalog(json.loads(catalog_path.read_text()))
        catalog_path.write_text(json.dumps(enriched, indent=2))
        result["catalog_enriched"] = True

    publish(result)
    log_path = VAULT_LOGS / f"quant-lib_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}.json"
    log_path.write_text(json.dumps(result, indent=2))
    logger.success(f"[AGENT] done. instruments: {result['instruments_built']}")


def main():
    logger.info("=== quant-lib agent starting ===")
    init_bus()
    run_and_publish()
    logger.info("[AGENT] entering bus watch loop...")
    watch_inbox(handle_inbox_message)


if __name__ == "__main__":
    main()
