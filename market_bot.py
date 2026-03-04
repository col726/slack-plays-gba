import time
from datetime import datetime
from zoneinfo import ZoneInfo

import yfinance as yf

from base_bot import BaseBotAdapter
from config import MARKET_POLL_INTERVAL
from emulator import Emulator
STRONG_MOVE_PCT = 1.0        # % move to trigger a / b
FLAT_THRESHOLD_PCT = 0.05    # % below which a move is considered flat
VOLUME_SPIKE_MULTIPLIER = 2.0  # multiple of avg volume to trigger start

MARKET_PRIMARY = "SPY"
MARKET_SECONDARY = "AMZN"
CRYPTO_PRIMARY = "BTC-USD"
CRYPTO_SECONDARY = "ETH-USD"


def _is_market_open() -> bool:
    now = datetime.now(ZoneInfo("America/New_York"))
    if now.weekday() >= 5:
        return False
    open_time = now.replace(hour=9, minute=30, second=0, microsecond=0)
    close_time = now.replace(hour=16, minute=0, second=0, microsecond=0)
    return open_time <= now < close_time


def _fetch(ticker_sym: str) -> tuple[float, float, float]:
    """Returns (current_price, current_volume, avg_recent_volume)."""
    hist = yf.Ticker(ticker_sym).history(period="1d", interval="1m")
    if hist.empty:
        raise ValueError(f"No data for {ticker_sym}")
    price = float(hist["Close"].iloc[-1])
    vol = float(hist["Volume"].iloc[-1])
    avg_vol = float(hist["Volume"].iloc[-11:-1].mean()) if len(hist) > 10 else vol
    return price, vol, avg_vol


class MarketBot(BaseBotAdapter):
    def __init__(self, emulator: Emulator):
        self._emulator = emulator
        self._running = False
        self._last_primary_price: float | None = None
        self._last_secondary_price: float | None = None
        self._prev_primary_delta: float = 0.0
        self._last_mode: str | None = None

    def _process_tick(self):
        market_open = _is_market_open()
        mode = "stocks" if market_open else "crypto"
        primary_sym = MARKET_PRIMARY if market_open else CRYPTO_PRIMARY
        secondary_sym = MARKET_SECONDARY if market_open else CRYPTO_SECONDARY

        # Reset price history on mode switch to avoid cross-comparing stock vs crypto prices
        if mode != self._last_mode:
            print(f"[market] Mode → {mode} (primary: {primary_sym}, secondary: {secondary_sym})")
            self._last_primary_price = None
            self._last_secondary_price = None
            self._prev_primary_delta = 0.0
            self._last_mode = mode

        try:
            primary_price, primary_vol, avg_vol = _fetch(primary_sym)
            secondary_price, _, _ = _fetch(secondary_sym)
        except Exception as e:
            print(f"[market] Failed to fetch prices: {e}")
            return

        commands: list[tuple[str, str]] = []  # (command, source_label)

        if self._last_primary_price is not None:
            pct = (primary_price - self._last_primary_price) / self._last_primary_price * 100

            if pct > FLAT_THRESHOLD_PCT:
                commands.append(("up", primary_sym))
                if pct >= STRONG_MOVE_PCT:
                    commands.append(("a", primary_sym))
            elif pct < -FLAT_THRESHOLD_PCT:
                commands.append(("down", primary_sym))
                if pct <= -STRONG_MOVE_PCT:
                    commands.append(("b", primary_sym))

            # Reversal: delta flipped sign since last poll
            if (self._prev_primary_delta > 0 and pct < 0) or \
               (self._prev_primary_delta < 0 and pct > 0):
                commands.append(("select", primary_sym))

            # Volume spike
            if avg_vol > 0 and primary_vol >= avg_vol * VOLUME_SPIKE_MULTIPLIER:
                commands.append(("start", primary_sym))

            self._prev_primary_delta = pct
            print(f"[market] {primary_sym}: {primary_price:.2f} ({pct:+.2f}%) "
                  f"vol: {primary_vol:.0f} (avg: {avg_vol:.0f}) | "
                  f"commands: {[c for c, _ in commands] or 'none'}")
        else:
            print(f"[market] First {mode} tick — "
                  f"{primary_sym}: {primary_price:.2f}, {secondary_sym}: {secondary_price:.2f}")

        if self._last_secondary_price is not None:
            sec_pct = (secondary_price - self._last_secondary_price) / self._last_secondary_price * 100
            if sec_pct > FLAT_THRESHOLD_PCT:
                commands.append(("right", secondary_sym))
            elif sec_pct < -FLAT_THRESHOLD_PCT:
                commands.append(("left", secondary_sym))

        for cmd, label in commands:
            self._emulator.queue_command(cmd)
            self._emulator.set_last_input("Market", label, cmd)

        self._last_primary_price = primary_price
        self._last_secondary_price = secondary_price

    def start(self) -> None:
        print("[market] Starting market bot...")
        self._running = True
        self._process_tick()
        while self._running:
            time.sleep(MARKET_POLL_INTERVAL)
            if self._running:
                self._process_tick()

    def stop(self) -> None:
        print("[market] Stopping...")
        self._running = False
