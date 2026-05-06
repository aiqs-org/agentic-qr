import os, json
from datetime import datetime, timezone
from pathlib import Path

VAULT_BUS = Path(os.getenv("VAULT_BUS_PATH", "/vault/bus"))
SHARED_DATA = Path(os.getenv("SHARED_DATA_PATH", "/shared/data"))

DEFAULT_TASK = {
    "connectors": ["alpaca", "fred"],
    "symbols": ["SPY", "QQQ", "TLT", "GLD"],
    "interval": "1d",
    "period": "3mo"
}

def load_task() -> dict:
    task_file = VAULT_BUS / "pipeline_task.json"
    if task_file.exists():
        with open(task_file) as f:
            pkg = json.load(f)
        task_file.unlink()
        print(f"[Pipeline] Task from bus: {pkg}")
        return pkg
    print(f"[Pipeline] No task found — using defaults")
    return DEFAULT_TASK

def publish_complete(task: dict, written_files: list):
    VAULT_BUS.mkdir(parents=True, exist_ok=True)
    msg = {
        "from": "pipelines",
        "to": ["quant-lib"],
        "type": "data_ready",
        "task": task,
        "files": written_files,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    out = VAULT_BUS / f"pipeline_complete_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}.json"
    with open(out, "w") as f:
        json.dump(msg, f, indent=2)
    print(f"[Pipeline] Published completion → {out}")

def main():
    task = load_task()
    connectors = task.get("connectors", ["alpaca", "fred"])
    written = []

    if "alpaca" in connectors:
        from connectors.alpaca_connector import fetch as alpaca_fetch
        records = alpaca_fetch(
            symbols=task.get("symbols", ["SPY", "QQQ", "TLT", "GLD"]),
            interval=task.get("interval", "1d"),
            period=task.get("period", "3mo")
        )
        written.append(f"shared/data/market/ ({len(records)} records)")

    if "fred" in connectors:
        from connectors.fred_connector import fetch as fred_fetch
        records = fred_fetch()
        written.append(f"shared/data/macro/ ({len(records)} records)")

    publish_complete(task, written)
    print(f"\n[Pipeline] Complete. Written: {written}")

if __name__ == "__main__":
    main()
