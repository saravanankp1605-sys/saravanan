# Forex Trading Bot (MetaTrader 5)

A Python forex trading bot that connects to MetaTrader 5, runs configurable
strategies (MA-crossover, RSI, MACD, Donchian breakout) with proper risk
management, supports backtesting on real historical data (Yahoo Finance, MT5,
or your own CSV), and can send Telegram notifications on trade events.

> **Trade at your own risk.** This is educational software. Always run on a
> **demo account** first. Past performance does not guarantee future results.

## Project structure

```
.
├── bot/
│   ├── config.py        # YAML config loader (typed dataclasses)
│   ├── logger.py        # console + file logging
│   ├── strategy.py      # MA-crossover / RSI / MACD / breakout
│   ├── risk.py          # position sizing, stop-loss, take-profit
│   ├── broker.py        # MetaTrader5 connector (lazy import)
│   ├── data.py          # OHLCV loaders: synthetic / CSV / yfinance / MT5
│   ├── backtester.py    # bar-by-bar backtester
│   └── notifier.py      # Telegram notifications (stdlib only)
├── run_backtest.py      # CLI: backtest with any data source / strategy
├── run_live.py          # CLI: live/demo bot against MT5
├── config.yaml          # all settings in one place
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

### 2. Run a backtest

```bash
# Built-in synthetic data (no internet required)
python run_backtest.py

# Real EURUSD data from Yahoo Finance
python run_backtest.py --source yfinance --symbol EURUSD \
    --start 2024-01-01 --end 2024-06-30 --interval 15m

# Your own CSV (columns: time,open,high,low,close,volume)
python run_backtest.py --source csv --csv data/eurusd_m15.csv

# Try a different strategy without editing config
python run_backtest.py --strategy rsi
python run_backtest.py --strategy macd
python run_backtest.py --strategy breakout
```

Sample output:

```
trades          42
win_rate        0.4524
profit_factor   1.312
total_return    0.0834
final_balance   10834.10
max_drawdown   -0.0421
```

### 3. Run the bot live (Windows + MT5 required)

1. Install the [MetaTrader 5 terminal](https://www.metatrader5.com/) and log
   into a **demo account** (your broker provides one).
2. Edit `config.yaml`:
   - `mt5.login`, `mt5.password`, `mt5.server` — your demo credentials
   - `trading.symbol`, `trading.timeframe`
   - `strategy.name` + `strategy.params`
   - `risk.*` — risk per trade, SL/TP in pips
3. Run it: `python run_live.py`. Stop with `Ctrl+C`.

## Strategies

Pick one with `strategy.name` in `config.yaml` (or `--strategy` on the CLI):

| Name           | Logic                                              | Params |
|----------------|----------------------------------------------------|--------|
| `ma_crossover` | BUY/SELL when fast SMA crosses slow SMA            | `fast_period`, `slow_period` |
| `rsi`          | BUY when RSI exits oversold, SELL when exits OB    | `period`, `overbought`, `oversold` |
| `macd`         | MACD line crosses signal line                      | `fast`, `slow`, `signal` |
| `breakout`     | Donchian channel breakout above/below N-bar HH/LL  | `period` |

Add a new strategy by writing a class with `attach_indicators(df)` and
`generate_signal(df) -> Signal` in `bot/strategy.py`, then register it in
`build_strategy()`.

## Telegram notifications (optional)

1. Talk to **@BotFather** on Telegram, run `/newbot`, copy the token.
2. Send any message to your new bot.
3. Visit `https://api.telegram.org/bot<TOKEN>/getUpdates` and read your `chat.id`.
4. In `config.yaml`:
   ```yaml
   notifications:
     telegram:
       enabled: true
       bot_token: "123456:ABC..."
       chat_id: "987654321"
   ```

You'll get messages on bot start/stop, every trade open, and every position close.
Notifications use only the Python stdlib — no extra packages.

## Configuration reference

See [`config.yaml`](./config.yaml) — every field is documented inline.

Key fields:
- **`risk.risk_per_trade`** — fraction of balance risked per trade. Position size
  is computed so that hitting the stop-loss costs exactly this amount.
- **`risk.stop_loss_pips` / `take_profit_pips`** — distances in pips. JPY pairs
  use 0.01 per pip; everything else uses 0.0001.

## Disclaimer

Forex trading carries substantial risk of loss. This software is provided as-is
for educational purposes only. The author is not responsible for any financial
losses incurred from using it.
