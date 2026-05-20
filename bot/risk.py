"""Risk management: position sizing and stop-loss / take-profit calculation."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple


def pip_value(symbol: str) -> float:
    """Return the price increment that equals one pip for a given symbol.

    For most FX pairs a pip is 0.0001. JPY pairs use 0.01.
    """
    s = symbol.upper()
    if s.endswith("JPY"):
        return 0.01
    return 0.0001


@dataclass
class RiskManager:
    risk_per_trade: float = 0.01      # 1% of balance
    stop_loss_pips: int = 30
    take_profit_pips: int = 60
    dynamic_sizing: bool = True
    fixed_lot: float = 0.01
    min_lot: float = 0.01
    max_lot: float = 100.0
    lot_step: float = 0.01
    contract_size: float = 100_000    # 1 standard FX lot

    def compute_lot(self, balance: float, symbol: str) -> float:
        """Return a lot size such that hitting the stop-loss costs ~risk_per_trade of balance."""
        if not self.dynamic_sizing:
            return self.fixed_lot

        risk_amount = balance * self.risk_per_trade
        pip = pip_value(symbol)
        # Loss per 1.0 lot if SL is hit (USD-quote pair approximation):
        loss_per_lot = self.stop_loss_pips * pip * self.contract_size
        if loss_per_lot <= 0:
            return self.min_lot

        raw_lot = risk_amount / loss_per_lot
        # Round down to lot_step
        steps = int(raw_lot / self.lot_step)
        lot = max(self.min_lot, min(self.max_lot, steps * self.lot_step))
        return round(lot, 2)

    def sl_tp(self, symbol: str, side: int, entry_price: float) -> Tuple[float, float]:
        """Compute (stop_loss, take_profit) prices.

        side: +1 for BUY, -1 for SELL.
        """
        pip = pip_value(symbol)
        sl_dist = self.stop_loss_pips * pip
        tp_dist = self.take_profit_pips * pip

        if side > 0:  # BUY
            sl = entry_price - sl_dist
            tp = entry_price + tp_dist
        else:         # SELL
            sl = entry_price + sl_dist
            tp = entry_price - tp_dist
        return round(sl, 5), round(tp, 5)
