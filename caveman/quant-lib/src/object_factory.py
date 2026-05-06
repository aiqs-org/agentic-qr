"""
object_factory.py
-----------------
Converts raw pipeline data (Alpaca OHLCV + FRED macro) into valid
NautilusTrader objects and writes them to shared/backtesting/.

quant-lib is the object factory only.
Feature engineering and strategy logic belong in strategy-core.
"""

import os
import json
from pathlib import Path
from datetime import datetime, timezone

import pandas as pd
from loguru import logger

from nautilus_trader.model.identifiers import InstrumentId, Symbol, Venue
from nautilus_trader.model.objects import Price, Quantity
from nautilus_trader.model.instruments import Equity
from nautilus_trader.model.data import Bar, BarType, BarSpecification
from nautilus_trader.model.enums import (
    AggregationSource,
    BarAggregation,
    PriceType,
)
from nautilus_trader.model.currencies import USD
from nautilus_trader.persistence.wranglers import BarDataWrangler

SHARED_DATA = Path(os.getenv("SHARED_DATA", "/shared/data"))
SHARED_BACKTESTING = Path(os.getenv("SHARED_BACKTESTING", "/shared/backtesting"))
SHARED_MODELS = Path(os.getenv("SHARED_MODELS", "/shared/models"))
VENUE_STR = os.getenv("DEFAULT_VENUE", "ALPACA")


def build_equity_instrument(symbol: str) -> Equity:
    instrument_id = InstrumentId(symbol=Symbol(symbol), venue=Venue(VENUE_STR))
    return Equity(
        instrument_id=instrument_id,
        raw_symbol=Symbol(symbol),
        currency=USD,
        price_precision=2,
        price_increment=Price.from_str("0.01"),
        multiplier=Quantity.from_str("1"),
        lot_size=Quantity.from_str("1"),
        ts_event=0,
        ts_init=0,
    )


def build_bars_from_csv(symbol: str, csv_path: Path, instrument: Equity) -> list[Bar]:
    df = pd.read_csv(csv_path, parse_dates=["timestamp"])
    df = df.sort_values("timestamp").reset_index(drop=True)

    bar_spec = BarSpecification(
        step=1,
        aggregation=BarAggregation.MINUTE,
        price_type=PriceType.LAST,
    )
    bar_type = BarType(
        instrument_id=instrument.id,
        bar_spec=bar_spec,
        aggregation_source=AggregationSource.EXTERNAL,
    )
    wrangler = BarDataWrangler(bar_type=bar_type, instrument=instrument)
    bars = wrangler.process(data=df)
    logger.info(f"[{symbol}] built {len(bars)} Bar objects")
    return bars


def write_bars(symbol: str, bars: list[Bar]) -> Path:
    out_dir = SHARED_BACKTESTING / "bars" / symbol
    out_dir.mkdir(parents=True, exist_ok=True)
    parquet_path = out_dir / "bars.parquet"
    rows = [{
        "ts_event": b.ts_event,
        "ts_init": b.ts_init,
        "open": str(b.open),
        "high": str(b.high),
        "low": str(b.low),
        "close": str(b.close),
        "volume": str(b.volume),
        "instrument_id": str(b.bar_type.instrument_id),
        "bar_type": str(b.bar_type),
    } for b in bars]
    pd.DataFrame(rows).to_parquet(parquet_path, index=False)
    logger.success(f"[{symbol}] written → {parquet_path}")
    return parquet_path


def write_instrument_catalog(instruments: dict) -> Path:
    out_path = SHARED_MODELS / "instruments.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    catalog = {
        sym: {
            "instrument_id": str(inst.id),
            "symbol": inst.id.symbol.value,
            "venue": inst.id.venue.value,
            "currency": inst.currency.code,
            "price_precision": inst.price_precision,
            "price_increment": str(inst.price_increment),
        }
        for sym, inst in instruments.items()
    }
    out_path.write_text(json.dumps(catalog, indent=2))
    logger.info(f"Instrument catalog → {out_path}")
    return out_path


def build_macro_catalog() -> Path:
    macro_dir = SHARED_DATA / "macro"
    out_path = SHARED_MODELS / "macro_catalog.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    catalog = {}
    if macro_dir.exists():
        for csv_file in macro_dir.glob("*.csv"):
            series_id = csv_file.stem
            df = pd.read_csv(csv_file, parse_dates=["date"])
            df = df.sort_values("date")
            catalog[series_id] = {
                "series_id": series_id,
                "rows": len(df),
                "start": str(df["date"].min().date()),
                "end": str(df["date"].max().date()),
                "latest_value": float(df["value"].dropna().iloc[-1]) if not df["value"].dropna().empty else None,
                "path": str(csv_file),
            }
            logger.info(f"[MACRO] cataloged {series_id}: {len(df)} rows")
    out_path.write_text(json.dumps(catalog, indent=2))
    logger.info(f"Macro catalog → {out_path}")
    return out_path


def run_object_factory() -> dict:
    market_dir = SHARED_DATA / "market"
    instruments = {}
    bar_paths = {}
    errors = []

    if market_dir.exists():
        for csv_file in market_dir.glob("*.csv"):
            symbol = csv_file.stem.upper()
            try:
                instrument = build_equity_instrument(symbol)
                instruments[symbol] = instrument
                bars = build_bars_from_csv(symbol, csv_file, instrument)
                parquet_path = write_bars(symbol, bars)
                bar_paths[symbol] = str(parquet_path)
            except Exception as e:
                logger.error(f"[{symbol}] ❌ {e}")
                errors.append({"symbol": symbol, "error": str(e)})
    else:
        logger.warning(f"No market data dir at {market_dir}")

    write_instrument_catalog(instruments)
    build_macro_catalog()

    return {
        "event": "quant_lib_objects_built",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "instruments_built": list(instruments.keys()),
        "bar_parquet_paths": bar_paths,
        "errors": errors,
    }
