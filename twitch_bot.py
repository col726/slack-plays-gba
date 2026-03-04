import asyncio

import twitchio

from base_bot import BaseBotAdapter
from config import TWITCH_BOT_TOKEN, TWITCH_CHANNEL
from emulator import Emulator

VALID_COMMANDS = {"up", "down", "left", "right", "a", "b", "start", "select"}


class _TwitchClient(twitchio.Client):
    def __init__(self, token: str, channel: str, emulator: Emulator):
        super().__init__(token=token, initial_channels=[channel])
        self._channel = channel
        self._emulator = emulator
        self._total_messages = 0
        self._total_valid = 0

    async def event_ready(self):
        print(f"[twitch] Connected as {self.nick}, listening in #{self._channel}")

    async def event_message(self, message: twitchio.Message):
        if message.echo:
            return
        self._total_messages += 1
        text = message.content.lower().strip()
        user = message.author.name if message.author else "unknown"

        if text not in VALID_COMMANDS:
            print(f"[twitch] Ignored '{text}' from {user} (msg #{self._total_messages})")
            return

        self._total_valid += 1
        self._emulator.queue_command(text)
        self._emulator.set_last_input("Twitch", user, text)
        print(f"[twitch] '{text}' from {user} (valid cmd #{self._total_valid})")


class TwitchBot(BaseBotAdapter):
    def __init__(self, emulator: Emulator):
        self._emulator = emulator
        self._client: _TwitchClient | None = None
        self._loop: asyncio.AbstractEventLoop | None = None

    def start(self) -> None:
        print(f"[twitch] Starting bot for channel #{TWITCH_CHANNEL}...")
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._client = _TwitchClient(
            token=TWITCH_BOT_TOKEN,
            channel=TWITCH_CHANNEL,
            emulator=self._emulator,
        )
        self._loop.run_until_complete(self._client.start())

    def stop(self) -> None:
        print("[twitch] Stopping...")
        if self._client and self._loop and not self._loop.is_closed():
            asyncio.run_coroutine_threadsafe(self._client.close(), self._loop)
