"""Trading strategies.

A strategy receives an OHLCV pandas DataFrame and emits a Signal:
  +1 = BUY, -1 = SELL, 0 = HOLD/FLAT.

All strategies must implement:
    attach_indicators(df) -> df with extra columns
    generate_signal(df)   -> Signal based on the most recent bars
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from typing import Protocol

import numpy as np
import pandas as pd


class Signal(IntEnum):
    SELL = -1
    HOLD = 0
    BUY = 1


class Strategy(Protocol):
    def generate_signal(self, df: pd.DataFrame) -> Signal: ...
    def attach_indicators(self, df: pd.DataFrame) -> pd.DataFrame: ...


# ---------- shared indicator helpers ----------------------------------

def _ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()


def _rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    # Wilder's smoothing == EMA with alpha=1/period
    avg_gain = gain.ewm(alpha=1 / period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return rsi.fillna(50.0)


def _macd(series: pd.Series, fast: int, slow: int, signal: int):
    ema_fast = _ema(series, fast)
    ema_slow = _ema(series, slow)
    macd = ema_fast - ema_slow
    sig = _ema(macd, signal)
    hist = macd - sig
    return macd, sig, hist


# ---------- strategies ------------------------------------------------

@dataclass
class MACrossoverStrategy:
    """Classic fast/slow simple-moving-average crossover."""

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
        if len(df) < self.slow_period + 2:
            return Signal.HOLD
        d = self.attach_indicators(df)
        prev, curr = d.iloc[-2], d.iloc[-1]
        if pd.isna(prev["sma_slow"]) or pd.isna(curr["sma_slow"]):
            return Signal.HOLD
        up = prev["sma_fast"] <= prev["sma_slow"] and curr["sma_fast"] > curr["sma_slow"]
        dn = prev["sma_fast"] >= prev["sma_slow"] and curr["sma_fast"] < curr["sma_slow"]
        if up:
            return Signal.BUY
        if dn:
            return Signal.SELL
        return Signal.HOLD


@dataclass
class RSIStrategy:
    """RSI mean-reversion: BUY when RSI exits oversold zone, SELL when exits overbought.

    A signal fires on the bar where RSI crosses BACK above `oversold` (BUY) or BACK
    below `overbought` (SELL) -- this avoids buying into a falling knife.
    """

    period: int = 14
    overbought: float = 70.0
    oversold: float = 30.0

    def attach_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        out = df.copy()
        out["rsi"] = _rsi(out["close"], self.period)
        return out

    def generate_signal(self, df: pd.DataFrame) -> Signal:
        if len(df) < self.period + 2:
            return Signal.HOLD
        d = self.attach_indicators(df)
        prev, curr = d.iloc[-2], d.iloc[-1]
        if pd.isna(prev["rsi"]) or pd.isna(curr["rsi"]):
            return Signal.HOLD
        if prev["rsi"] <= self.oversold < curr["rsi"]:
            return Signal.BUY
        if prev["rsi"] >= self.overbought > curr["rsi"]:
            return Signal.SELL
        return Signal.HOLD


@dataclass
class MACDStrategy:
    """MACD-line / signal-line crossover."""

    fast: int = 12
    slow: int = 26
    signal: int = 9

    def __post_init__(self) -> None:
        if self.fast >= self.slow:
            raise ValueError("fast must be < slow")

    def attach_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        out = df.copy()
        macd, sig, hist = _macd(out["close"], self.fast, self.slow, self.signal)
        out["macd"] = macd
        out["macd_signal"] = sig
        out["macd_hist"] = hist
        return out

    def generate_signal(self, df: pd.DataFrame) -> Signal:
        if len(df) < self.slow + self.signal + 2:
            return Signal.HOLD
        d = self.attach_indicators(df)
        prev, curr = d.iloc[-2], d.iloc[-1]
        if pd.isna(prev["macd_signal"]) or pd.isna(curr["macd_signal"]):
            return Signal.HOLD
        up = prev["macd"] <= prev["macd_signal"] and curr["macd"] > curr["macd_signal"]
        dn = prev["macd"] >= prev["macd_signal"] and curr["macd"] < curr["macd_signal"]
        if up:
            return Signal.BUY
        if dn:
            return Signal.SELL
        return Signal.HOLD


@dataclass
class BreakoutStrategy:
    """Donchian-channel breakout: BUY on close above N-bar high, SELL on close below N-bar low."""

    period: int = 20

    def attach_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        out = df.copy()
        # Use the previous N bars (exclude current) so a "breakout" is meaningful.
        out["donch_high"] = out["high"].shift(1).rolling(self.period).max()
        out["donch_low"] = out["low"].shift(1).rolling(self.period).min()
        return out

    def generate_signal(self, df: pd.DataFrame) -> Signal:
        if len(df) < self.period + 2:
            return Signal.HOLD
        d = self.attach_indicators(df)
        curr = d.iloc[-1]
        if pd.isna(curr["donch_high"]) or pd.isna(curr["donch_low"]):
            return Signal.HOLD
        if curr["close"] > curr["donch_high"]:
            return Signal.BUY
        if curr["close"] < curr["donch_low"]:
            return Signal.SELL
        return Signal.HOLD


# ---------- factory ---------------------------------------------------

def build_strategy(name: str, **kwargs) -> Strategy:
    name = name.lower()
    if name == "ma_crossover":
        return MACrossoverStrategy(
            fast_period=kwargs.get("fast_period", 20),
            slow_period=kwargs.get("slow_period", 50),
        )
    if name == "rsi":
        return RSIStrategy(
            period=kwargs.get("period", 14),
            overbought=kwargs.get("overbought", 70.0),
            oversold=kwargs.get("oversold", 30.0),
        )
    if name == "macd":
        return MACDStrategy(
            fast=kwargs.get("fast", 12),
            slow=kwargs.get("slow", 26),
            signal=kwargs.get("signal", 9),
        )
    if name == "breakout":
        return BreakoutStrategy(period=kwargs.get("period", 20))
    raise ValueError(
        f"Unknown strategy: {name!r}. "
        "Available: ma_crossover, rsi, macd, breakout"
    )
