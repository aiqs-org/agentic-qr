"""Distill raw knowledge graph sources into reviewable candidate nodes."""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx


DISTILLER_MODEL = os.getenv("DISTILLER_MODEL", "")
QWEN_MODEL = os.getenv("QWEN_MODEL", "qwen/qwen3.6-35b-a3b")
QWEN_BASE_URL = os.getenv("QWEN_BASE_URL", "")
QWEN_API_KEY = os.getenv("QWEN_API_KEY", "")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL = (
    os.getenv("DISTILLER_OPENROUTER_MODEL")
    or os.getenv("MINIMAX_MODEL")
    or "minimax/minimax-m2.7"
)
POLL_INTERVAL = int(os.getenv("DISTILLER_POLL_INTERVAL", "15"))

SHARED_CONTEXT_GRAPH = Path(os.getenv("SHARED_CONTEXT_GRAPH_PATH", "/shared/context_graph"))
VAULT_BUS = Path(os.getenv("VAULT_BUS_PATH", "/vault/bus"))

NODES_DIR = SHARED_CONTEXT_GRAPH / "nodes"
RAW_DIR = SHARED_CONTEXT_GRAPH / "raw"
DISTILLED_DIR = SHARED_CONTEXT_GRAPH / "distilled"
REVIEW_EVENTS = VAULT_BUS / "review-events"


SYSTEM_PROMPT = """You distill raw investing and market notes into a belief graph.

Return JSON only. Do not include markdown fences.

Input is a raw source note. Extract 1-5 candidate knowledge nodes. Prefer
middle-layer reusable knowledge over narrow trivia.

Allowed node_type values:
- belief: a raw but meaningful claim or worldview fragment
- principle: a reusable market mechanism or rule that may generalize
- heuristic: an operational rule that could inform strategy construction

For each candidate, return:
{
  "node_type": "belief|principle|heuristic",
  "title": "short title",
  "summary": "2-4 sentence distillation",
  "confidence": 0.15-0.75,
  "validation_required": ["reasoning_review", "historical_examples", "backtest"],
  "rationale": "why this node matters",
  "tags": ["..."]
}

Use candidate confidence unless the source provides strong evidence. Do not
pretend raw opinions are validated.
"""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def compact_ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")


def write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, default=str))
    return path


def load_node(path: Path) -> dict:
    return json.loads(path.read_text())


def raw_text_for(node: dict) -> str:
    ref = node.get("raw_content_ref", "")
    if ref:
        path = Path(ref)
        if path.exists():
            return path.read_text()
        if ref.startswith("/shared/context_graph/"):
            local = SHARED_CONTEXT_GRAPH / ref.removeprefix("/shared/context_graph/")
            if local.exists():
                return local.read_text()
    return node.get("summary") or node.get("title", "")


def already_distilled(node: dict) -> bool:
    if node.get("distillation", {}).get("status") == "completed":
        return True
    if node.get("children"):
        return True
    return False


def model_endpoints() -> list[dict]:
    endpoints = []
    if QWEN_BASE_URL and QWEN_API_KEY:
        endpoints.append(
            {
                "name": "qwen",
                "base_url": QWEN_BASE_URL,
                "api_key": QWEN_API_KEY,
                "model": DISTILLER_MODEL or QWEN_MODEL,
            }
        )
    if OPENROUTER_API_KEY:
        endpoints.append(
            {
                "name": "openrouter",
                "base_url": "https://openrouter.ai/api/v1",
                "api_key": OPENROUTER_API_KEY,
                "model": DISTILLER_MODEL or OPENROUTER_MODEL,
            }
        )
    return endpoints


def call_model(source_node: dict, raw_text: str) -> tuple[list[dict], str]:
    endpoints = model_endpoints()
    if not endpoints:
        return fallback_distillation(source_node, raw_text), "fallback"

    for endpoint in endpoints:
        url = endpoint["base_url"].rstrip("/") + "/chat/completions"
        headers = {"Authorization": f"Bearer {endpoint['api_key']}", "Content-Type": "application/json"}
        payload = {
            "model": endpoint["model"],
            "max_tokens": 2500,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": (
                        "SOURCE NODE:\n"
                        + json.dumps(source_node, indent=2)[:2000]
                        + "\n\nRAW NOTE:\n"
                        + raw_text[:12000]
                        + "\n\nReturn JSON: {\"candidates\": [...]}"
                    ),
                },
            ],
        }
        try:
            response = httpx.post(url, headers=headers, json=payload, timeout=120)
            response.raise_for_status()
            raw = response.json()["choices"][0]["message"]["content"].strip()
            raw = raw.replace("```json", "").replace("```", "").strip()
            data = json.loads(raw)
            candidates = data.get("candidates", data if isinstance(data, list) else [])
            if candidates:
                model_label = f"{endpoint['name']}:{endpoint['model']}"
                return candidates[:5], model_label
        except Exception as exc:
            print(f"[Distiller] {endpoint['name']} failed: {exc}")

    print("[Distiller] all model endpoints failed, using fallback")
    return fallback_distillation(source_node, raw_text), "fallback"


def fallback_distillation(source_node: dict, raw_text: str) -> list[dict]:
    first_line = ""
    for line in raw_text.splitlines():
        stripped = line.strip("#-: ")
        if stripped and not stripped.startswith("---"):
            first_line = stripped
            break
    title = first_line[:100] or source_node.get("title", "Raw belief")
    return [
        {
            "node_type": "belief",
            "title": title,
            "summary": "Raw source captured for human distillation review. Model distillation was unavailable.",
            "confidence": 0.1,
            "validation_required": ["distillation_review", "reasoning_review"],
            "rationale": "Fallback candidate preserves the raw item for review.",
            "tags": ["fallback"],
        }
    ]


def normalize_candidate(candidate: dict) -> dict:
    node_type = candidate.get("node_type", "belief")
    if node_type not in {"belief", "principle", "heuristic"}:
        node_type = "belief"
    confidence = candidate.get("confidence", 0.25)
    try:
        confidence = max(0.0, min(1.0, float(confidence)))
    except Exception:
        confidence = 0.25
    validation = candidate.get("validation_required") or ["reasoning_review"]
    if isinstance(validation, str):
        validation = [validation]
    return {
        "node_type": node_type,
        "title": str(candidate.get("title", "Untitled candidate"))[:160],
        "summary": str(candidate.get("summary", "")),
        "confidence": confidence,
        "validation_required": validation,
        "rationale": str(candidate.get("rationale", "")),
        "tags": candidate.get("tags", []),
    }


def write_candidate(source_node: dict, candidate: dict, ordinal: int) -> tuple[str, Path]:
    model_label = candidate.get("_model", "fallback")
    candidate = normalize_candidate(candidate)
    node_id = f"kn_{compact_ts()}_{ordinal}"
    now = utc_now()
    node_path = NODES_DIR / f"{node_id}.json"
    note_path = DISTILLED_DIR / f"{node_id}.md"

    payload = {
        "node_id": node_id,
        "node_type": candidate["node_type"],
        "title": candidate["title"],
        "summary": candidate["summary"],
        "status": "candidate",
        "confidence": candidate["confidence"],
        "source_type": "system_generated",
        "validation_required": candidate["validation_required"],
        "parents": [source_node["node_id"]],
        "children": [],
        "evidence_supports": [source_node["node_id"]],
        "evidence_contradicts": [],
        "project_ids": source_node.get("project_ids", []),
        "raw_content_ref": source_node.get("raw_content_ref", ""),
        "obsidian_path": str(note_path),
        "distillation": {
            "source_node_id": source_node["node_id"],
            "model": model_label,
            "rationale": candidate["rationale"],
            "tags": candidate["tags"],
        },
        "created_at": now,
        "updated_at": now,
    }
    write_json(node_path, payload)
    write_candidate_note(note_path, payload)
    return node_id, node_path


def write_candidate_note(note_path: Path, node: dict) -> None:
    note_path.parent.mkdir(parents=True, exist_ok=True)
    note_path.write_text(
        "---\n"
        f"node_id: {node['node_id']}\n"
        f"node_type: {node['node_type']}\n"
        f"status: {node['status']}\n"
        f"confidence: {node['confidence']}\n"
        f"parents: {node.get('parents', [])}\n"
        f"validation_required: {node.get('validation_required', [])}\n"
        "---\n\n"
        f"# {node['title']}\n\n"
        "## Summary\n\n"
        f"{node.get('summary', '')}\n\n"
        "## Rationale\n\n"
        f"{node.get('distillation', {}).get('rationale', '')}\n\n"
        "## Validation Needed\n\n"
        + "\n".join(f"- {item}" for item in node.get("validation_required", []))
        + "\n"
    )


def update_source_node(path: Path, source_node: dict, child_ids: list[str]) -> None:
    source_node["children"] = sorted(set(source_node.get("children", []) + child_ids))
    source_node["distillation"] = {
        "status": "completed",
        "completed_at": utc_now(),
        "child_node_ids": child_ids,
        "model": child_model(source_node, child_ids),
    }
    source_node["updated_at"] = utc_now()
    write_json(path, source_node)


def publish_event(source_node: dict, child_ids: list[str]) -> None:
    REVIEW_EVENTS.mkdir(parents=True, exist_ok=True)
    event_path = REVIEW_EVENTS / f"{compact_ts()}_distillation_completed.json"
    write_json(
        event_path,
        {
            "event": "distillation_completed",
            "source_node_id": source_node["node_id"],
            "candidate_node_ids": child_ids,
            "status": "needs_review",
            "created_at": utc_now(),
        },
    )


def child_model(source_node: dict, child_ids: list[str]) -> str:
    for child_id in child_ids:
        path = NODES_DIR / f"{child_id}.json"
        if path.exists():
            try:
                child = json.loads(path.read_text())
                return child.get("distillation", {}).get("model", "unknown")
            except Exception:
                pass
    return source_node.get("distillation", {}).get("model", "unknown")


def process_node(path: Path) -> bool:
    source_node = load_node(path)
    if source_node.get("node_type") != "source":
        return False
    if source_node.get("status") != "raw":
        return False
    if already_distilled(source_node):
        return False

    raw_text = raw_text_for(source_node)
    print(f"[Distiller] distilling {source_node['node_id']}: {source_node.get('title', '')[:80]}")
    candidates, model_label = call_model(source_node, raw_text)
    child_ids = []
    for idx, candidate in enumerate(candidates, start=1):
        candidate["_model"] = model_label
        child_id, child_path = write_candidate(source_node, candidate, idx)
        print(f"[Distiller] wrote {child_id} -> {child_path}")
        child_ids.append(child_id)
    update_source_node(path, source_node, child_ids)
    publish_event(source_node, child_ids)
    return True


def run_once() -> int:
    NODES_DIR.mkdir(parents=True, exist_ok=True)
    processed = 0
    for path in sorted(NODES_DIR.glob("*.json")):
        try:
            if process_node(path):
                processed += 1
        except Exception as exc:
            print(f"[Distiller] failed {path}: {exc}")
    return processed


def main() -> None:
    print("=== context distiller starting ===")
    while True:
        processed = run_once()
        if processed:
            print(f"[Distiller] processed {processed} raw source node(s)")
        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
