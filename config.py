import os
from dotenv import load_dotenv

load_dotenv()

ROM_PATH = os.environ["ROM_PATH"]

# Slack (optional — leave blank to disable)
SLACK_BOT_TOKEN = os.environ.get("SLACK_BOT_TOKEN", "")
SLACK_APP_TOKEN = os.environ.get("SLACK_APP_TOKEN", "")
CHANNEL_ID = os.environ.get("SLACK_CHANNEL_ID", "")

# Twitch chat bot (optional — leave blank to disable)
# Get a token at https://twitchapps.com/tmi/ — pass the value without the "oauth:" prefix
TWITCH_BOT_TOKEN = os.environ.get("TWITCH_BOT_TOKEN", "")
TWITCH_CHANNEL = os.environ.get("TWITCH_CHANNEL", "")  # channel name, e.g. "yourchannel"

MODE = os.environ.get("MODE", "anarchy")          # "anarchy" or "democracy"
DEMOCRACY_WINDOW = int(os.environ.get("DEMOCRACY_WINDOW", "10"))  # seconds per vote window
SCREENSHOT_INTERVAL = int(os.environ.get("SCREENSHOT_INTERVAL", "300"))  # seconds between screenshots

# Quiet hours — no screenshots will be posted during this window
TIMEZONE = os.environ.get("TIMEZONE", "America/New_York")
QUIET_HOURS_START = int(os.environ.get("QUIET_HOURS_START", "22"))  # 10pm
QUIET_HOURS_END = int(os.environ.get("QUIET_HOURS_END", "8"))       # 8am
FRAMES_PER_INPUT = int(os.environ.get("FRAMES_PER_INPUT", "6"))  # frames to hold a button

# Game Boy native resolution and stream output size
GB_WIDTH = 160
GB_HEIGHT = 144
STREAM_SCALE = 6
STREAM_WIDTH = GB_WIDTH * STREAM_SCALE   # 960
STREAM_HEIGHT = GB_HEIGHT * STREAM_SCALE  # 864
SAVE_STATE_PATH = os.environ.get("SAVE_STATE_PATH", "autosave.state")

# Market bot (optional — no credentials needed)
MARKET_BOT_ENABLED = os.environ.get("MARKET_BOT_ENABLED", "").lower() in ("1", "true", "yes")
MARKET_POLL_INTERVAL = int(os.environ.get("MARKET_POLL_INTERVAL", "300"))

# Weather bot (optional — requires OpenWeatherMap API key)
WEATHER_API_KEY = os.environ.get("WEATHER_API_KEY", "")
WEATHER_CITY = os.environ.get("WEATHER_CITY", "New York")
WEATHER_POLL_INTERVAL = int(os.environ.get("WEATHER_POLL_INTERVAL", "600"))

# Twitch streaming (optional — leave blank to disable)
TWITCH_STREAM_KEY = os.environ.get("TWITCH_STREAM_KEY", "")
STREAM_FPS = int(os.environ.get("STREAM_FPS", "30"))
