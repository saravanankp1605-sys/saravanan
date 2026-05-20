"""Run a backtest using either synthetic data or a CSV file.

Usage:
    python run_backtest.py                 # synthetic demo data
    python run_backtest.py data/eurusd.csv # CSV with columns: time,open,high,low,close,volume
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

from bot.backtester import generate_synthetic_ohlcv, run_backtest
from bot.config import BotConfig
from bot.logger import setup_logger
from bot.risk import RiskManager
from bot.strategy import build_strategy


def main(csv_path: str | None = None) -> int:
    cfg = BotConfig.load("config.yaml")
    log = setup_logger("forex_bot", cfg.logging.level, cfg.logging.file)

    if csv_path:
        log.info("Loading historical data from %s", csv_path)
        df = pd.read_csv(csv_path, parse_dates=["time"])
    else:
        log.info("No CSV given, generating synthetic OHLCV data for demo")
        df = generate_synthetic_ohlcv()

    strategy = build_strategy(
        cfg.strategy.name,
        fast_period=cfg.strategy.fast_period,
        slow_period=cfg.strategy.slow_period,
    )
    risk = RiskManager(
        risk_per_trade=cfg.risk.risk_per_trade,
        stop_loss_pips=cfg.risk.stop_loss_pips,
        take_profit_pips=cfg.risk.take_profit_pips,
        dynamic_sizing=cfg.risk.dynamic_sizing,
        fixed_lot=cfg.trading.lot_size,
    )

    log.info("Running backtest: symbol=%s strategy=%s bars=%d",
             cfg.trading.symbol, cfg.strategy.name, len(df))
    result = run_backtest(df, strategy, risk, symbol=cfg.trading.symbol)

    summary = result.summary()
    log.info("=" * 50)
    log.info("Backtest summary")
    for k, v in summary.items():
        log.info("  %-15s %s", k, v)
    log.info("=" * 50)

    # Save equity curve for later inspection
    out_dir = Path("logs")
    out_dir.mkdir(exist_ok=True)
    result.equity_curve.to_csv(out_dir / "equity_curve.csv", header=["equity"])
    log.info("Equity curve saved to logs/equity_curve.csv")
    return 0


if __name__ == "__main__":
    csv = sys.argv[1] if len(sys.argv) > 1 else None
    sys.exit(main(csv))
