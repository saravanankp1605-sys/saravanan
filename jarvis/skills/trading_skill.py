"""Trading skills - integrate JARVIS with the existing forex bot in `bot/`."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

from .base import Skill, SkillParameter


def _load_cfg():
    """Lazy import to avoid hard-failing the assistant if pandas/yaml missing."""
    from bot.config import BotConfig
    return BotConfig.load("config.yaml")


class ShowTradingConfigSkill(Skill):
    name = "show_trading_config"
    description = "Show the current forex trading bot configuration (symbol, strategy, risk)."
    parameters = []

    def execute(self, **kwargs: Any) -> str:
        cfg = _load_cfg()
        return (
            f"Symbol:    {cfg.trading.symbol}\n"
            f"Timeframe: {cfg.trading.timeframe}\n"
            f"Strategy:  {cfg.strategy.name} (fast={cfg.strategy.fast_period}, "
            f"slow={cfg.strategy.slow_period})\n"
            f"Risk:      {cfg.risk.risk_per_trade * 100:.2f}% per trade | "
            f"SL={cfg.risk.stop_loss_pips} pips | TP={cfg.risk.take_profit_pips} pips"
        )

    def match(self, text: str) -> Optional[Dict[str, Any]]:
        t = text.lower()
        if ("show" in t or "what" in t) and ("trading config" in t or "bot config" in t):
            return {}
        if t.strip() in {"trading config", "bot config", "show config"}:
            return {}
        return None


class RunBacktestSkill(Skill):
    name = "run_backtest"
    description = (
        "Run a backtest of the configured trading strategy on synthetic data "
        "(or a CSV file) and return a summary of trades, win rate, and PnL."
    )
    parameters = [
        SkillParameter(
            "csv_path", "string",
            "Optional path to a CSV file with columns time,open,high,low,close,volume. "
            "If omitted, synthetic demo data is used.",
            required=False,
        ),
    ]

    def execute(self, **kwargs: Any) -> str:
        # Lazy imports so the assistant can boot without pandas installed.
        try:
            import pandas as pd
            from bot.backtester import generate_synthetic_ohlcv, run_backtest
            from bot.strategy import build_strategy
            from bot.risk import RiskManager
        except ImportError as e:
            return f"Trading dependencies not installed: {e}. Try: pip install -r requirements.txt"

        cfg = _load_cfg()
        csv_path = kwargs.get("csv_path")

        if csv_path and Path(csv_path).exists():
            df = pd.read_csv(csv_path, parse_dates=["time"])
            source = csv_path
        else:
            df = generate_synthetic_ohlcv()
            source = "synthetic data"

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

        result = run_backtest(df, strategy, risk, symbol=cfg.trading.symbol)
        s = result.summary()
        lines = [
            f"Backtest: {cfg.trading.symbol} | {len(df)} bars from {source}",
            f"  trades:        {s['trades']}",
            f"  win_rate:      {s['win_rate']:.2%}",
            f"  profit_factor: {s['profit_factor']}",
            f"  total_return:  {s['total_return']:.2%}",
            f"  final_balance: {s['final_balance']}",
            f"  max_drawdown:  {s['max_drawdown']:.2%}",
        ]
        return "\n".join(lines)

    def match(self, text: str) -> Optional[Dict[str, Any]]:
        t = text.lower()
        if "backtest" in t or "back test" in t or "run a back" in t:
            # Naive CSV-path extraction: look for a token ending in .csv
            csv_path = None
            for word in text.split():
                if word.lower().endswith(".csv"):
                    csv_path = word.strip("'\"")
                    break
            return {"csv_path": csv_path} if csv_path else {}
        return None
