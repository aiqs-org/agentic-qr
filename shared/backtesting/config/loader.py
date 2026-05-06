"""
loader.py
---------
Loads pipeline market data from /shared/data/market/ into NautilusTrader Bar objects.

Pipeline JSON format (Alpaca connector):
    [{"source": "alpaca", "symbol": "SPY", "timestamp": "...", "data": {"open": ..., "high": ..., "low": ..., "close": ..., "volume": ...}}]

GOTCHAS:
- OHLCV is nested inside 'data' key — not top-level.
- Use f'{x:.2f}' for Price — never str(round(x,2)) which gives precision=1 on whole numbers.
- drop_duplicates() needs 'timestamp' column only — raw df has dict column which is unhashable.
"""

import json
import glob
from pathlib import Path
import pandas as pd
from nautilus_trader.model.objects import Price, Quantity
from nautilus_trader.model.data import Bar, BarType

SHARED_DATA = Path("/shared/data/market")

def load_bars(symbol: str, bar_type: BarType, data_dir: Path = SHARED_DATA) -> list:
    pattern = str(data_dir / f"{symbol}_1d_*.json")
    files = sorted(glob.glob(pattern))
    if not files:
        raise FileNotFoundError(f"No data files found for {symbol} at {pattern}")
    records = []
    for f in files:
        for r in json.load(open(f)):
            records.append({
                "timestamp": pd.Timestamp(r["timestamp"]),
                "open":  r["data"]["open"],
                "high":  r["data"]["high"],
                "low":   r["data"]["low"],
                "close": r["data"]["close"],
                "volume": r["data"]["volume"],
            })
    df = pd.DataFrame(records).drop_duplicates("timestamp").sort_values("timestamp").reset_index(drop=True)
    bars = []
    for _, row in df.iterrows():
        ts = int(row.timestamp.timestamp() * 1e9)
        bars.append(Bar(
            bar_type=bar_type,
            open=Price.from_str(f"{row.open:.2f}"),
            high=Price.from_str(f"{row.high:.2f}"),
            low=Price.from_str(f"{row.low:.2f}"),
            close=Price.from_str(f"{row.close:.2f}"),
            volume=Quantity.from_int(int(row.volume)),
            ts_event=ts,
            ts_init=ts,
        ))
    return bars


def load_quotes_from_bars(symbol: str, bar_type, data_dir: Path = SHARED_DATA):
    """Generate synthetic QuoteTick data from bars for backtest execution.
    Uses ts_event - 1 so quotes arrive before bar-triggered orders."""
    from nautilus_trader.model.data import QuoteTick
    from nautilus_trader.model.objects import Price, Quantity as Q
    bars = load_bars(symbol, bar_type, data_dir)
    quotes = []
    for bar in bars:
        qt = QuoteTick(
            instrument_id=bar.bar_type.instrument_id,
            bid_price=bar.close,
            ask_price=bar.close,
            bid_size=Q.from_int(10000),
            ask_size=Q.from_int(10000),
            ts_event=bar.ts_event - 1,
            ts_init=bar.ts_init - 1,
        )
        quotes.append(qt)
    return quotes

def load_macro(series_id: str, data_dir: Path = Path("/shared/data/macro")) -> pd.DataFrame:
    pattern = str(data_dir / f"{series_id}_*.json")
    files = sorted(glob.glob(pattern))
    if not files:
        raise FileNotFoundError(f"No macro data for {series_id} at {pattern}")
    records = []
    for f in files:
        for r in json.load(open(f)):
            records.append({
                "date": pd.Timestamp(r.get("date") or r.get("timestamp")),
                "value": r.get("value") or r.get("data"),
            })
    return pd.DataFrame(records).drop_duplicates("date").sort_values("date").reset_index(drop=True)
