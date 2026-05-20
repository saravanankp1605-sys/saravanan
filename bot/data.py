"""Historical OHLCV data loaders for backtesting.

Sources supported:
  - synthetic : built-in random-walk generator (no internet needed)
  - csv       : a local file with columns time,open,high,low,close,volume
  - yfinance  : Yahoo! Finance via the yfinance package (free, internet required)
  - mt5       : pull a date range straight from the MetaTrader 5 terminal

All loaders return a DataFrame with columns:
    time, open, high, low, close, volume
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd


def load_csv(path: str | Path) -> pd.DataFrame:
    """Load OHLCV from CSV. Expects columns: time,open,high,low,close,volume."""
    df = pd.read_csv(path)
    if "time" not in df.columns:
        # try common alternatives
        for alt in ("date", "Date", "Datetime", "timestamp"):
            if alt in df.columns:
                df = df.rename(columns={alt: "time"})
                break
    df["time"] = pd.to_datetime(df["time"])
    df.columns = [c.lower() for c in df.columns]
    needed = ["time", "open", "high", "low", "close"]
    for col in needed:
        if col not in df.columns:
            raise ValueError(f"CSV is missing required column: {col}")
    if "volume" not in df.columns:
        df["volume"] = 0
    return df[["time", "open", "high", "low", "close", "volume"]].reset_index(drop=True)


def load_yfinance(symbol: str, start: str, end: str,
                  interval: str = "15m") -> pd.DataFrame:
    """Fetch OHLCV from Yahoo Finance.

    Forex symbols on Yahoo end in '=X', e.g. 'EURUSD=X'. If `symbol` is plain
    'EURUSD' we'll add the suffix automatically.

    Yahoo limits intraday history (e.g. 60 days for <=15m intervals).
    """
    try:
        import yfinance as yf  # type: ignore
    except ImportError as e:
        raise RuntimeError(
            "yfinance is required for source='yfinance'. Install with:\n"
            "    pip install yfinance"
        ) from e

    if "=" not in symbol and "/" not in symbol and len(symbol) == 6:
        symbol = f"{symbol}=X"

    df = yf.download(symbol, start=start, end=end, interval=interval,
                     progress=False, auto_adjust=False)
    if df is None or df.empty:
        raise RuntimeError(
            f"yfinance returned no data for {symbol} {start}..{end} @ {interval}"
        )
    # Flatten columns if MultiIndex (newer yfinance versions)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [c[0] for c in df.columns]
    df = df.reset_index().rename(columns={
        "Date": "time", "Datetime": "time",
        "Open": "open", "High": "high", "Low": "low",
        "Close": "close", "Volume": "volume",
    })
    df["time"] = pd.to_datetime(df["time"])
    if "volume" not in df.columns:
        df["volume"] = 0
    return df[["time", "open", "high", "low", "close", "volume"]].dropna().reset_index(drop=True)


def load_mt5_range(symbol: str, timeframe: str,
                   start: str | datetime, end: str | datetime) -> pd.DataFrame:
    """Pull a date range directly from a connected MT5 terminal.

    Requires Windows + the MetaTrader5 package + an open MT5 terminal (or call
    `MT5Broker.connect()` first).
    """
    try:
        import MetaTrader5 as mt5  # type: ignore
    except ImportError as e:
        raise RuntimeError(
            "MetaTrader5 package required for source='mt5'. Windows-only:\n"
            "    pip install MetaTrader5"
        ) from e

    tf_map = {
        "M1": mt5.TIMEFRAME_M1, "M5": mt5.TIMEFRAME_M5,
        "M15": mt5.TIMEFRAME_M15, "M30": mt5.TIMEFRAME_M30,
        "H1": mt5.TIMEFRAME_H1, "H4": mt5.TIMEFRAME_H4,
        "D1": mt5.TIMEFRAME_D1,
    }
    tf = tf_map.get(timeframe.upper())
    if tf is None:
        raise ValueError(f"Unsupported timeframe: {timeframe}")

    if not mt5.initialize():
        raise RuntimeError(f"mt5.initialize() failed: {mt5.last_error()}")

    s = pd.to_datetime(start).to_pydatetime()
    e = pd.to_datetime(end).to_pydatetime()
    rates = mt5.copy_rates_range(symbol, tf, s, e)
    if rates is None or len(rates) == 0:
        raise RuntimeError(f"MT5 returned no data for {symbol} {start}..{end}")

    df = pd.DataFrame(rates)
    df["time"] = pd.to_datetime(df["time"], unit="s")
    df = df.rename(columns={"tick_volume": "volume"})
    return df[["time", "open", "high", "low", "close", "volume"]]


def load_data(source: str, *, csv_path: Optional[str] = None,
              yfinance_symbol: Optional[str] = None,
              mt5_symbol: Optional[str] = None,
              timeframe: str = "M15",
              start: Optional[str] = None,
              end: Optional[str] = None,
              interval: str = "15m") -> pd.DataFrame:
    """Dispatch helper used by run_backtest.py."""
    source = source.lower()
    if source == "synthetic":
        from .backtester import generate_synthetic_ohlcv
        return generate_synthetic_ohlcv()
    if source == "csv":
        if not csv_path:
            raise ValueError("data.csv_path is required for source='csv'")
        return load_csv(csv_path)
    if source == "yfinance":
        if not yfinance_symbol or not start or not end:
            raise ValueError(
                "data.yfinance_symbol, data.start_date, data.end_date "
                "are required for source='yfinance'"
            )
        return load_yfinance(yfinance_symbol, start, end, interval)
    if source == "mt5":
        if not mt5_symbol or not start or not end:
            raise ValueError(
                "symbol, data.start_date, data.end_date are required for source='mt5'"
            )
        return load_mt5_range(mt5_symbol, timeframe, start, end)
    raise ValueError(
        f"Unknown data source: {source!r}. "
        "Use one of: synthetic, csv, yfinance, mt5"
    )
