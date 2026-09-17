# Mahabub Music Bot 🎵

Fast Telegram group voice-chat music bot using Pyrogram, PyTgCalls, yt-dlp and FFmpeg.

## Requirements

- Python 3.10/3.11 recommended
- FFmpeg
- Telegram Bot Token
- Telegram API ID and API Hash
- The bot must be an administrator in the group and be allowed to manage voice chats.

## Install

```bash
sudo apt update
sudo apt install -y ffmpeg python3 python3-pip
pip3 install -r requirements.txt
```

Set environment variables:

```bash
export API_ID="YOUR_API_ID"
export API_HASH="YOUR_API_HASH"
export BOT_TOKEN="YOUR_BOT_TOKEN"
```

Run:

```bash
python3 bot.py
```

## Commands

/play <song or YouTube URL>
/pause
/resume
/skip
/stop
/leave
/queue
/now
/volume 1-100

## Docker

```bash
docker build -t mahbub-music-bot .
docker run --restart unless-stopped \
  -e API_ID="YOUR_API_ID" \
  -e API_HASH="YOUR_API_HASH" \
  -e BOT_TOKEN="YOUR_BOT_TOKEN" \
  mahbub-music-bot
```

## Speed notes

The player resolves the audio stream and sends it to PyTgCalls without downloading the complete song first. YouTube extraction is the main startup bottleneck, so keeping yt-dlp updated is important.

This is a starter production-oriented project. PyTgCalls APIs can change between releases; pin the dependency versions on your VPS after confirming a working deployment.
