import os, json, time, requests
import yfinance as yf
from datetime import datetime
from pathlib import Path

SHARED_DATA = Path(os.getenv("SHARED_DATA_PATH", "/shared/data"))

def fetch(symbols: list, interval: str = "1d", period: str = "1mo") -> list:
    out_dir = SHARED_DATA / "market"
    out_dir.mkdir(parents=True, exist_ok=True)
    results = []
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    })
    for symbol in symbols:
        print(f"[yfinance] Fetching {symbol} {interval} {period}")
        try:
            ticker = yf.Ticker(symbol, session=session)
            df = ticker.history(period=period, interval=interval)
            if df.empty:
                print(f"[yfinance] No data for {symbol}")
                continue
            records = []
            for ts, row in df.iterrows():
                records.append({
                    "source": "yfinance",
                    "type": "ohlcv",
                    "symbol": symbol,
                    "interval": interval,
                    "timestamp": ts.isoformat(),
                    "data": {
                        "open": round(float(row["Open"]), 6),
                        "high": round(float(row["High"]), 6),
                        "low": round(float(row["Low"]), 6),
                        "close": round(float(row["Close"]), 6),
                        "volume": int(row["Volume"]),
                    }
                })
            out_file = out_dir / f"{symbol}_{interval}_{datetime.utcnow().strftime('%Y%m%d')}.json"
            with open(out_file, "w") as f:
                json.dump(records, f, indent=2)
            print(f"[yfinance] Saved {len(records)} records → {out_file}")
            results.extend(records)
            time.sleep(2)
        except Exception as e:
            print(f"[yfinance] Error fetching {symbol}: {e}")
    return results
