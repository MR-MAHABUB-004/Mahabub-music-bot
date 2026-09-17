# Mahabub Music Bot v2 🎵

Fast Telegram Voice Chat music bot using:

- Pyrogram
- PyTgCalls 2.3.3
- yt-dlp
- FFmpeg

## Important: voice chat requires a USER account

Telegram's `phone.joinGroupCall` method is restricted to users, so the
voice player uses a separate Pyrogram USER session. The normal BotFather
bot handles commands.

The USER account must be in the group and should have permission to
manage voice chats.

## Environment variables

```env
API_ID=YOUR_API_ID
API_HASH=YOUR_API_HASH
BOT_TOKEN=YOUR_BOT_TOKEN
SESSION_STRING=YOUR_USER_SESSION_STRING
```

## Generate SESSION_STRING

Install requirements locally:

```bash
pip install -r requirements.txt
```

Then:

```bash
python generate_session.py
```

Enter the USER account phone number, Telegram login code and 2FA password
if enabled. Copy the generated session string into `SESSION_STRING`.

Do not share the session string.

## Commands

```text
/play <song or YouTube URL>
/pause
/resume
/skip
/stop
/leave
/queue
/now
/volume 1-200
```

## Render

Use **Docker**.

Add these four Environment Variables in Render:

```text
API_ID
API_HASH
BOT_TOKEN
SESSION_STRING
```

No `.env` file is required on Render.

## VPS

```bash
sudo apt update
sudo apt install -y ffmpeg python3 python3-pip

pip3 install -r requirements.txt

python3 bot.py
```

For a VPS, PM2/systemd/supervisor can keep the process alive.

## Speed

The player uses a direct media stream through PyTgCalls' current
`MediaStream` API. It does not download the complete song before
starting playback.
