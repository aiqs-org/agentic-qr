"""
venue.py
--------
Builds a correctly configured NautilusTrader BacktestEngine.

IMPORTANT DEFAULTS (do not change without testing):
- bar_execution=True   : allows market orders to fill against bar OHLC prices.
                         Without this, all orders reject with 'no market for X'.
- AccountType.MARGIN   : allows both long and short. CASH account blocks short
                         selling and rejects sells when no position exists.
- OmsType.NETTING      : standard for single-instrument equity strategies.
- price_precision=2    : SPY/QQQ/TLT/GLD all use 2 decimal places.
                         Bars must be formatted with f'{price:.2f}' — NOT
                         str(round(x,2)) which produces '693.0' (precision=1).
"""

from nautilus_trader.backtest.engine import BacktestEngine, BacktestEngineConfig
from nautilus_trader.model.currencies import USD
from nautilus_trader.model.enums import AccountType, OmsType
from nautilus_trader.model.identifiers import Venue
from nautilus_trader.model.objects import Money

VENUE = Venue("SIM")

def build_engine(trader_id: str = "TRADER-001", starting_balance: float = 100_000.0) -> BacktestEngine:
    engine = BacktestEngine(config=BacktestEngineConfig(trader_id=trader_id))
    engine.add_venue(
        venue=VENUE,
        oms_type=OmsType.NETTING,
        account_type=AccountType.MARGIN,
        base_currency=USD,
        starting_balances=[Money(starting_balance, USD)],
        bar_execution=True,
    )
    return engine
