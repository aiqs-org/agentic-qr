import os
import json
from pathlib import Path
from datetime import datetime, timezone
import pandas as pd
from nautilus_trader.model.identifiers import InstrumentId, Symbol, Venue
from nautilus_trader.model.objects import Price, Quantity
from nautilus_trader.model.instruments import Equity
from nautilus_trader.model.data import BarType, BarSpecification
from nautilus_trader.model.enums import AggregationSource, BarAggregation, PriceType
from nautilus_trader.model.currencies import USD
from nautilus_trader.persistence.wranglers import BarDataWrangler

SHARED_DATA = Path(os.getenv("SHARED_DATA", "/shared/data"))
SHARED_BACKTESTING = Path(os.getenv("SHARED_BACKTESTING", "/shared/backtesting"))
SHARED_MODELS = Path(os.getenv("SHARED_MODELS", "/shared/models"))
VENUE_STR = os.getenv("DEFAULT_VENUE", "ALPACA")

def load_market_json(json_path):
    raw = json.loads(json_path.read_text())
    records = raw if isinstance(raw, list) else raw.get("bars", raw.get("data", []))
    rows = []
    for rec in records:
        d = rec.get("data", rec)
        rows.append({"timestamp": pd.Timestamp(rec["timestamp"], tz="UTC"), "open": float(d["open"]), "high": float(d["high"]), "low": float(d["low"]), "close": float(d["close"]), "volume": float(d["volume"])})
    df = pd.DataFrame(rows).sort_values("timestamp").reset_index(drop=True)
    df = df.set_index("timestamp")
    return df

def build_equity_instrument(symbol):
    iid = InstrumentId(symbol=Symbol(symbol), venue=Venue(VENUE_STR))
    return Equity(instrument_id=iid, raw_symbol=Symbol(symbol), currency=USD, price_precision=2, price_increment=Price.from_str("0.01"), lot_size=Quantity.from_str("1"), ts_event=0, ts_init=0)

def build_bars(symbol, df, instrument):
    bar_spec = BarSpecification(step=1, aggregation=BarAggregation.DAY, price_type=PriceType.LAST)
    bar_type = BarType(instrument_id=instrument.id, bar_spec=bar_spec, aggregation_source=AggregationSource.EXTERNAL)
    wrangler = BarDataWrangler(bar_type=bar_type, instrument=instrument)
    bars = wrangler.process(data=df)
    print(f"[{symbol}] built {len(bars)} daily bars")
    return bars

def write_bars(symbol, bars):
    out_dir = SHARED_BACKTESTING / "bars" / symbol
    out_dir.mkdir(parents=True, exist_ok=True)
    parquet_path = out_dir / "bars.parquet"
    rows = [{"ts_event": b.ts_event, "ts_init": b.ts_init, "open": str(b.open), "high": str(b.high), "low": str(b.low), "close": str(b.close), "volume": str(b.volume), "instrument_id": str(b.bar_type.instrument_id), "bar_type": str(b.bar_type)} for b in bars]
    pd.DataFrame(rows).to_parquet(parquet_path, index=False)
    print(f"[{symbol}] -> {parquet_path}")
    return parquet_path

def write_instrument_catalog(instruments):
    out_path = SHARED_MODELS / "instruments.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    catalog = {}
    for sym, inst in instruments.items():
        catalog[sym] = {
            "instrument_id": str(inst.id),
            "symbol": inst.id.symbol.value,
            "venue": inst.id.venue.value,
            "price_precision": inst.price_precision,
            "price_increment": str(inst.price_increment),
        }
    out_path.write_text(json.dumps(catalog, indent=2))
    print(f"Instrument catalog -> {out_path}")

def build_macro_catalog():
    macro_dir = SHARED_DATA / "macro"
    out_path = SHARED_MODELS / "macro_catalog.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    catalog = {}
    if macro_dir.exists():
        for json_file in macro_dir.glob("*.json"):
            series_id = json_file.stem.split("_")[0]
            try:
                raw = json.loads(json_file.read_text())
                records = raw if isinstance(raw, list) else raw.get("observations", raw.get("data", []))
                rows = [{"date": pd.Timestamp(rec["timestamp"]), "value": float(rec["data"]["value"])} for rec in records]
                df = pd.DataFrame(rows).sort_values("date")
                catalog[series_id] = {"series_id": series_id, "rows": len(df), "start": str(df["date"].min().date()), "end": str(df["date"].max().date()), "latest_value": float(df["value"].dropna().iloc[-1]) if not df["value"].dropna().empty else None, "path": str(json_file)}
                print(f"[MACRO] {series_id}: {len(df)} rows")
            except Exception as e:
                print(f"[MACRO] failed {json_file.name}: {e}")
    out_path.write_text(json.dumps(catalog, indent=2))
    print(f"Macro catalog -> {out_path}")

def run_object_factory():
    market_dir = SHARED_DATA / "market"
    instruments = {}
    bar_paths = {}
    errors = []
    if market_dir.exists():
        symbol_files = {}
        for json_file in market_dir.glob("*.json"):
            symbol = json_file.stem.split("_")[0].upper()
            symbol_files.setdefault(symbol, []).append(json_file)
        for symbol, files in symbol_files.items():
            try:
                dfs = [load_market_json(f) for f in sorted(files)]
                df = pd.concat(dfs)
                df = df[~df.index.duplicated(keep="first")].sort_index()
                instrument = build_equity_instrument(symbol)
                instruments[symbol] = instrument
                bars = build_bars(symbol, df, instrument)
                parquet_path = write_bars(symbol, bars)
                bar_paths[symbol] = str(parquet_path)
            except Exception as e:
                print(f"[{symbol}] ERROR: {e}")
                errors.append({"symbol": symbol, "error": str(e)})
    write_instrument_catalog(instruments)
    build_macro_catalog()
    return {"event": "quant_lib_objects_built", "timestamp": datetime.now(timezone.utc).isoformat(), "instruments_built": list(instruments.keys()), "bar_parquet_paths": bar_paths, "errors": errors}
