import asyncio
import logging

from pyrogram import Client, filters
from pyrogram.types import Message

from pytgcalls import PyTgCalls
from pytgcalls import filters as tg_filters
from pytgcalls.types import StreamEnded

from config import (
    API_ID,
    API_HASH,
    BOT_TOKEN,
    SESSION_STRING,
)

from player import MusicPlayer


# ============================================================
# Logging
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)

log = logging.getLogger("MahabubMusicBot")


# ============================================================
# Validate configuration
# ============================================================

if not API_ID:
    raise RuntimeError("API_ID is missing.")

if not API_HASH:
    raise RuntimeError("API_HASH is missing.")

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is missing.")

if not SESSION_STRING:
    raise RuntimeError(
        "SESSION_STRING is missing. "
        "A user account is required for voice chats."
    )


# ============================================================
# Telegram Bot Account
# ============================================================

bot = Client(
    "mahbub_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
)


# ============================================================
# Telegram User Account
# This account joins the voice chat.
# ============================================================

assistant = Client(
    "mahbub_assistant",
    api_id=API_ID,
    api_hash=API_HASH,
    session_string=SESSION_STRING,
)


# ============================================================
# PyTgCalls
# ============================================================

calls = PyTgCalls(assistant)

players = {}


# ============================================================
# Player manager
# ============================================================

def get_player(chat_id: int) -> MusicPlayer:

    if chat_id not in players:

        players[chat_id] = MusicPlayer(
            chat_id,
            calls,
        )

    return players[chat_id]


# ============================================================
# Stream ended
# ============================================================

@calls.on_update(tg_filters.stream_end())
async def stream_end_handler(_, update: StreamEnded):

    player = players.get(update.chat_id)

    if player:

        try:
            await player.on_stream_end()

        except Exception:

            log.exception(
                "Stream end handler failed"
            )


# ============================================================
# START
# ============================================================

@bot.on_message(filters.command("start"))
async def start_cmd(_, message: Message):

    await message.reply_text(
        "🎵 **Mahabub Music Bot**\n\n"
        "Fast Telegram Voice Chat Music Player.\n\n"
        "▶️ `/play <song or YouTube URL>`\n"
        "⏸ `/pause`\n"
        "▶️ `/resume`\n"
        "⏭ `/skip`\n"
        "⏹ `/stop`\n"
        "📜 `/queue`\n"
        "🎵 `/now`\n"
        "🔊 `/volume 1-200`"
    )


# ============================================================
# PLAY
# ============================================================

@bot.on_message(filters.command(["play", "p"]))
async def play_cmd(_, message: Message):

    if not message.text:
        return

    parts = message.text.split(
        maxsplit=1
    )

    if len(parts) < 2:

        await message.reply_text(
            "❌ **Usage:**\n"
            "`/play song name or YouTube URL`"
        )

        return

    query = parts[1].strip()

    if not query:

        await message.reply_text(
            "❌ Please provide a song name or URL."
        )

        return

    status = await message.reply_text(
        "🔎 **Searching...**"
    )

    try:

        player = get_player(
            message.chat.id
        )

        requester = (
            message.from_user.id
            if message.from_user
            else 0
        )

        title = await player.add(
            query,
            requester,
        )

        if player.current:

            await status.edit_text(
                f"🎵 **Queued:** {title}"
            )

        else:

            await status.edit_text(
                f"🎵 **Starting:** {title}"
            )

        await player.start_if_needed()

    except Exception as exc:

        log.exception(
            "Play failed"
        )

        await status.edit_text(
            f"❌ `{str(exc)[:900]}`"
        )


# ============================================================
# PAUSE
# ============================================================

@bot.on_message(filters.command("pause"))
async def pause_cmd(_, message: Message):

    try:

        player = get_player(
            message.chat.id
        )

        await player.pause()

        await message.reply_text(
            "⏸ **Paused**"
        )

    except Exception as exc:

        log.exception(
            "Pause failed"
        )

        await message.reply_text(
            f"❌ `{str(exc)[:900]}`"
        )


# ============================================================
# RESUME
# ============================================================

@bot.on_message(filters.command("resume"))
async def resume_cmd(_, message: Message):

    try:

        player = get_player(
            message.chat.id
        )

        await player.resume()

        await message.reply_text(
            "▶️ **Resumed**"
        )

    except Exception as exc:

        log.exception(
            "Resume failed"
        )

        await message.reply_text(
            f"❌ `{str(exc)[:900]}`"
        )


# ============================================================
# SKIP
# ============================================================

@bot.on_message(filters.command("skip"))
async def skip_cmd(_, message: Message):

    try:

        player = get_player(
            message.chat.id
        )

        title = await player.skip()

        if title:

            await message.reply_text(
                f"⏭ **Skipped**\n"
                f"🎵 **Next:** {title}"
            )

        else:

            await message.reply_text(
                "⏭ Queue finished."
            )

    except Exception as exc:

        log.exception(
            "Skip failed"
        )

        await message.reply_text(
            f"❌ `{str(exc)[:900]}`"
        )


# ============================================================
# STOP / LEAVE
# ============================================================

@bot.on_message(
    filters.command(
        ["stop", "leave"]
    )
)
async def stop_cmd(_, message: Message):

    try:

        player = get_player(
            message.chat.id
        )

        await player.stop()

        await message.reply_text(
            "⏹ **Stopped and left the voice chat.**"
        )

    except Exception as exc:

        log.exception(
            "Stop failed"
        )

        await message.reply_text(
            f"❌ `{str(exc)[:900]}`"
        )


# ============================================================
# QUEUE
# ============================================================

@bot.on_message(filters.command("queue"))
async def queue_cmd(_, message: Message):

    try:

        player = get_player(
            message.chat.id
        )

        await message.reply_text(
            player.queue_text()
        )

    except Exception as exc:

        log.exception(
            "Queue failed"
        )

        await message.reply_text(
            f"❌ `{str(exc)[:900]}`"
        )


# ============================================================
# NOW
# ============================================================

@bot.on_message(filters.command("now"))
async def now_cmd(_, message: Message):

    try:

        player = get_player(
            message.chat.id
        )

        await message.reply_text(
            player.now_text()
        )

    except Exception as exc:

        log.exception(
            "Now failed"
        )

        await message.reply_text(
            f"❌ `{str(exc)[:900]}`"
        )


# ============================================================
# VOLUME
# ============================================================

@bot.on_message(filters.command("volume"))
async def volume_cmd(_, message: Message):

    if not message.text:

        await message.reply_text(
            "❌ Usage: `/volume 1-200`"
        )

        return

    parts = message.text.split()

    if len(parts) != 2:

        await message.reply_text(
            "❌ Usage: `/volume 1-200`"
        )

        return

    try:

        value = int(parts[1])

    except ValueError:

        await message.reply_text(
            "❌ Volume must be a number."
        )

        return

    if not 1 <= value <= 200:

        await message.reply_text(
            "❌ Volume must be between 1 and 200."
        )

        return

    try:

        player = get_player(
            message.chat.id
        )

        await player.set_volume(
            value
        )

        await message.reply_text(
            f"🔊 Volume: **{value}%**"
        )

    except Exception as exc:

        log.exception(
            "Volume failed"
        )

        await message.reply_text(
            f"❌ `{str(exc)[:900]}`"
        )


# ============================================================
# MAIN
# ============================================================

async def main():

    log.info(
        "Starting Mahabub Music Bot..."
    )

    # --------------------------------------------------------
    # Start Telegram bot
    # --------------------------------------------------------

    await bot.start()

    log.info(
        "Command bot started."
    )

    # --------------------------------------------------------
    # Start Telegram user account
    # --------------------------------------------------------

    await assistant.start()

    log.info(
        "Assistant user account started."
    )

    # --------------------------------------------------------
    # Start PyTgCalls
    # --------------------------------------------------------

    await calls.start()

    log.info(
        "Voice call engine started."
    )

    # --------------------------------------------------------
    # Get bot information
    # --------------------------------------------------------

    bot_me = await bot.get_me()

    # --------------------------------------------------------
    # Get assistant information
    # --------------------------------------------------------

    me = await assistant.get_me()

    log.info(
        "Voice assistant: %s (@%s) | ID: %s",
        me.first_name,
        me.username or "none",
        me.id,
    )

    # --------------------------------------------------------
    # Startup information
    # --------------------------------------------------------

    print(
        "\n"
        "🎵 MAHABUB MUSIC BOT\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🤖 Bot: @{bot_me.username or 'unknown'}\n"
        f"👤 Assistant: {me.first_name}\n"
        f"🆔 Assistant ID: {me.id}\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "✅ Bot started successfully!\n"
        "🎶 Voice Chat Music System: ONLINE\n"
        "⚡ Ready to play music!\n"
    )

    # --------------------------------------------------------
    # Keep bot alive
    # --------------------------------------------------------

    await asyncio.Event().wait()


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":

    try:

        # NOTE: `bot`, `assistant`, and `calls` above are created at
        # import time (module load), before any event loop exists.
        # `asyncio.run(main())` always creates a *brand-new* loop —
        # different from whatever loop those objects implicitly
        # bound their internal locks/queues to — which is exactly
        # what causes "Future ... attached to a different loop".
        # Reusing the same (already-current) loop instead of
        # asyncio.run() fixes that mismatch.
        loop = asyncio.get_event_loop()
        loop.run_until_complete(main())

    except KeyboardInterrupt:

        log.info(
            "Bot stopped by user."
        )

    except Exception:

        log.exception(
            "Fatal error"
        )

        raise
