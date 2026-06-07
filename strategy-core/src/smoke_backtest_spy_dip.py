#!/usr/bin/env python3
"""Run a deterministic SPY dip/hold strategy through strategy-core's harness."""

from __future__ import annotations

import json
from pathlib import Path

import swe


def main() -> int:
    strategy_path = Path("/shared/backtesting/strategies/spy_daily_dip_hold_5.py")
    result = swe.run_backtest(strategy_path, {"SPY": {}})
    print(json.dumps(result, indent=2, default=str))
    return 0 if result.get("status") == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
