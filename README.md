# Slack Plays GBA

A "Twitch Plays Pokemon"-style bot that lets your Slack workspace control a Game Boy emulator. Users send button commands in a Slack channel, and the bot feeds them into PyBoy in real time. Screenshots are posted automatically so everyone can follow along.

## Prerequisites

- Python 3.12+
- A Slack app with a bot token and app-level token (Socket Mode enabled)
- A Game Boy / Game Boy Color ROM (`.gb` or `.gbc`)
- ffmpeg (only if using Twitch streaming)

## Setup

**1. Clone the repo and create a virtual environment**

```bash
git clone <repo-url>
cd slack-plays-gba
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

**2. Configure environment variables**

```bash
cp .env.example .env
```

Edit `.env` and fill in:

| Variable | Description |
|---|---|
| `SLACK_BOT_TOKEN` | Bot token from your Slack app's OAuth & Permissions page (`xoxb-...`) |
| `SLACK_APP_TOKEN` | App-level token with `connections:write` scope (`xapp-...`) |
| `SLACK_CHANNEL_ID` | ID of the channel to watch (right-click channel → Copy channel ID) |
| `ROM_PATH` | Path to your `.gb` or `.gbc` ROM file |

**3. Set up your Slack app**

In your Slack app settings:
- Enable **Socket Mode**
- Under **OAuth & Permissions**, add the bot scopes: `chat:write`, `files:write`, `channels:history`
- Under **Event Subscriptions**, subscribe to `message.channels`
- Install the app to your workspace and invite the bot to your channel

**4. Run the bot**

```bash
python main.py
```

## Usage

Send button commands in the configured Slack channel:

`up` `down` `left` `right` `a` `b` `start` `select`

**Anarchy mode** (default): every command executes immediately.

**Democracy mode**: votes are collected over a time window and the most-voted command wins. Set `MODE=democracy` and `DEMOCRACY_WINDOW=<seconds>` in `.env`.

Screenshots are posted to the channel automatically on the interval set by `SCREENSHOT_INTERVAL` (default: 300 seconds). Quiet hours can be configured with `QUIET_HOURS_START` and `QUIET_HOURS_END` to suppress overnight screenshots.

## Optional: Twitch Streaming

Set `TWITCH_STREAM_KEY` in `.env` to your Twitch stream key. The bot will pipe the emulator output to Twitch via ffmpeg automatically. Leave it blank to disable.
