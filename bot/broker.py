"""MetaTrader 5 broker connector.

NOTE: The `MetaTrader5` Python package is Windows-only and requires the MT5
terminal to be installed. This module imports it lazily so the rest of the
bot (backtester, strategy) can be developed and tested on any OS.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import List, Optional

import pandas as pd

from .config import BotConfig

log = logging.getLogger("forex_bot")


_TIMEFRAME_MAP = {
    "M1": "TIMEFRAME_M1",
    "M5": "TIMEFRAME_M5",
    "M15": "TIMEFRAME_M15",
    "M30": "TIMEFRAME_M30",
    "H1": "TIMEFRAME_H1",
    "H4": "TIMEFRAME_H4",
    "D1": "TIMEFRAME_D1",
}


@dataclass
class Position:
    ticket: int
    symbol: str
    side: int          # +1 buy, -1 sell
    volume: float
    price_open: float
    sl: float
    tp: float
    profit: float


class MT5Broker:
    """Thin wrapper around the MetaTrader5 Python API."""

    def __init__(self, cfg: BotConfig):
        self.cfg = cfg
        self._mt5 = None  # lazy import

    # -- connection -----------------------------------------------------
    def _ensure_mt5(self):
        if self._mt5 is None:
            try:
                import MetaTrader5 as mt5  # type: ignore
            except ImportError as e:
                raise RuntimeError(
                    "MetaTrader5 package not installed. It is Windows-only.\n"
                    "Install with: pip install MetaTrader5"
                ) from e
            self._mt5 = mt5
        return self._mt5

    def connect(self) -> bool:
        mt5 = self._ensure_mt5()
        kwargs = {}
        if self.cfg.mt5.path:
            kwargs["path"] = self.cfg.mt5.path
        if not mt5.initialize(**kwargs):
            log.error("MT5 initialize() failed: %s", mt5.last_error())
            return False
        if self.cfg.mt5.login:
            ok = mt5.login(
                login=self.cfg.mt5.login,
                password=self.cfg.mt5.password,
                server=self.cfg.mt5.server,
            )
            if not ok:
                log.error("MT5 login failed: %s", mt5.last_error())
                return False
        info = mt5.account_info()
        if info is not None:
            log.info("Connected to MT5 | login=%s | server=%s | balance=%.2f %s",
                     info.login, info.server, info.balance, info.currency)
        return True

    def disconnect(self) -> None:
        if self._mt5 is not None:
            self._mt5.shutdown()

    # -- account / market data -----------------------------------------
    def account_balance(self) -> float:
        mt5 = self._ensure_mt5()
        info = mt5.account_info()
        return float(info.balance) if info else 0.0

    def get_rates(self, symbol: str, timeframe: str, count: int = 500) -> pd.DataFrame:
        mt5 = self._ensure_mt5()
        tf_attr = _TIMEFRAME_MAP.get(timeframe.upper())
        if tf_attr is None:
            raise ValueError(f"Unsupported timeframe: {timeframe}")
        tf = getattr(mt5, tf_attr)
        rates = mt5.copy_rates_from_pos(symbol, tf, 0, count)
        if rates is None or len(rates) == 0:
            return pd.DataFrame()
        df = pd.DataFrame(rates)
        df["time"] = pd.to_datetime(df["time"], unit="s")
        df = df.rename(columns={"tick_volume": "volume"})
        return df[["time", "open", "high", "low", "close", "volume"]]

    def symbol_tick(self, symbol: str):
        mt5 = self._ensure_mt5()
        return mt5.symbol_info_tick(symbol)

    # -- orders ---------------------------------------------------------
    def open_market(self, symbol: str, side: int, volume: float,
                    sl: float, tp: float, comment: str = "forex_bot"):
        mt5 = self._ensure_mt5()
        if not mt5.symbol_select(symbol, True):
            raise RuntimeError(f"Failed to select symbol: {symbol}")
        tick = mt5.symbol_info_tick(symbol)
        price = tick.ask if side > 0 else tick.bid
        order_type = mt5.ORDER_TYPE_BUY if side > 0 else mt5.ORDER_TYPE_SELL

        req = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": volume,
            "type": order_type,
            "price": price,
            "sl": sl,
            "tp": tp,
            "deviation": self.cfg.trading.deviation,
            "magic": self.cfg.trading.magic_number,
            "comment": comment,
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        result = mt5.order_send(req)
        if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
            log.error("order_send failed: %s", result)
            return None
        log.info("Opened %s %.2f %s @ %.5f (SL=%.5f TP=%.5f) ticket=%s",
                 "BUY" if side > 0 else "SELL", volume, symbol, price, sl, tp, result.order)
        return result

    def positions(self, symbol: Optional[str] = None) -> List[Position]:
        mt5 = self._ensure_mt5()
        raw = mt5.positions_get(symbol=symbol) if symbol else mt5.positions_get()
        if raw is None:
            return []
        out: List[Position] = []
        for p in raw:
            out.append(Position(
                ticket=p.ticket, symbol=p.symbol,
                side=1 if p.type == mt5.POSITION_TYPE_BUY else -1,
                volume=p.volume, price_open=p.price_open,
                sl=p.sl, tp=p.tp, profit=p.profit,
            ))
        return out

    def close_position(self, pos: Position):
        mt5 = self._ensure_mt5()
        tick = mt5.symbol_info_tick(pos.symbol)
        price = tick.bid if pos.side > 0 else tick.ask
        order_type = mt5.ORDER_TYPE_SELL if pos.side > 0 else mt5.ORDER_TYPE_BUY
        req = {
            "action": mt5.TRADE_ACTION_DEAL,
            "position": pos.ticket,
            "symbol": pos.symbol,
            "volume": pos.volume,
            "type": order_type,
            "price": price,
            "deviation": self.cfg.trading.deviation,
            "magic": self.cfg.trading.magic_number,
            "comment": "forex_bot_close",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        return mt5.order_send(req)
