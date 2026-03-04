import threading
from collections import Counter
from typing import Callable


class AnarchyProcessor:
    """Every command is queued immediately."""

    def __init__(self, on_command: Callable[[str], bool]):
        self.on_command = on_command
        self._total = 0

    def process(self, command: str) -> bool:
        result = self.on_command(command)
        if result:
            self._total += 1
            print(f"[anarchy] Executed '{command}' (total: {self._total})")
        return result

    def get_vote_counts(self) -> dict[str, int]:
        return {}


class DemocracyProcessor:
    """Collect votes over a time window, then execute the plurality winner."""

    def __init__(self, on_command: Callable[[str], bool], window_seconds: int = 10):
        self.on_command = on_command
        self.window_seconds = window_seconds
        self._votes: list[str] = []
        self._lock = threading.Lock()
        self._timer: threading.Timer | None = None
        self._round = 0
        self._total_commands = 0

    def process(self, command: str) -> bool:
        with self._lock:
            self._votes.append(command)
            count = len(self._votes)
            timer_active = self._timer is not None
            if self._timer is None:
                self._timer = threading.Timer(self.window_seconds, self._execute_winner)
                self._timer.start()
                print(f"[democracy] Vote window opened ({self.window_seconds}s) — first vote: '{command}'")
            else:
                print(f"[democracy] Vote received: '{command}' ({count} votes so far)")
        return True

    def _execute_winner(self):
        with self._lock:
            self._round += 1
            if self._votes:
                counts = dict(Counter(self._votes))
                winner = Counter(self._votes).most_common(1)[0][0]
                total_votes = len(self._votes)
                winner_pct = counts[winner] / total_votes * 100
                self._total_commands += 1
                print(
                    f"[democracy] Round {self._round} result — winner: '{winner}' "
                    f"({counts[winner]}/{total_votes} votes, {winner_pct:.0f}%) | "
                    f"full tally: {counts}"
                )
                self.on_command(winner)
                self._votes.clear()
            else:
                print(f"[democracy] Round {self._round} — no votes received, skipping")
            self._timer = None

    def get_vote_counts(self) -> dict[str, int]:
        with self._lock:
            return dict(Counter(self._votes))
