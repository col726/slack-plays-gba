import signal
import sys
import threading

from config import ROM_PATH, FRAMES_PER_INPUT, TWITCH_STREAM_KEY
from emulator import Emulator
from bot import SlackBot


def main():
    print("=== Slack Plays GBA ===")

    emulator = Emulator(ROM_PATH, frames_per_input=FRAMES_PER_INPUT)
    bot = SlackBot(emulator)

    emulator_thread = threading.Thread(target=emulator.run, daemon=True)
    emulator_thread.start()
    print(f"[main] Emulator started with ROM: {ROM_PATH}")

    if TWITCH_STREAM_KEY:
        from streamer import TwitchStreamer
        streamer = TwitchStreamer(emulator)
        stream_thread = threading.Thread(target=streamer.run, daemon=True)
        stream_thread.start()
    else:
        print("[main] No TWITCH_STREAM_KEY set — skipping stream")

    def shutdown(sig, frame):
        print("\n[main] Shutting down...")
        emulator.stop()
        if TWITCH_STREAM_KEY:
            streamer.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    bot.start()  # blocks until stopped


if __name__ == "__main__":
    main()
