import signal
import threading

from config import ROM_PATH, FRAMES_PER_INPUT, TWITCH_STREAM_KEY, SLACK_BOT_TOKEN, TWITCH_BOT_TOKEN, TWITCH_CHANNEL
from emulator import Emulator
from base_bot import BaseBotAdapter


def main():
    print("=== Slack Plays GBA ===")

    emulator = Emulator(ROM_PATH, frames_per_input=FRAMES_PER_INPUT)

    emulator_thread = threading.Thread(target=emulator.run, daemon=True)
    emulator_thread.start()
    print(f"[main] Emulator started with ROM: {ROM_PATH}")

    streamer = None
    if TWITCH_STREAM_KEY:
        from streamer import TwitchStreamer
        streamer = TwitchStreamer(emulator)
        stream_thread = threading.Thread(target=streamer.run, daemon=True)
        stream_thread.start()
    else:
        print("[main] No TWITCH_STREAM_KEY set — skipping stream")

    bots: list[BaseBotAdapter] = []

    if SLACK_BOT_TOKEN:
        from bot import SlackBot
        bots.append(SlackBot(emulator))
    else:
        print("[main] No SLACK_BOT_TOKEN set — skipping Slack bot")

    if TWITCH_BOT_TOKEN and TWITCH_CHANNEL:
        from twitch_bot import TwitchBot
        bots.append(TwitchBot(emulator))
    else:
        print("[main] No TWITCH_BOT_TOKEN/TWITCH_CHANNEL set — skipping Twitch bot")

    if not bots:
        print("[main] No bots configured — exiting. Set SLACK_BOT_TOKEN or TWITCH_BOT_TOKEN+TWITCH_CHANNEL.")
        emulator.stop()
        return

    for bot in bots:
        t = threading.Thread(target=bot.start, daemon=True)
        t.start()

    stop_event = threading.Event()

    def shutdown(sig, frame):
        print("\n[main] Shutting down...")
        emulator.stop()
        for bot in bots:
            bot.stop()
        if streamer:
            streamer.stop()
        stop_event.set()

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    stop_event.wait()


if __name__ == "__main__":
    main()
