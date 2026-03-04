import time
import threading
from datetime import datetime
from zoneinfo import ZoneInfo

from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from slack_sdk import WebClient

from config import (
    SLACK_BOT_TOKEN, SLACK_APP_TOKEN, CHANNEL_ID,
    MODE, DEMOCRACY_WINDOW, SCREENSHOT_INTERVAL, FRAMES_PER_INPUT,
    TIMEZONE, QUIET_HOURS_START, QUIET_HOURS_END,
)
from emulator import Emulator
from command_processor import AnarchyProcessor, DemocracyProcessor

VALID_COMMANDS = {"up", "down", "left", "right", "a", "b", "start", "select"}


class SlackBot:
    def __init__(self, emulator: Emulator):
        self.emulator = emulator
        self.app = App(token=SLACK_BOT_TOKEN)
        self.client = WebClient(token=SLACK_BOT_TOKEN)
        self._total_messages = 0
        self._total_valid = 0
        self._total_screenshots = 0

        if MODE == "democracy":
            self.processor = DemocracyProcessor(
                on_command=emulator.queue_command,
                window_seconds=DEMOCRACY_WINDOW,
            )
            print(f"[bot] Mode: democracy ({DEMOCRACY_WINDOW}s vote window)")
        else:
            self.processor = AnarchyProcessor(on_command=emulator.queue_command)
            print("[bot] Mode: anarchy")

        self._register_handlers()

    def _register_handlers(self):
        @self.app.message()
        def handle_message(message, say):
            self._total_messages += 1

            channel = message.get("channel")
            if channel != CHANNEL_ID:
                print(f"[bot] Ignored message from wrong channel: {channel}")
                return
            if message.get("bot_id") or message.get("subtype"):
                print(f"[bot] Ignored bot/system message (subtype={message.get('subtype')})")
                return

            text = message.get("text", "").lower().strip()
            user = message.get("user", "unknown")

            if text not in VALID_COMMANDS:
                print(f"[bot] Ignored invalid command '{text}' from user {user} (msg #{self._total_messages})")
                return

            self._total_valid += 1
            accepted = self.processor.process(text)
            status = "accepted" if accepted else "rejected"
            print(f"[bot] '{text}' from {user} — {status} (valid cmd #{self._total_valid})")

            if accepted and MODE == "democracy":
                counts = self.processor.get_vote_counts()
                vote_str = "  |  ".join(
                    f"*{k}*: {v}" for k, v in sorted(counts.items(), key=lambda x: -x[1])
                )
                try:
                    self.client.reactions_add(
                        channel=message["channel"],
                        timestamp=message["ts"],
                        name="ballot_box_with_ballot",
                    )
                    print(f"[bot] Added ballot reaction to message from {user}")
                except Exception as e:
                    print(f"[bot] Failed to add reaction: {e}")

    def post_screenshot(self, caption: str = ""):
        print(f"[bot] Capturing screenshot for Slack...")
        try:
            png_bytes = self.emulator.get_screenshot()
            self.client.files_upload_v2(
                channel=CHANNEL_ID,
                content=png_bytes,
                filename="pokemon.png",
                title=caption or "Current game state",
            )
            self._total_screenshots += 1
            print(f"[bot] Screenshot #{self._total_screenshots} posted to Slack (caption: '{caption or 'none'}')")
        except Exception as e:
            print(f"[bot] Screenshot upload failed: {e}")
            raise

    def _is_quiet_hours(self) -> bool:
        hour = datetime.now(ZoneInfo(TIMEZONE)).hour
        if QUIET_HOURS_START > QUIET_HOURS_END:
            # Wraps midnight e.g. 22 -> 8
            return hour >= QUIET_HOURS_START or hour < QUIET_HOURS_END
        return QUIET_HOURS_START <= hour < QUIET_HOURS_END

    def _seconds_until_quiet_hours_end(self) -> float:
        now = datetime.now(ZoneInfo(TIMEZONE))
        wake = now.replace(hour=QUIET_HOURS_END, minute=0, second=0, microsecond=0)
        if wake <= now:
            wake = wake.replace(day=wake.day + 1)
        return (wake - now).total_seconds()

    def _screenshot_loop(self):
        if SCREENSHOT_INTERVAL == 0:
            print("[bot] Screenshots disabled (SCREENSHOT_INTERVAL=0)")
            return
        print(f"[bot] Screenshot loop started — waiting 3s for emulator boot...")
        time.sleep(3)
        self.post_screenshot("Game started! Send commands: up down left right a b start select")
        print(f"[bot] Will post screenshots every {SCREENSHOT_INTERVAL}s (quiet hours: {QUIET_HOURS_START}:00–{QUIET_HOURS_END}:00 {TIMEZONE})")
        while True:
            time.sleep(SCREENSHOT_INTERVAL)
            if self._is_quiet_hours():
                secs = self._seconds_until_quiet_hours_end()
                print(f"[bot] Quiet hours active — sleeping until {QUIET_HOURS_END}:00 {TIMEZONE} ({secs/3600:.1f}h)")
                time.sleep(secs)
                print("[bot] Quiet hours over, resuming screenshots")
                continue
            try:
                self.post_screenshot()
            except Exception as e:
                print(f"[bot] Screenshot loop error: {e}")

    def start(self):
        t = threading.Thread(target=self._screenshot_loop, daemon=True)
        t.start()
        print(f"[bot] Listening on channel {CHANNEL_ID}...")
        SocketModeHandler(self.app, SLACK_APP_TOKEN).start()
