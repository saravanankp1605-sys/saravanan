"""Live (or demo) trading runner.

Connects to a MetaTrader 5 terminal, polls for new bars, runs the strategy,
and places market orders with stop-loss / take-profit.

WARNING: Requires Windows + MT5 terminal + MetaTrader5 Python package.
Always run on a DEMO account first.
"""
from __future__ import annotations

import signal as os_signal
import sys
import time
from datetime import datetime, timezone

from bot.broker import MT5Broker
from bot.config import BotConfig
from bot.logger import setup_logger
from bot.risk import RiskManager
from bot.strategy import Signal, build_strategy


_TIMEFRAME_SECONDS = {
    "M1": 60, "M5": 300, "M15": 900, "M30": 1800,
    "H1": 3600, "H4": 14_400, "D1": 86_400,
}


_running = True


def _stop(signum, frame):  # noqa: ARG001
    global _running
    _running = False


def main() -> int:
    cfg = BotConfig.load("config.yaml")
    log = setup_logger("forex_bot", cfg.logging.level, cfg.logging.file)

    os_signal.signal(os_signal.SIGINT, _stop)
    os_signal.signal(os_signal.SIGTERM, _stop)

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

    broker = MT5Broker(cfg)
    if not broker.connect():
        log.error("Could not connect to MT5. Aborting.")
        return 1

    symbol = cfg.trading.symbol
    timeframe = cfg.trading.timeframe
    poll_seconds = max(5, _TIMEFRAME_SECONDS.get(timeframe.upper(), 60) // 6)

    log.info("Bot started | symbol=%s timeframe=%s strategy=%s",
             symbol, timeframe, cfg.strategy.name)

    last_bar_time = None
    try:
        while _running:
            df = broker.get_rates(symbol, timeframe, count=max(200, cfg.strategy.slow_period * 4))
            if df.empty:
                log.warning("No bars returned, retrying...")
                time.sleep(poll_seconds)
                continue

            # Only act on a NEW closed bar
            current_bar_time = df["time"].iloc[-1]
            if last_bar_time is None:
                last_bar_time = current_bar_time
                log.info("Initialised at bar %s", current_bar_time)
                time.sleep(poll_seconds)
                continue

            if current_bar_time == last_bar_time:
                time.sleep(poll_seconds)
                continue

            last_bar_time = current_bar_time

            # Use only fully-closed bars for signal generation
            closed = df.iloc[:-1]
            sig = strategy.generate_signal(closed)
            log.info("New bar %s | signal=%s", current_bar_time, sig.name)

            open_positions = broker.positions(symbol=symbol)
            if sig == Signal.HOLD:
                continue

            if len(open_positions) >= cfg.risk.max_open_positions:
                log.info("Max positions open (%d), skipping signal", len(open_positions))
                continue

            tick = broker.symbol_tick(symbol)
            if tick is None:
                log.warning("No tick for %s", symbol)
                continue
            entry = tick.ask if sig == Signal.BUY else tick.bid
            sl, tp = risk.sl_tp(symbol, int(sig), entry)
            volume = risk.compute_lot(broker.account_balance(), symbol)
            broker.open_market(symbol, int(sig), volume, sl, tp)

            time.sleep(poll_seconds)
    finally:
        broker.disconnect()
        log.info("Bot stopped at %s", datetime.now(timezone.utc).isoformat())
    return 0


if __name__ == "__main__":
    sys.exit(main())
