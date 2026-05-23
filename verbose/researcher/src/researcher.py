import os, json, httpx
from datetime import datetime
from pathlib import Path

import os
MODEL = os.getenv("QWEN_MODEL", "Qwen/Qwen3.6-35B-A3B-FP8")
QWEN_URL = os.getenv("QWEN_BASE_URL", "")
QWEN_KEY = os.getenv("QWEN_API_KEY", "")
SHARED_KNOWLEDGE = Path(os.getenv("SHARED_KNOWLEDGE_PATH", "/shared/knowledge"))
VAULT_BUS = Path(os.getenv("VAULT_BUS_PATH", "/vault/bus"))
URL = "https://openrouter.ai/api/v1/chat/completions"
PROMPT = """You are the Researcher agent. Output financial research in markdown only. No code.
Format:
---
title:
date:
hypothesis_id:
confidence: low|medium|high
tags: []
---
## Summary
## Analysis
## Hypothesis
## Evidence
## Open Questions
## Next Steps"""

def call_model(messages):
    headers = {"Authorization": f"Bearer {QWEN_KEY or os.getenv('OPENROUTER_API_KEY')}", "Content-Type": "application/json"}
    use_url = QWEN_URL if QWEN_URL else URL
    r = httpx.post(use_url, headers=headers, json={"model": MODEL, "max_tokens": 4096, "messages": messages}, timeout=120)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]

def run(task, hypothesis_id=None):
    if not hypothesis_id:
        hypothesis_id = f"HYP-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
    print(f"[Researcher] {task} | {hypothesis_id}")
    ctx = ""
    bf = VAULT_BUS / "librarian_to_researcher.json"
    if bf.exists():
        ctx = json.load(open(bf)).get("context", "")
    msg = f"Librarian context:\n{ctx}\n\nTask: {task}" if ctx else f"Task: {task}"
    result = call_model([{"role": "system", "content": PROMPT}, {"role": "user", "content": msg}])
    SHARED_KNOWLEDGE.mkdir(parents=True, exist_ok=True)
    out = SHARED_KNOWLEDGE / f"{datetime.utcnow().strftime('%Y-%m-%d')}_{hypothesis_id}.md"
    out.write_text(result)
    print(f"[Researcher] Saved → {out}")
    VAULT_BUS.mkdir(parents=True, exist_ok=True)
    json.dump({
        "from": "researcher", "to": ["caveman", "manager"],
        "type": "new_finding", "hypothesis_id": hypothesis_id,
        "path": str(out), "timestamp": datetime.utcnow().isoformat()
    }, open(VAULT_BUS / f"researcher_out_{hypothesis_id}.json", "w"), indent=2)
    print("[Researcher] Done")
    return result
