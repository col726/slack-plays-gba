import time
from dataclasses import dataclass

import requests

from base_bot import BaseBotAdapter
from config import SPORTS_POLL_INTERVAL
from emulator import Emulator

ESPN_URL = "https://site.api.espn.com/apis/site/v2/sports/{sport}/{league}/scoreboard"

# sport path, league path, score jump that triggers 'a', normal periods before OT
SPORTS = {
    "NFL": ("football",   "nfl",  6, 4),
    "NBA": ("basketball", "nba",  3, 4),
    "NHL": ("hockey",     "nhl",  1, 3),
    "MLB": ("baseball",   "mlb",  2, 9),
}

SIMULTANEOUS_SCORING_THRESHOLD = 2  # games scoring in same poll to trigger 'select'


@dataclass
class GameState:
    home_score: int
    away_score: int
    state: str      # "pre", "in", "post"
    period: int
    home_abbr: str
    away_abbr: str


def _fetch_games(sport: str, league: str) -> dict[str, GameState]:
    url = ESPN_URL.format(sport=sport, league=league)
    resp = requests.get(url, timeout=10)
    resp.raise_for_status()
    games = {}
    for event in resp.json().get("events", []):
        game_id = event["id"]
        status = event["status"]
        state = status["type"]["state"]
        period = status.get("period", 0)
        comp = event["competitions"][0]
        home = next(c for c in comp["competitors"] if c["homeAway"] == "home")
        away = next(c for c in comp["competitors"] if c["homeAway"] == "away")
        games[game_id] = GameState(
            home_score=int(home.get("score") or 0),
            away_score=int(away.get("score") or 0),
            state=state,
            period=period,
            home_abbr=home["team"]["abbreviation"],
            away_abbr=away["team"]["abbreviation"],
        )
    return games


class SportsBot(BaseBotAdapter):
    def __init__(self, emulator: Emulator):
        self._emulator = emulator
        self._running = False
        # {league_name: {game_id: GameState}}
        self._last_state: dict[str, dict[str, GameState]] = {name: {} for name in SPORTS}

    def _process_league(self, name: str, sport: str, league: str, big_score: int, max_period: int) -> int:
        """Process one league. Returns number of scoring events this tick."""
        try:
            current = _fetch_games(sport, league)
        except Exception as e:
            print(f"[sports] Failed to fetch {name}: {e}")
            return 0

        if not current:
            print(f"[sports] {name}: no games today")
            self._last_state[name] = {}
            return 0

        active = [g for g in current.values() if g.state == "in"]
        print(f"[sports] {name}: {len(current)} game(s) today, {len(active)} active")

        last = self._last_state[name]
        scoring_events = 0
        commands: list[tuple[str, str]] = []

        for game_id, curr in current.items():
            prev = last.get(game_id)
            label = f"{curr.away_abbr}@{curr.home_abbr}"

            if prev is None:
                # First time seeing this game — just record state
                continue

            # Game started
            if prev.state == "pre" and curr.state == "in":
                commands.append(("right", f"{name} {label} started"))

            # Game ended
            elif prev.state == "in" and curr.state == "post":
                commands.append(("left", f"{name} {label} final"))

            if curr.state == "in":
                # Overtime
                if curr.period > max_period and curr.period > prev.period:
                    commands.append(("start", f"{name} {label} OT"))

                # Home team scored
                home_delta = curr.home_score - prev.home_score
                if home_delta > 0:
                    commands.append(("up", f"{name} {curr.home_abbr} +{home_delta}"))
                    if home_delta >= big_score:
                        commands.append(("a", f"{name} {curr.home_abbr} big score"))
                    scoring_events += 1

                # Away team scored
                away_delta = curr.away_score - prev.away_score
                if away_delta > 0:
                    commands.append(("down", f"{name} {curr.away_abbr} +{away_delta}"))
                    if away_delta >= big_score:
                        commands.append(("a", f"{name} {curr.away_abbr} big score"))
                    scoring_events += 1

                # Lead changed
                prev_leading = "home" if prev.home_score > prev.away_score else \
                               "away" if prev.away_score > prev.home_score else "tied"
                curr_leading = "home" if curr.home_score > curr.away_score else \
                               "away" if curr.away_score > curr.home_score else "tied"
                if prev_leading != curr_leading and curr_leading != "tied":
                    commands.append(("b", f"{name} {label} lead change"))

        for cmd, lbl in commands:
            self._emulator.queue_command(cmd)
            self._emulator.set_last_input("Sports", lbl, cmd)
            print(f"[sports] {lbl} → {cmd}")

        self._last_state[name] = current
        return scoring_events

    def _process_tick(self):
        total_scoring = 0
        for name, (sport, league, big_score, max_period) in SPORTS.items():
            total_scoring += self._process_league(name, sport, league, big_score, max_period)

        # Multiple games scoring simultaneously
        if total_scoring >= SIMULTANEOUS_SCORING_THRESHOLD:
            self._emulator.queue_command("select")
            self._emulator.set_last_input("Sports", f"{total_scoring} games scoring", "select")
            print(f"[sports] {total_scoring} simultaneous scoring events → select")

    def start(self) -> None:
        print(f"[sports] Starting sports bot (NFL/NBA/NHL/MLB, polling every {SPORTS_POLL_INTERVAL}s)...")
        self._running = True
        self._process_tick()
        while self._running:
            time.sleep(SPORTS_POLL_INTERVAL)
            if self._running:
                self._process_tick()

    def stop(self) -> None:
        print("[sports] Stopping...")
        self._running = False
