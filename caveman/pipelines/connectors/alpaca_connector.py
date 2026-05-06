"""
Connector: Alpaca Markets
Free account: https://app.alpaca.markets/signup
Output: normalized OHLCV JSON → shared/data/market/
Swap: replace yfinance_connector.py calls with this
"""

import os, json, requests
from datetime import datetime, timezone
from pathlib import Path

SHARED_DATA = Path(os.getenv("SHARED_DATA_PATH", "/shared/data"))
ALPACA_API_KEY = os.getenv("ALPACA_API_KEY", "")
ALPACA_SECRET_KEY = os.getenv("ALPACA_SECRET_KEY", "")
BASE_URL = "https://data.alpaca.markets/v2/stocks"

TIMEFRAME_MAP = {"1d": "1Day", "1h": "1Hour", "1wk": "1Week"}

def fetch(symbols: list, interval: str = "1d", period: str = "3mo") -> list:
    if not ALPACA_API_KEY or not ALPACA_SECRET_KEY:
        print("[Alpaca] WARNING: API keys not set — skipping")
        return []

    headers = {
        "APCA-API-KEY-ID": ALPACA_API_KEY,
        "APCA-API-SECRET-KEY": ALPACA_SECRET_KEY,
    }

    timeframe = TIMEFRAME_MAP.get(interval, "1Day")
    out_dir = SHARED_DATA / "market"
    out_dir.mkdir(parents=True, exist_ok=True)
    results = []

    # period → start date
    period_days = {"1mo": 30, "3mo": 90, "6mo": 180, "1y": 365}
    days = period_days.get(period, 90)
    from datetime import timedelta
    start = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")

    for symbol in symbols:
        print(f"[Alpaca] Fetching {symbol} {timeframe} from {start}")
        try:
            url = f"{BASE_URL}/{symbol}/bars"
            params = {
                "timeframe": timeframe,
                "start": start,
                "limit": 1000,
                "feed": "iex",
            }
            resp = requests.get(url, headers=headers, params=params, timeout=30)
            resp.raise_for_status()
            bars = resp.json().get("bars", [])

            if not bars:
                print(f"[Alpaca] No data for {symbol}")
                continue

            records = []
            for bar in bars:
                records.append({
                    "source": "alpaca",
                    "type": "ohlcv",
                    "symbol": symbol,
                    "interval": interval,
                    "timestamp": bar["t"],
                    "data": {
                        "open":   round(float(bar["o"]), 6),
                        "high":   round(float(bar["h"]), 6),
                        "low":    round(float(bar["l"]), 6),
                        "close":  round(float(bar["c"]), 6),
                        "volume": int(bar["v"]),
                    }
                })

            out_file = out_dir / f"{symbol}_{interval}_{datetime.now(timezone.utc).strftime('%Y%m%d')}.json"
            with open(out_file, "w") as f:
                json.dump(records, f, indent=2)
            print(f"[Alpaca] Saved {len(records)} records → {out_file}")
            results.extend(records)

        except Exception as e:
            print(f"[Alpaca] Error fetching {symbol}: {e}")

    return results
