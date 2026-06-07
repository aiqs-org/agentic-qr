import sys

sys.path.insert(0, "/shared/backtesting")

from config import get_bar_type, get_instrument
from nautilus_trader.model.data import Bar
from nautilus_trader.model.enums import OrderSide
from nautilus_trader.model.objects import Quantity
from nautilus_trader.trading.strategy import Strategy


class GeneratedStrategy(Strategy):
    def __init__(self):
        super().__init__()
        self.instrument_id = get_instrument("SPY").id
        self.bar_type = get_bar_type("SPY")
        self.closes = []
        self.in_position = False
        self.entry_bar_index = None
        self.bar_index = 0

    def on_start(self):
        self.subscribe_bars(self.bar_type)

    def on_bar(self, bar: Bar):
        self.bar_index += 1
        self.closes.append(float(bar.close))

        if self.in_position and self.entry_bar_index is not None:
            if self.bar_index - self.entry_bar_index >= 5:
                self._sell()
                self.entry_bar_index = None
            return

        if len(self.closes) < 2:
            return

        previous_close = self.closes[-2]
        current_close = self.closes[-1]
        close_to_close_return = (current_close / previous_close) - 1.0
        if close_to_close_return < -0.01:
            self.entry_bar_index = self.bar_index
            self._buy()

    def _buy(self):
        if self.in_position:
            return
        order = self.order_factory.market(
            instrument_id=self.instrument_id,
            order_side=OrderSide.BUY,
            quantity=Quantity.from_int(100),
        )
        self.submit_order(order)
        self.in_position = True

    def _sell(self):
        if not self.in_position:
            return
        order = self.order_factory.market(
            instrument_id=self.instrument_id,
            order_side=OrderSide.SELL,
            quantity=Quantity.from_int(100),
        )
        self.submit_order(order)
        self.in_position = False

    def on_stop(self):
        if self.in_position:
            self.close_all_positions(self.instrument_id)
