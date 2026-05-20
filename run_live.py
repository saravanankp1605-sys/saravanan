"""Live (or demo) trading runner.

Connects to a MetaTrader 5 terminal, polls for new bars, runs the strategy,
places market orders with stop-loss / take-profit, and (optionally) sends
Telegram notifications on trade events.

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
from bot.notifier import build_notifier
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
    notifier = build_notifier(cfg)

    os_signal.signal(os_signal.SIGINT, _stop)
    os_signal.signal(os_signal.SIGTERM, _stop)

    strategy = build_strategy(cfg.strategy.name, **cfg.strategy.params)
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
        notifier.info("Forex bot failed to connect to MT5.")
        return 1

    symbol = cfg.trading.symbol
    timeframe = cfg.trading.timeframe
    poll_seconds = max(5, _TIMEFRAME_SECONDS.get(timeframe.upper(), 60) // 6)

    log.info("Bot started | symbol=%s timeframe=%s strategy=%s",
             symbol, timeframe, cfg.strategy.name)
    notifier.info(
        f"Forex bot *started*\n"
        f"Symbol: `{symbol}`  TF: `{timeframe}`  Strategy: `{cfg.strategy.name}`"
    )

    last_bar_time = None
    known_tickets: set[int] = set()

    try:
        while _running:
            df = broker.get_rates(symbol, timeframe,
                                  count=max(200, 4 * max(
                                      cfg.strategy.params.get("slow_period", 50),
                                      cfg.strategy.params.get("slow", 26),
                                      cfg.strategy.params.get("period", 20),
                                  )))
            if df.empty:
                log.warning("No bars returned, retrying...")
                time.sleep(poll_seconds)
                continue

            current_bar_time = df["time"].iloc[-1]
            if last_bar_time is None:
                last_bar_time = current_bar_time
                # also seed known tickets with whatever is already open
                known_tickets = {p.ticket for p in broker.positions(symbol=symbol)}
                log.info("Initialised at bar %s", current_bar_time)
                time.sleep(poll_seconds)
                continue

            # Detect closed positions (notify)
            current_tickets = {p.ticket for p in broker.positions(symbol=symbol)}
            for closed_ticket in known_tickets - current_tickets:
                # We don't have full info post-close; send a generic note.
                notifier.info(f"Position `{closed_ticket}` closed on `{symbol}`.")
            known_tickets = current_tickets

            if current_bar_time == last_bar_time:
                time.sleep(poll_seconds)
                continue
            last_bar_time = current_bar_time

            # Use only fully-closed bars for signal generation.
            closed = df.iloc[:-1]
            sig = strategy.generate_signal(closed)
            log.info("New bar %s | signal=%s", current_bar_time, sig.name)

            open_positions = broker.positions(symbol=symbol)
            if sig == Signal.HOLD:
                continue
            if len(open_positions) >= cfg.risk.max_open_positions:
                log.info("Max positions open (%d), skipping", len(open_positions))
                continue

            tick = broker.symbol_tick(symbol)
            if tick is None:
                log.warning("No tick for %s", symbol)
                continue
            entry = tick.ask if sig == Signal.BUY else tick.bid
            sl, tp = risk.sl_tp(symbol, int(sig), entry)
            volume = risk.compute_lot(broker.account_balance(), symbol)
            result = broker.open_market(symbol, int(sig), volume, sl, tp)
            if result is not None:
                ticket = getattr(result, "order", None)
                notifier.trade_opened(symbol, int(sig), volume, entry, sl, tp, ticket)
                if ticket is not None:
                    known_tickets.add(ticket)

            time.sleep(poll_seconds)
    finally:
        broker.disconnect()
        log.info("Bot stopped at %s", datetime.now(timezone.utc).isoformat())
        notifier.info("Forex bot *stopped*.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
