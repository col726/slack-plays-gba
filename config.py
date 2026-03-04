import os
from dotenv import load_dotenv

load_dotenv()

SLACK_BOT_TOKEN = os.environ["SLACK_BOT_TOKEN"]
SLACK_APP_TOKEN = os.environ["SLACK_APP_TOKEN"]
CHANNEL_ID = os.environ["SLACK_CHANNEL_ID"]
ROM_PATH = os.environ["ROM_PATH"]

MODE = os.environ.get("MODE", "anarchy")          # "anarchy" or "democracy"
DEMOCRACY_WINDOW = int(os.environ.get("DEMOCRACY_WINDOW", "10"))  # seconds per vote window
SCREENSHOT_INTERVAL = int(os.environ.get("SCREENSHOT_INTERVAL", "300"))  # seconds between screenshots

# Quiet hours — no screenshots will be posted during this window
TIMEZONE = os.environ.get("TIMEZONE", "America/New_York")
QUIET_HOURS_START = int(os.environ.get("QUIET_HOURS_START", "22"))  # 10pm
QUIET_HOURS_END = int(os.environ.get("QUIET_HOURS_END", "8"))       # 8am
FRAMES_PER_INPUT = int(os.environ.get("FRAMES_PER_INPUT", "6"))  # frames to hold a button

# Twitch streaming (optional — leave blank to disable)
TWITCH_STREAM_KEY = os.environ.get("TWITCH_STREAM_KEY", "")
STREAM_FPS = int(os.environ.get("STREAM_FPS", "30"))
