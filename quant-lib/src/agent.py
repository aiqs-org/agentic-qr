import os
import json
from pathlib import Path
from datetime import datetime, timezone

from loguru import logger
from dotenv import load_dotenv

from object_factory import run_object_factory
from bus import init_bus, publish, watch_inbox
from reasoning_packets import write_quant_lib_packet

load_dotenv()

SHARED_MODELS = Path(os.getenv("SHARED_MODELS", "/shared/models"))
VAULT_LOGS = Path(os.getenv("VAULT_LOGS", "/vault/logs"))
VAULT_LOGS.mkdir(parents=True, exist_ok=True)

SYSTEM_PROMPT = """You are the quant-lib Research Ops agent in the caveman trading system.
Your role is the OBJECT FACTORY layer only.
 - Build NautilusTrader instrument and bar objects from pipeline data.
 - Maintain typed mechanical catalogs of available objects.
 - Do NOT write research opinions into instruments.json or macro_catalog.json.
 - Do NOT build features, signals, or strategy logic.
Output: structured JSON for machines. Never raw code."""


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
    macro_path = SHARED_MODELS / "macro_catalog.json"
    catalog = json.loads(catalog_path.read_text()) if catalog_path.exists() else {}
    macro = json.loads(macro_path.read_text()) if macro_path.exists() else {}
    packet_path = write_quant_lib_packet(result, catalog, macro)
    result["reasoning_packet"] = str(packet_path)
    result["catalog_enriched"] = False

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
