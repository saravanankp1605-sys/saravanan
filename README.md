# Forex Trading Bot (MetaTrader 5)

A Python forex trading bot that connects to MetaTrader 5, executes a moving-average
crossover strategy with proper risk management, and includes a backtester so you can
validate the strategy on historical data before going live.

> **Trade at your own risk.** This is educational software. Always run on a **demo
> account** first. Past performance does not guarantee future results.

## Project structure

```
.
├── bot/
│   ├── __init__.py
│   ├── config.py        # YAML config loader (typed dataclasses)
│   ├── logger.py        # console + file logging
│   ├── strategy.py      # MA-crossover strategy + Signal enum
│   ├── risk.py          # position sizing, stop-loss, take-profit
│   ├── broker.py        # MetaTrader5 connector (lazy import)
│   └── backtester.py    # bar-by-bar backtester + synthetic data
├── run_backtest.py      # CLI: run backtest on synthetic data or a CSV
├── run_live.py          # CLI: run the live/demo bot against MT5
├── config.yaml          # bot configuration
└── requirements.txt
```

## Quick start

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

For live/demo trading you also need (Windows only):

```bash
pip install MetaTrader5
```

### 2. Run a backtest (works on any OS)

```bash
# Uses built-in synthetic EURUSD-style M15 data
python run_backtest.py

# Or your own CSV: columns time,open,high,low,close,volume
python run_backtest.py data/eurusd_m15.csv
```

You'll get a summary like:

```
trades          42
win_rate        0.4524
profit_factor   1.312
total_return    0.0834
final_balance   10834.10
max_drawdown   -0.0421
```

### 3. Run the bot live (Windows + MT5 required)

1. Install the [MetaTrader 5 terminal](https://www.metatrader5.com/) and log in to a
   **demo account** (your broker should provide one).
2. Edit `config.yaml`:
   - `mt5.login`, `mt5.password`, `mt5.server` — your MT5 demo credentials
   - `trading.symbol`, `trading.timeframe` — what to trade
   - `strategy.fast_period`, `strategy.slow_period` — strategy parameters
   - `risk.*` — risk per trade, SL/TP in pips
3. Run it:

   ```bash
   python run_live.py
   ```

4. Stop with Ctrl+C.

## Configuration reference

See [`config.yaml`](./config.yaml) — every field is documented inline.

Key fields:

- **`strategy.fast_period` / `slow_period`** — SMA windows. The bot goes long when
  `fast` crosses above `slow`, short when it crosses below.
- **`risk.risk_per_trade`** — fraction of account balance risked on each trade
  (`0.01` = 1%). Position size is computed so that hitting the stop-loss costs
  exactly this amount.
- **`risk.stop_loss_pips` / `take_profit_pips`** — distances in pips. JPY pairs use
  0.01 per pip; everything else uses 0.0001.

## Extending the bot

- **New strategy?** Add a class with `attach_indicators(df)` and
  `generate_signal(df) -> Signal` in `bot/strategy.py`, then register it in
  `build_strategy()`.
- **New broker?** Add a module alongside `bot/broker.py` exposing the same methods
  (`connect`, `get_rates`, `open_market`, `positions`, `close_position`,
  `account_balance`, `symbol_tick`).
- **Notifications?** Hook into `bot/logger.py` (e.g., a Telegram handler).

## Disclaimer

Forex trading carries substantial risk of loss. This software is provided as-is for
educational purposes only. The author is not responsible for any financial losses
incurred from using it.
