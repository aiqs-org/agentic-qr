"""
Connector: FRED (Federal Reserve Economic Data)
Free API key: https://fred.stlouisfed.org/docs/api/api_key.html
Output: normalized macro JSON → shared/data/macro/
"""

import os, json, requests
from datetime import datetime
from pathlib import Path

SHARED_DATA = Path(os.getenv("SHARED_DATA_PATH", "/shared/data"))
FRED_API_KEY = os.getenv("FRED_API_KEY", "")
FRED_URL = "https://api.stlouisfed.org/fred/series/observations"

# Default macro series — swap or extend as needed
DEFAULT_SERIES = {
    "DGS10":   "10yr_treasury_yield",
    "FEDFUNDS": "fed_funds_rate",
    "CPIAUCSL": "cpi_urban",
    "UNRATE":   "unemployment_rate",
    "T10Y2Y":   "yield_curve_10y2y",
    "VIXCLS":   "vix_close",
}

def fetch(series: dict = None, observation_start: str = "2020-01-01") -> list:
    if not FRED_API_KEY:
        print("[FRED] WARNING: FRED_API_KEY not set — skipping")
        return []

    series = series or DEFAULT_SERIES
    out_dir = SHARED_DATA / "macro"
    out_dir.mkdir(parents=True, exist_ok=True)
    results = []

    for series_id, label in series.items():
        print(f"[FRED] Fetching {series_id} ({label})")
        try:
            resp = requests.get(FRED_URL, params={
                "series_id": series_id,
                "api_key": FRED_API_KEY,
                "file_type": "json",
                "observation_start": observation_start,
            }, timeout=30)
            resp.raise_for_status()
            observations = resp.json().get("observations", [])

            records = []
            for obs in observations:
                if obs["value"] == ".":
                    continue
                records.append({
                    "source": "fred",
                    "type": "macro",
                    "series_id": series_id,
                    "label": label,
                    "timestamp": obs["date"],
                    "data": {"value": float(obs["value"])}
                })

            out_file = out_dir / f"{series_id}_{datetime.utcnow().strftime('%Y%m%d')}.json"
            with open(out_file, "w") as f:
                json.dump(records, f, indent=2)
            print(f"[FRED] Saved {len(records)} records → {out_file}")
            results.extend(records)

        except Exception as e:
            print(f"[FRED] Error fetching {series_id}: {e}")

    return results
