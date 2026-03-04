import time

import requests

from base_bot import BaseBotAdapter
from config import WEATHER_API_KEY, WEATHER_CITY, WEATHER_POLL_INTERVAL
from emulator import Emulator

API_URL = "https://api.openweathermap.org/data/2.5/weather"

TEMP_FLAT_THRESHOLD = 0.5   # °F change below which temp is considered flat
WIND_FLAT_THRESHOLD = 0.5   # mph change below which wind is considered flat


def _fetch_weather() -> dict:
    resp = requests.get(API_URL, params={
        "q": WEATHER_CITY,
        "appid": WEATHER_API_KEY,
        "units": "imperial",
    }, timeout=10)
    resp.raise_for_status()
    return resp.json()


def _condition_id(data: dict) -> int:
    return data["weather"][0]["id"]


class WeatherBot(BaseBotAdapter):
    def __init__(self, emulator: Emulator):
        self._emulator = emulator
        self._running = False
        self._last_temp: float | None = None
        self._last_wind: float | None = None

    def _process_tick(self):
        try:
            data = _fetch_weather()
        except Exception as e:
            print(f"[weather] Failed to fetch weather: {e}")
            return

        temp = float(data["main"]["temp"])
        wind = float(data["wind"]["speed"])
        condition = _condition_id(data)
        description = data["weather"][0]["description"]

        print(f"[weather] {WEATHER_CITY}: {temp:.1f}°F, wind {wind:.1f}mph, condition {condition} ({description})")

        commands: list[tuple[str, str]] = []

        # Temperature → up / down
        if self._last_temp is not None:
            delta = temp - self._last_temp
            if delta > TEMP_FLAT_THRESHOLD:
                commands.append(("up", f"{temp:.1f}°F ↑"))
            elif delta < -TEMP_FLAT_THRESHOLD:
                commands.append(("down", f"{temp:.1f}°F ↓"))

        # Wind speed → right (faster) / left (slower)
        if self._last_wind is not None:
            delta = wind - self._last_wind
            if delta > WIND_FLAT_THRESHOLD:
                commands.append(("right", f"wind {wind:.1f}mph ↑"))
            elif delta < -WIND_FLAT_THRESHOLD:
                commands.append(("left", f"wind {wind:.1f}mph ↓"))

        # Condition codes: 2xx=thunderstorm, 3xx/5xx=rain, 6xx=snow, 701/741=mist/fog
        if 200 <= condition < 300:
            commands.append(("start", "⛈ thunderstorm"))
        elif 300 <= condition < 600:
            commands.append(("a", "🌧 rain"))
        elif 600 <= condition < 700:
            commands.append(("b", "🌨 snow"))
        elif condition in (701, 721, 741):
            commands.append(("select", "🌫 fog"))

        for cmd, label in commands:
            self._emulator.queue_command(cmd)
            self._emulator.set_last_input("Weather", label, cmd)

        print(f"[weather] Commands: {[c for c, _ in commands] or 'none'}")

        self._last_temp = temp
        self._last_wind = wind

    def start(self) -> None:
        print(f"[weather] Starting weather bot for {WEATHER_CITY}...")
        self._running = True
        self._process_tick()
        while self._running:
            time.sleep(WEATHER_POLL_INTERVAL)
            if self._running:
                self._process_tick()

    def stop(self) -> None:
        print("[weather] Stopping...")
        self._running = False
