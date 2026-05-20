"""Trade reporting: detailed trade log, P&L breakdown, win/loss ratio,
fees & commissions, and max drawdown.

Generates a human-readable report to stdout/log and exports a CSV trade log.
"""
from __future__ import annotations

import csv
import logging
from dataclasses import dataclass
from io import StringIO
from pathlib import Path
from typing import TYPE_CHECKING, List

import pandas as pd

if TYPE_CHECKING:
    from .backtester import BacktestResult, Trade

log = logging.getLogger("forex_bot")


@dataclass
class FeeConfig:
    """Transaction cost model.

    commission_per_lot: flat fee charged per lot per side (open + close).
        e.g. $7.0 means $7 when opening + $7 when closing = $14 round-trip per lot.
    spread_pips: simulated spread added to each entry (deducted from raw P&L).
        Set to 0 if spread is already baked into the OHLCV data.
    swap_per_night: overnight swap per lot per night (positive = cost). Ignored
        for now (intraday strategies close same day).
    """
    commission_per_lot: float = 7.0
    spread_pips: float = 0.0
    swap_per_night: float = 0.0


# ---------------------------------------------------------------------------
# Fee / commission calculation
# ---------------------------------------------------------------------------

def _compute_trade_commission(trade: "Trade", fee: FeeConfig) -> float:
    """Return total commission for a single round-trip trade."""
    return 2 * fee.commission_per_lot * trade.volume


def _compute_spread_cost(trade: "Trade", fee: FeeConfig,
                         pip_value: float, contract_size: float) -> float:
    """Simulated spread cost deducted from P&L."""
    return fee.spread_pips * pip_value * trade.volume * contract_size


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------

@dataclass
class ReportRow:
    """One row of the trade log."""
    trade_no: int
    side: str
    entry_time: str
    exit_time: str
    entry_price: float
    exit_price: float
    volume: float
    gross_pnl: float
    commission: float
    spread_cost: float
    net_pnl: float
    reason: str


def generate_report(
    result: "BacktestResult",
    fee: FeeConfig,
    symbol: str = "EURUSD",
    pip_value: float = 0.0001,
    contract_size: float = 100_000,
) -> str:
    """Generate a full text report and return it as a string.

    Includes:
      1. Trade Log (chronological)
      2. Profit & Loss (gross, fees, net)
      3. Win/Loss Ratio
      4. Fees & Commissions breakdown
      5. Max Drawdown
    """
    trades = result.trades
    rows: List[ReportRow] = []
    total_commission = 0.0
    total_spread_cost = 0.0
    total_gross_pnl = 0.0

    for i, t in enumerate(trades, start=1):
        comm = _compute_trade_commission(t, fee)
        spread = _compute_spread_cost(t, fee, pip_value, contract_size)
        net = t.pnl - comm - spread
        total_commission += comm
        total_spread_cost += spread
        total_gross_pnl += t.pnl
        rows.append(ReportRow(
            trade_no=i,
            side="BUY" if t.side > 0 else "SELL",
            entry_time=str(t.entry_time),
            exit_time=str(t.exit_time) if t.exit_time else "",
            entry_price=round(t.entry, 5),
            exit_price=round(t.exit, 5) if t.exit else 0.0,
            volume=t.volume,
            gross_pnl=round(t.pnl, 2),
            commission=round(comm, 2),
            spread_cost=round(spread, 2),
            net_pnl=round(net, 2),
            reason=t.reason,
        ))

    total_net_pnl = total_gross_pnl - total_commission - total_spread_cost
    total_fees = total_commission + total_spread_cost

    # Win / loss using NET P&L (after fees)
    net_pnls = [r.net_pnl for r in rows]
    wins = [p for p in net_pnls if p > 0]
    losses = [p for p in net_pnls if p <= 0]
    n = len(rows)
    win_count = len(wins)
    loss_count = len(losses)
    win_rate = (win_count / n) if n else 0.0
    avg_win = (sum(wins) / win_count) if win_count else 0.0
    avg_loss = (sum(losses) / loss_count) if loss_count else 0.0
    profit_factor = (sum(wins) / -sum(losses)) if losses and sum(losses) != 0 else float("inf")

    # Max drawdown from equity curve
    equity = result.equity_curve
    if len(equity):
        peak = equity.cummax()
        dd = (equity - peak) / peak
        max_dd = float(dd.min())
        max_dd_abs = float((equity - peak).min())
    else:
        max_dd = 0.0
        max_dd_abs = 0.0

    # Build report string
    lines: list[str] = []
    sep = "=" * 70

    lines.append(sep)
    lines.append(f"  BACKTEST REPORT — {symbol}")
    lines.append(sep)
    lines.append("")

    # --- Section 1: Trade Log ---
    lines.append("1. TRADE LOG (chronological)")
    lines.append("-" * 70)
    lines.append(
        f"{'#':>4} {'Side':<5} {'Entry Time':<20} {'Exit Time':<20} "
        f"{'Entry':>9} {'Exit':>9} {'Vol':>5} {'Gross':>8} {'Fees':>7} "
        f"{'Net':>8} {'Reason':<6}"
    )
    lines.append("-" * 70)
    for r in rows:
        lines.append(
            f"{r.trade_no:>4} {r.side:<5} {r.entry_time:<20} {r.exit_time:<20} "
            f"{r.entry_price:>9.5f} {r.exit_price:>9.5f} {r.volume:>5.2f} "
            f"{r.gross_pnl:>+8.2f} {r.commission + r.spread_cost:>7.2f} "
            f"{r.net_pnl:>+8.2f} {r.reason:<6}"
        )
    lines.append("")

    # --- Section 2: Profit & Loss ---
    lines.append("2. PROFIT & LOSS")
    lines.append("-" * 40)
    lines.append(f"  Initial balance:    ${result.initial_balance:>12,.2f}")
    lines.append(f"  Gross P&L:          ${total_gross_pnl:>+12,.2f}")
    lines.append(f"  Total fees:         ${total_fees:>12,.2f}")
    lines.append(f"  Net P&L:            ${total_net_pnl:>+12,.2f}")
    lines.append(f"  Final balance:      ${result.initial_balance + total_net_pnl:>12,.2f}")
    lines.append(f"  Return:             {(total_net_pnl / result.initial_balance) * 100:>+10.2f}%")
    lines.append("")

    # --- Section 3: Win/Loss Ratio ---
    lines.append("3. WIN / LOSS RATIO")
    lines.append("-" * 40)
    lines.append(f"  Total trades:       {n}")
    lines.append(f"  Winning trades:     {win_count}  ({win_rate * 100:.1f}%)")
    lines.append(f"  Losing trades:      {loss_count}  ({(1 - win_rate) * 100:.1f}%)")
    lines.append(f"  Average win:        ${avg_win:>+10,.2f}")
    lines.append(f"  Average loss:       ${avg_loss:>+10,.2f}")
    lines.append(f"  Profit factor:      {profit_factor:.3f}")
    if avg_loss != 0:
        lines.append(f"  Reward/risk ratio:  {abs(avg_win / avg_loss):.2f}")
    lines.append("")

    # --- Section 4: Fees & Commissions ---
    lines.append("4. FEES & COMMISSIONS")
    lines.append("-" * 40)
    lines.append(f"  Commission/lot:     ${fee.commission_per_lot:.2f} per side")
    lines.append(f"  Spread (simulated): {fee.spread_pips:.1f} pips")
    lines.append(f"  Total commissions:  ${total_commission:>10,.2f}")
    lines.append(f"  Total spread cost:  ${total_spread_cost:>10,.2f}")
    lines.append(f"  Total fees:         ${total_fees:>10,.2f}")
    lines.append(f"  Fees as % of gross: {(total_fees / abs(total_gross_pnl) * 100) if total_gross_pnl else 0:.1f}%")
    lines.append("")

    # --- Section 5: Max Drawdown ---
    lines.append("5. MAX DRAWDOWN")
    lines.append("-" * 40)
    lines.append(f"  Max drawdown (%):   {max_dd * 100:.2f}%")
    lines.append(f"  Max drawdown ($):   ${max_dd_abs:>10,.2f}")
    lines.append("")
    lines.append(sep)

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CSV export
# ---------------------------------------------------------------------------

def export_trade_log_csv(result: "BacktestResult", fee: FeeConfig,
                         path: str | Path,
                         symbol: str = "EURUSD",
                         pip_value: float = 0.0001,
                         contract_size: float = 100_000) -> None:
    """Write the trade log to a CSV file."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "trade_no", "side", "entry_time", "exit_time",
            "entry_price", "exit_price", "volume",
            "gross_pnl", "commission", "spread_cost", "net_pnl", "reason",
        ])
        for i, t in enumerate(result.trades, start=1):
            comm = _compute_trade_commission(t, fee)
            spread = _compute_spread_cost(t, fee, pip_value, contract_size)
            net = t.pnl - comm - spread
            writer.writerow([
                i,
                "BUY" if t.side > 0 else "SELL",
                str(t.entry_time),
                str(t.exit_time) if t.exit_time else "",
                round(t.entry, 5),
                round(t.exit, 5) if t.exit else "",
                t.volume,
                round(t.pnl, 2),
                round(comm, 2),
                round(spread, 2),
                round(net, 2),
                t.reason,
            ])
    log.info("Trade log CSV saved to %s", path)
