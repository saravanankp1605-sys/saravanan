"""Trading strategies.

A strategy receives an OHLCV pandas DataFrame and emits a Signal:
  +1 = BUY, -1 = SELL, 0 = HOLD/FLAT.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from typing import Protocol

import pandas as pd


class Signal(IntEnum):
    SELL = -1
    HOLD = 0
    BUY = 1


class Strategy(Protocol):
    def generate_signal(self, df: pd.DataFrame) -> Signal: ...
    def attach_indicators(self, df: pd.DataFrame) -> pd.DataFrame: ...


@dataclass
class MACrossoverStrategy:
    """Classic fast/slow simple-moving-average crossover.

    BUY  when fast SMA crosses above slow SMA.
    SELL when fast SMA crosses below slow SMA.
    """

    fast_period: int = 20
    slow_period: int = 50

    def __post_init__(self) -> None:
        if self.fast_period >= self.slow_period:
            raise ValueError("fast_period must be < slow_period")

    def attach_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        out = df.copy()
        out["sma_fast"] = out["close"].rolling(self.fast_period).mean()
        out["sma_slow"] = out["close"].rolling(self.slow_period).mean()
        return out

    def generate_signal(self, df: pd.DataFrame) -> Signal:
        """Generate signal from the most recent two completed bars."""
        if len(df) < self.slow_period + 2:
            return Signal.HOLD

        d = self.attach_indicators(df)
        prev = d.iloc[-2]
        curr = d.iloc[-1]

        if pd.isna(prev["sma_slow"]) or pd.isna(curr["sma_slow"]):
            return Signal.HOLD

        crossed_up = prev["sma_fast"] <= prev["sma_slow"] and curr["sma_fast"] > curr["sma_slow"]
        crossed_down = prev["sma_fast"] >= prev["sma_slow"] and curr["sma_fast"] < curr["sma_slow"]

        if crossed_up:
            return Signal.BUY
        if crossed_down:
            return Signal.SELL
        return Signal.HOLD


def build_strategy(name: str, **kwargs) -> Strategy:
    if name == "ma_crossover":
        return MACrossoverStrategy(
            fast_period=kwargs.get("fast_period", 20),
            slow_period=kwargs.get("slow_period", 50),
        )
    raise ValueError(f"Unknown strategy: {name}")
