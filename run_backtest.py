"""Run a backtest using the configured data source.

Usage:
    python run_backtest.py                 # uses data.source from config.yaml
    python run_backtest.py --source csv --csv data/eurusd.csv
    python run_backtest.py --source yfinance --symbol EURUSD --start 2024-01-01 --end 2024-06-30 --interval 15m
    python run_backtest.py --strategy rsi  # override strategy name from config

CSV format: time,open,high,low,close,volume  (case-insensitive headers)
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from bot.backtester import run_backtest
from bot.config import BotConfig
from bot.data import load_data
from bot.logger import setup_logger
from bot.risk import RiskManager
from bot.strategy import build_strategy


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run a forex strategy backtest.")
    p.add_argument("--config", default="config.yaml")
    p.add_argument("--source", choices=["synthetic", "csv", "yfinance", "mt5"],
                   help="Override data.source from config")
    p.add_argument("--csv", help="Override data.csv_path")
    p.add_argument("--symbol", help="Override yfinance/mt5 symbol")
    p.add_argument("--start", help="Override data.start_date (YYYY-MM-DD)")
    p.add_argument("--end", help="Override data.end_date (YYYY-MM-DD)")
    p.add_argument("--interval", help="Override yfinance interval (e.g. 15m, 1h)")
    p.add_argument("--strategy", help="Override strategy.name")
    p.add_argument("--balance", type=float, default=10_000.0,
                   help="Initial balance for the backtest (default 10000)")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    cfg = BotConfig.load(args.config)
    log = setup_logger("forex_bot", cfg.logging.level, cfg.logging.file)

    source = args.source or cfg.data.source
    log.info("Loading data | source=%s", source)
    df = load_data(
        source,
        csv_path=args.csv or cfg.data.csv_path,
        yfinance_symbol=args.symbol or cfg.data.yfinance_symbol,
        mt5_symbol=args.symbol or cfg.trading.symbol,
        timeframe=cfg.trading.timeframe,
        start=args.start or cfg.data.start_date or None,
        end=args.end or cfg.data.end_date or None,
        interval=args.interval or cfg.data.interval,
    )
    log.info("Loaded %d bars | %s -> %s", len(df),
             df["time"].iloc[0], df["time"].iloc[-1])

    strat_name = args.strategy or cfg.strategy.name
    strategy = build_strategy(strat_name, **cfg.strategy.params)
    risk = RiskManager(
        risk_per_trade=cfg.risk.risk_per_trade,
        stop_loss_pips=cfg.risk.stop_loss_pips,
        take_profit_pips=cfg.risk.take_profit_pips,
        dynamic_sizing=cfg.risk.dynamic_sizing,
        fixed_lot=cfg.trading.lot_size,
    )

    log.info("Running backtest | symbol=%s strategy=%s",
             cfg.trading.symbol, strat_name)
    result = run_backtest(df, strategy, risk,
                          symbol=cfg.trading.symbol,
                          initial_balance=args.balance)

    summary = result.summary()
    log.info("=" * 50)
    log.info("Backtest summary (%s, %s)", strat_name, cfg.trading.symbol)
    for k, v in summary.items():
        log.info("  %-15s %s", k, v)
    log.info("=" * 50)

    out_dir = Path("logs")
    out_dir.mkdir(exist_ok=True)
    result.equity_curve.to_csv(out_dir / "equity_curve.csv", header=["equity"])
    log.info("Equity curve saved to logs/equity_curve.csv")
    return 0


if __name__ == "__main__":
    sys.exit(main())
