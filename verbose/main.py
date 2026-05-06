import os, json, sys, time
from pathlib import Path

VAULT_BUS = Path(os.getenv("VAULT_BUS_PATH", "/vault/bus"))
POLL_INTERVAL = 10

def load_task():
    task_file = VAULT_BUS / "verbose_task.json"
    if task_file.exists():
        with open(task_file) as f:
            pkg = json.load(f)
        task_file.unlink()
        return pkg.get("task", ""), pkg.get("hypothesis_id", None)
    return None, None

def run_pipeline(task, hypothesis_id):
    print(f"\n=== VERBOSE PIPELINE: {task[:80]} ===")
    from librarian.src.librarian import run as librarian_run
    librarian_run(task)
    from researcher.src.researcher import run as researcher_run
    result = researcher_run(task, hypothesis_id)
    # Trigger strategy-core if researcher produced a hypothesis
    inbox = VAULT_BUS / "strategy-core-inbox"
    inbox.mkdir(parents=True, exist_ok=True)
    from datetime import datetime, timezone
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    trigger = inbox / f"{ts}_run_pending.json"
    trigger.write_text(json.dumps({"event": "run_pending_hypotheses"}))
    print("[Verbose] Pipeline complete. Triggered strategy-core.")

def main():
    print("=== verbose daemon starting ===")
    # Run default task on startup
    run_pipeline("Analyze current macro conditions and their impact on equity volatility", None)
    print(f"[Verbose] watching {VAULT_BUS}/verbose_task.json every {POLL_INTERVAL}s...")
    while True:
        try:
            task, hypothesis_id = load_task()
            if task:
                run_pipeline(task, hypothesis_id)
        except Exception as e:
            print(f"[Verbose] error: {e}")
        time.sleep(POLL_INTERVAL)

if __name__ == "__main__":
    main()
