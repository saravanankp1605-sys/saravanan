"""Simple bar-by-bar backtester.

Walks through OHLCV history, runs the strategy after each closed bar, and
simulates trades with stop-loss / take-profit. Reports equity curve and stats.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

import numpy as np
import pandas as pd

from .risk import RiskManager, pip_value
from .strategy import Signal, Strategy


@dataclass
class Trade:
    entry_time: pd.Timestamp
    exit_time: Optional[pd.Timestamp]
    side: int
    entry: float
    exit: Optional[float]
    sl: float
    tp: float
    volume: float
    pnl: float = 0.0
    reason: str = ""  # "tp" | "sl" | "signal" | "eod"


@dataclass
class BacktestResult:
    trades: List[Trade] = field(default_factory=list)
    equity_curve: pd.Series = field(default_factory=lambda: pd.Series(dtype=float))
    initial_balance: float = 10_000.0

    @property
    def final_balance(self) -> float:
        return float(self.equity_curve.iloc[-1]) if len(self.equity_curve) else self.initial_balance

    def summary(self, commission_per_lot: float = 0.0,
                spread_pips: float = 0.0,
                pip_value: float = 0.0001,
                contract_size: float = 100_000) -> dict:
        """Return a summary dict with P&L, win/loss, fees, and max drawdown.

        If commission_per_lot or spread_pips are provided, net P&L accounts
        for transaction costs.
        """
        n = len(self.trades)

        # Compute per-trade net P&L (after fees)
        net_pnls: List[float] = []
        total_commission = 0.0
        total_spread_cost = 0.0
        total_gross_pnl = 0.0
        for t in self.trades:
            comm = 2 * commission_per_lot * t.volume
            spread = spread_pips * pip_value * t.volume * contract_size
            net = t.pnl - comm - spread
            net_pnls.append(net)
            total_commission += comm
            total_spread_cost += spread
            total_gross_pnl += t.pnl

        total_fees = total_commission + total_spread_cost
        total_net_pnl = total_gross_pnl - total_fees

        wins = [p for p in net_pnls if p > 0]
        losses = [p for p in net_pnls if p <= 0]
        win_rate = (len(wins) / n) if n else 0.0
        gross_profit = sum(wins)
        gross_loss = -sum(losses) or 1e-9
        profit_factor = gross_profit / gross_loss
        net_return = total_net_pnl / self.initial_balance

        # Max drawdown from equity curve
        equity = self.equity_curve
        if len(equity):
            peak = equity.cummax()
            dd = (equity - peak) / peak
            max_dd = float(dd.min())
            max_dd_abs = float((equity - peak).min())
        else:
            max_dd = 0.0
            max_dd_abs = 0.0

        return {
            "trades": n,
            "winning_trades": len(wins),
            "losing_trades": len(losses),
            "win_rate": round(win_rate, 4),
            "profit_factor": round(profit_factor, 3),
            "gross_pnl": round(total_gross_pnl, 2),
            "total_commissions": round(total_commission, 2),
            "total_spread_cost": round(total_spread_cost, 2),
            "total_fees": round(total_fees, 2),
            "net_pnl": round(total_net_pnl, 2),
            "net_return": round(net_return, 4),
            "final_balance": round(self.initial_balance + total_net_pnl, 2),
            "max_drawdown_pct": round(max_dd, 4),
            "max_drawdown_abs": round(max_dd_abs, 2),
        }


def run_backtest(df: pd.DataFrame, strategy: Strategy, risk: RiskManager,
                 symbol: str = "EURUSD",
                 initial_balance: float = 10_000.0) -> BacktestResult:
    """Run a deterministic bar-by-bar backtest.

    Assumptions:
    - Orders fill at the next bar's open.
    - SL/TP are checked against the bar's high/low (intrabar order is unknown,
      so when both are hit in the same bar we conservatively assume SL first).
    - Only one open position at a time.
    """
    df = strategy.attach_indicators(df).reset_index(drop=True)
    pip = pip_value(symbol)
    contract = risk.contract_size

    balance = initial_balance
    equity_history: list[tuple[pd.Timestamp, float]] = []
    trades: list[Trade] = []
    open_trade: Optional[Trade] = None
    pending_signal: Signal = Signal.HOLD

    for i in range(1, len(df)):
        bar = df.iloc[i]
        prev = df.iloc[i - 1]
        time = bar["time"] if "time" in df.columns else pd.Timestamp(i, unit="s")

        # 1) Manage open trade against this bar
        if open_trade is not None:
            hit_sl = (bar["low"] <= open_trade.sl <= bar["high"]) if open_trade.side > 0 \
                else (bar["low"] <= open_trade.sl <= bar["high"])
            hit_tp = (bar["low"] <= open_trade.tp <= bar["high"])

            exit_price: Optional[float] = None
            reason = ""
            if open_trade.side > 0:
                if bar["low"] <= open_trade.sl:
                    exit_price, reason = open_trade.sl, "sl"
                elif bar["high"] >= open_trade.tp:
                    exit_price, reason = open_trade.tp, "tp"
            else:
                if bar["high"] >= open_trade.sl:
                    exit_price, reason = open_trade.sl, "sl"
                elif bar["low"] <= open_trade.tp:
                    exit_price, reason = open_trade.tp, "tp"

            if exit_price is not None:
                price_diff = (exit_price - open_trade.entry) * open_trade.side
                pnl = price_diff * open_trade.volume * contract
                open_trade.exit = exit_price
                open_trade.exit_time = time
                open_trade.pnl = pnl
                open_trade.reason = reason
                balance += pnl
                trades.append(open_trade)
                open_trade = None

        # 2) Execute pending signal at this bar's open
        if open_trade is None and pending_signal != Signal.HOLD:
            entry = float(bar["open"])
            side = int(pending_signal)
            sl, tp = risk.sl_tp(symbol, side, entry)
            volume = risk.compute_lot(balance, symbol)
            open_trade = Trade(
                entry_time=time, exit_time=None, side=side,
                entry=entry, exit=None, sl=sl, tp=tp, volume=volume,
            )
            pending_signal = Signal.HOLD

        # 3) Generate next signal from completed bars
        window = df.iloc[: i + 1]
        sig = strategy.generate_signal(window)
        if open_trade is None:
            pending_signal = sig
        # Ignore signals while in a trade (could add reverse-on-signal later)

        # 4) Mark-to-market equity
        if open_trade is not None:
            unrealized = (bar["close"] - open_trade.entry) * open_trade.side \
                * open_trade.volume * contract
            equity = balance + unrealized
        else:
            equity = balance
        equity_history.append((time, equity))

    # Close any dangling trade at the last close
    if open_trade is not None:
        last = df.iloc[-1]
        exit_price = float(last["close"])
        price_diff = (exit_price - open_trade.entry) * open_trade.side
        pnl = price_diff * open_trade.volume * contract
        open_trade.exit = exit_price
        open_trade.exit_time = last["time"] if "time" in df.columns else None
        open_trade.pnl = pnl
        open_trade.reason = "eod"
        balance += pnl
        trades.append(open_trade)

    times, equities = zip(*equity_history) if equity_history else ([], [])
    eq = pd.Series(equities, index=pd.Index(times, name="time"))
    return BacktestResult(trades=trades, equity_curve=eq, initial_balance=initial_balance)


# ---------- Synthetic data generator (for offline demo) ----------

def generate_synthetic_ohlcv(n: int = 1500, seed: int = 42,
                             start_price: float = 1.10) -> pd.DataFrame:
    """Generate plausible-looking EURUSD-style M15 bars for demo backtests."""
    rng = np.random.default_rng(seed)
    # Random walk with mild trend regime shifts
    returns = rng.normal(0, 0.0005, size=n)
    trend = np.sin(np.linspace(0, 6 * np.pi, n)) * 0.0003
    closes = start_price * np.exp(np.cumsum(returns + trend))

    highs = closes * (1 + rng.uniform(0, 0.0008, size=n))
    lows = closes * (1 - rng.uniform(0, 0.0008, size=n))
    opens = np.concatenate([[start_price], closes[:-1]])
    volume = rng.integers(50, 500, size=n)

    times = pd.date_range("2024-01-01", periods=n, freq="15min")
    return pd.DataFrame({
        "time": times,
        "open": opens.round(5),
        "high": np.maximum.reduce([opens, closes, highs]).round(5),
        "low": np.minimum.reduce([opens, closes, lows]).round(5),
        "close": closes.round(5),
        "volume": volume,
    })
