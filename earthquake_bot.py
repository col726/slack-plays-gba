import time
from datetime import datetime, timezone, timedelta

import requests

from base_bot import BaseBotAdapter
from config import EARTHQUAKE_POLL_INTERVAL, EARTHQUAKE_MIN_MAGNITUDE
from emulator import Emulator

USGS_URL = "https://earthquake.usgs.gov/fdsnws/event/1/query"
SWARM_THRESHOLD = 3  # quakes in one window to trigger select


def _fetch_earthquakes(since: datetime, min_magnitude: float) -> list[dict]:
    resp = requests.get(USGS_URL, params={
        "format": "geojson",
        "starttime": since.strftime("%Y-%m-%dT%H:%M:%S"),
        "minmagnitude": min_magnitude,
        "orderby": "time",
    }, timeout=15)
    resp.raise_for_status()
    return resp.json().get("features", [])


class EarthquakeBot(BaseBotAdapter):
    def __init__(self, emulator: Emulator):
        self._emulator = emulator
        self._running = False
        self._last_poll_time: datetime = datetime.now(timezone.utc) - timedelta(seconds=EARTHQUAKE_POLL_INTERVAL)

    def _process_tick(self):
        since = self._last_poll_time
        self._last_poll_time = datetime.now(timezone.utc)

        try:
            quakes = _fetch_earthquakes(since, EARTHQUAKE_MIN_MAGNITUDE)
        except Exception as e:
            print(f"[earthquake] Failed to fetch data: {e}")
            return

        if not quakes:
            print(f"[earthquake] No earthquakes since last poll")
            return

        print(f"[earthquake] {len(quakes)} earthquake(s) since last poll")

        for quake in quakes:
            props = quake["properties"]
            coords = quake["geometry"]["coordinates"]  # [longitude, latitude, depth]
            mag = props.get("mag") or 0.0
            place = props.get("place", "unknown location")
            lon, lat = coords[0], coords[1]

            commands: list[tuple[str, str]] = []
            label = f"M{mag:.1f} {place}"

            # Directional: latitude → up/down, longitude → left/right
            commands.append(("up" if lat >= 0 else "down", label))
            commands.append(("right" if lon >= 0 else "left", label))

            # Magnitude thresholds
            if mag >= 4.0:
                commands.append(("a", label))
            if mag >= 5.0:
                commands.append(("b", label))
            if mag >= 6.0:
                commands.append(("start", label))

            for cmd, lbl in commands:
                self._emulator.queue_command(cmd)
                self._emulator.set_last_input("Quake", lbl, cmd)

            print(f"[earthquake] M{mag:.1f} at {place} ({lat:.2f}, {lon:.2f}) → {[c for c, _ in commands]}")

        # Seismic swarm
        if len(quakes) >= SWARM_THRESHOLD:
            self._emulator.queue_command("select")
            self._emulator.set_last_input("Quake", f"swarm ({len(quakes)} quakes)", "select")
            print(f"[earthquake] Swarm detected ({len(quakes)} quakes) → select")

    def start(self) -> None:
        print(f"[earthquake] Starting earthquake bot (min M{EARTHQUAKE_MIN_MAGNITUDE}, polling every {EARTHQUAKE_POLL_INTERVAL}s)...")
        self._running = True
        self._process_tick()
        while self._running:
            time.sleep(EARTHQUAKE_POLL_INTERVAL)
            if self._running:
                self._process_tick()

    def stop(self) -> None:
        print("[earthquake] Stopping...")
        self._running = False
