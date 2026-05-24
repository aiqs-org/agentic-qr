#!/usr/bin/env python3
"""Check configured model IDs without exposing provider secrets."""

from __future__ import annotations

import argparse
import json
import os
import urllib.request
from dataclasses import dataclass
from pathlib import Path


DEFAULT_ROOT = Path(__file__).resolve().parents[1]
OPENROUTER_MODELS_URL = "https://openrouter.ai/api/v1/models"
SERVICE_ENV_FILES = (
    "strategy-core/.env",
    "verbose/.env",
    "quant-lib/.env",
    "intake/.env",
)
MODEL_KEYS = (
    "GENERATOR_MODEL",
    "ANALYST_MODEL",
    "MINIMAX_MODEL",
    "QWEN_MODEL",
    "GLM_MODEL",
)
BASE_URL_KEYS = (
    "OPENROUTER_BASE_URL",
    "GENERATOR_BASE_URL",
    "ANALYST_BASE_URL",
    "QWEN_BASE_URL",
)


@dataclass
class ModelCheck:
    service: str
    key: str
    model: str
    status: str
    detail: str


def parse_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def load_openrouter_model_ids() -> set[str]:
    with urllib.request.urlopen(OPENROUTER_MODELS_URL, timeout=30) as response:
        payload = json.load(response)
    return {model["id"] for model in payload.get("data", []) if "id" in model}


def is_openrouter_config(values: dict[str, str]) -> bool:
    for key in BASE_URL_KEYS:
        if "openrouter.ai" in values.get(key, ""):
            return True
    return any(key in values for key in ("OPENROUTER_API_KEY", "MINIMAX_MODEL", "GENERATOR_MODEL"))


def is_openrouter_url(value: str) -> bool:
    return "openrouter.ai" in value


def closest(model: str, known_ids: set[str]) -> str | None:
    lowered = model.lower()
    if lowered in {known.lower() for known in known_ids}:
        for known in known_ids:
            if known.lower() == lowered:
                return known
    prefix = lowered.split("/")[-1].split(":")[0]
    hits = sorted(mid for mid in known_ids if prefix and prefix in mid.lower())
    return hits[0] if hits else None


def check_models(root: Path, known_ids: set[str]) -> list[ModelCheck]:
    checks: list[ModelCheck] = []
    for rel in SERVICE_ENV_FILES:
        path = root / rel
        service = rel.split("/", 1)[0]
        values = parse_env(path)
        if not values:
            checks.append(ModelCheck(service, "env", "", "warn", f"{rel} missing or unreadable"))
            continue
        analyst_base_url = values.get("ANALYST_BASE_URL") or values.get("QWEN_BASE_URL") or ""
        if analyst_base_url and not is_openrouter_url(analyst_base_url):
            has_provider_key = bool(values.get("ANALYST_API_KEY") or values.get("QWEN_API_KEY"))
            if not has_provider_key:
                checks.append(ModelCheck(
                    service,
                    "ANALYST_API_KEY",
                    "",
                    "warn",
                    "ANALYST_BASE_URL points outside OpenRouter but no ANALYST_API_KEY/QWEN_API_KEY is set",
                ))
        if not is_openrouter_config(values):
            checks.append(ModelCheck(service, "env", "", "skip", "not configured for OpenRouter"))
            continue
        keys = []
        if "GENERATOR_MODEL" in values:
            keys.append("GENERATOR_MODEL")
        elif "MINIMAX_MODEL" in values:
            keys.append("MINIMAX_MODEL")
        analyst_keys = []
        if "ANALYST_MODEL" in values:
            analyst_keys.append("ANALYST_MODEL")
        elif "QWEN_MODEL" in values:
            analyst_keys.append("QWEN_MODEL")
        if "GLM_MODEL" in values and (
            "ANALYST_BASE_URL" in values or "QWEN_BASE_URL" in values
        ):
            analyst_keys.append("GLM_MODEL")
        if analyst_base_url and not is_openrouter_url(analyst_base_url):
            for key in analyst_keys:
                model = values.get(key)
                if model:
                    checks.append(ModelCheck(
                        service,
                        key,
                        model,
                        "skip",
                        "external analyst provider; not checked against OpenRouter",
                    ))
        else:
            keys.extend(analyst_keys)
        for key in MODEL_KEYS:
            if key not in keys:
                continue
            model = values.get(key)
            if not model:
                continue
            if model in known_ids:
                checks.append(ModelCheck(service, key, model, "ok", "available on OpenRouter"))
            else:
                suggestion = closest(model, known_ids)
                detail = "not found in OpenRouter model list"
                if suggestion:
                    detail += f"; nearest current ID: {suggestion}"
                checks.append(ModelCheck(service, key, model, "error", detail))
    return checks


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate configured model IDs against OpenRouter.")
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT, help="Repository root to inspect.")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    args = parser.parse_args()

    root = args.root.resolve()
    try:
        known_ids = load_openrouter_model_ids()
    except Exception as exc:
        print(f"[WARN ] models  could not load OpenRouter model list: {exc}")
        return 0

    checks = check_models(root, known_ids)
    if args.json:
        print(json.dumps([check.__dict__ for check in checks], indent=2))
    else:
        for check in checks:
            label = check.status.upper()
            model = f" {check.model}" if check.model else ""
            print(f"[{label:5}] {check.service:<13} {check.key:<16}{model} - {check.detail}")
    return 1 if any(check.status == "error" for check in checks) else 0


if __name__ == "__main__":
    raise SystemExit(main())
