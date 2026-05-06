import os, json, hashlib, httpx
from datetime import datetime
from pathlib import Path

MODEL = "moonshotai/kimi-k2.6"
SHARED_KNOWLEDGE = Path(os.getenv("SHARED_KNOWLEDGE_PATH", "/shared/knowledge"))
VAULT_BUS = Path(os.getenv("VAULT_BUS_PATH", "/vault/bus"))
INDEX_PATH = Path(os.getenv("LIBRARIAN_INDEX_PATH", "/app/librarian/index"))
URL = "https://openrouter.ai/api/v1/chat/completions"
PROMPT = 'Return JSON only: {"selected_docs":[],"context":"","gaps":[]}. Pick docs relevant to the task.'

def call_model(messages):
    headers = {"Authorization": f"Bearer {os.getenv('OPENROUTER_API_KEY')}", "Content-Type": "application/json"}
    r = httpx.post(URL, headers=headers, json={"model": MODEL, "max_tokens": 2048, "messages": messages}, timeout=60)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]

def build_index():
    INDEX_PATH.mkdir(parents=True, exist_ok=True)
    index = {}
    if not SHARED_KNOWLEDGE.exists():
        return index
    for f in sorted(SHARED_KNOWLEDGE.glob("*.md")):
        c = f.read_text()
        index[f.name] = {"title": f.stem, "hash": hashlib.md5(c.encode()).hexdigest()[:8], "preview": c[:300]}
    json.dump(index, open(INDEX_PATH / "knowledge_index.json", "w"), indent=2)
    print(f"[Librarian] Indexed {len(index)} docs")
    return index

def run(task):
    index = build_index()
    if not index:
        pkg = {"selected_docs": [], "context": "", "gaps": ["No docs yet"]}
    else:
        summary = "\n".join(f"- {k}: {v['preview'][:150]}" for k, v in index.items())
        raw = call_model([
            {"role": "system", "content": PROMPT},
            {"role": "user", "content": f"Task: {task}\nDocs:\n{summary}"}
        ])
        try:
            pkg = json.loads(raw)
        except:
            pkg = {"selected_docs": list(index.keys()), "context": summary, "gaps": []}
        for fname in pkg.get("selected_docs", []):
            p = SHARED_KNOWLEDGE / fname
            if p.exists():
                pkg["context"] += f"\n\n--- {fname} ---\n{p.read_text()}"
    pkg["timestamp"] = datetime.utcnow().isoformat()
    VAULT_BUS.mkdir(parents=True, exist_ok=True)
    json.dump(pkg, open(VAULT_BUS / "librarian_to_researcher.json", "w"), indent=2)
    print("[Librarian] Done")
