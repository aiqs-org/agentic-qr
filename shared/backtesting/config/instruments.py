from nautilus_trader.test_kit.providers import TestInstrumentProvider
from nautilus_trader.model.identifiers import InstrumentId
from nautilus_trader.model.enums import AggregationSource, BarAggregation
from nautilus_trader.model.data import BarType, BarSpecification

SYMBOLS = ["SPY", "QQQ", "TLT", "GLD"]

def get_instrument(symbol: str):
    return TestInstrumentProvider.equity(symbol=symbol, venue="SIM")

def get_bar_type(symbol: str) -> BarType:
    instrument = get_instrument(symbol)
    return BarType(
        instrument.id,
        BarSpecification(1, BarAggregation.DAY, AggregationSource.EXTERNAL)
    )

def get_instrument_id(symbol: str) -> InstrumentId:
    return get_instrument(symbol).id
