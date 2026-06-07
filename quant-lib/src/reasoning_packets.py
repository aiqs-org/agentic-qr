"""Reasoning packet writer for quant-lib outputs.

Mechanical catalogs stay pure. Any research interpretation is written as a
separate packet so strategy workers can opt into it through a ContextPack.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


SHARED_CONTEXT_GRAPH = Path("/shared/context_graph")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def compact_ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")


def write_quant_lib_packet(result: dict, catalog: dict, macro: dict) -> Path:
    packet_id = f"rp_quant_lib_{compact_ts()}"
    out_dir = SHARED_CONTEXT_GRAPH / "reasoning_packets"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{packet_id}.json"
    payload = {
        "packet_id": packet_id,
        "packet_type": "quant_lib_object_catalog",
        "purpose": "Summarize available mechanical market, macro, instrument, and bar objects.",
        "context_mode": "mechanical_catalog_only",
        "rules": [
            "Instrument and macro catalogs are mechanical source-of-truth objects.",
            "Do not write research opinions into instruments.json or macro_catalog.json.",
            "Strategy workers should request separate belief/context graph nodes when they need interpretation.",
        ],
        "instruments_built": result.get("instruments_built", []),
        "bar_parquet_paths": result.get("bar_parquet_paths", {}),
        "errors": result.get("errors", []),
        "catalog_preview": {
            "instruments": sorted(catalog.keys()),
            "macro": sorted(macro.keys()),
        },
        "created_at": utc_now(),
    }
    out_path.write_text(json.dumps(payload, indent=2, default=str))
    return out_path
