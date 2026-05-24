"""
agent.py — strategy-core main loop
Model: MiniMax via OpenRouter
Role: SWE agent — hypothesis → strategy code → backtest → result
"""

import os
import json
from pathlib import Path
from datetime import datetime, timezone

from loguru import logger
from dotenv import load_dotenv

from swe import SHARED_HYPOTHESES, load_context, load_pending_hypotheses, process_hypothesis
from bus import init_bus, publish, watch_inbox

load_dotenv()

VAULT_LOGS = Path(os.getenv("VAULT_LOGS", "/vault/logs"))
VAULT_LOGS.mkdir(parents=True, exist_ok=True)


def handle_inbox_message(msg: dict):
    event = msg.get("event", "")
    task = msg.get("task", "")
    logger.info(f"[BUS] received: {event or task or 'unknown'}")

    if event == "new_hypothesis":
        hypothesis = msg.get("hypothesis", {})
        if not hypothesis:
            return
        context = load_context()
        result = process_hypothesis(
            {"path": Path(f"/tmp/bus_hyp_{datetime.now().strftime('%f')}.json"), "data": hypothesis},
            context
        )
        publish({
            "event": "backtest_complete",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "result": result,
        })

    elif task == "implement_and_backtest":
        hypothesis_id = msg.get("hypothesis_id")
        if not hypothesis_id:
            logger.warning("[BUS] implement_and_backtest missing hypothesis_id")
            return

        hyp_path = SHARED_HYPOTHESES / f"{hypothesis_id}.json"
        if not hyp_path.exists():
            logger.warning(f"[BUS] hypothesis not found: {hypothesis_id}")
            return

        context = load_context()
        result = process_hypothesis(
            {"path": hyp_path, "data": json.loads(hyp_path.read_text())},
            context,
        )
        publish({
            "event": "backtest_complete",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "hypothesis_id": hypothesis_id,
            "result": result,
        })

    elif event == "run_pending_hypotheses":
        run_pending()

    elif event == "query_results":
        results_dir = Path(os.getenv("SHARED_BACKTESTING", "/shared/backtesting")) / "results"
        results = []
        if results_dir.exists():
            for f in sorted(results_dir.glob("*.json"))[-5:]:
                results.append(json.loads(f.read_text()))
        publish({
            "event": "results_response",
            "query_id": msg.get("query_id"),
            "results": results,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })


def run_pending():
    """Process any hypotheses waiting in shared/hypotheses/."""
    context = load_context()
    hypotheses = load_pending_hypotheses()
    if not hypotheses:
        logger.info("[AGENT] no pending hypotheses")
        return
    for entry in hypotheses:
        try:
            result = process_hypothesis(entry, context)
            publish({
                "event": "backtest_complete",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "result": result,
            })
        except Exception as e:
            logger.error(f"[AGENT] failed to process hypothesis: {e}")


def main():
    logger.info("=== strategy-core agent starting ===")
    init_bus()

    # Check for any pending hypotheses on startup
    run_pending()

    logger.info("[AGENT] entering bus watch loop...")
    watch_inbox(handle_inbox_message)


if __name__ == "__main__":
    main()
