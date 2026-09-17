import asyncio
import logging

# =========================================================
# Pyrogram / PyTgCalls compatibility fix
# =========================================================

import pyrogram.errors

if not hasattr(pyrogram.errors, "GroupcallForbidden"):
    if hasattr(pyrogram.errors, "GroupCallForbidden"):
        pyrogram.errors.GroupcallForbidden = (
            pyrogram.errors.GroupCallForbidden
        )
    else:
        class GroupcallForbidden(Exception):
            pass

        pyrogram.errors.GroupcallForbidden = GroupcallForbidden


# =========================================================
# Imports
# =========================================================

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


# =========================================================
# Logging
# =========================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)

log = logging.getLogger("MahabubMusicBot")


# =========================================================
# Bot Account
# =========================================================

bot = Client(
    "mahbub_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
)


# =========================================================
# Assistant User Account
# This account joins the Telegram Voice Chat
# =========================================================

if not SESSION_STRING:
    raise RuntimeError(
        "SESSION_STRING is missing. "
        "A user account is required for voice chats."
    )

assistant = Client(
    "mahbub_assistant",
    api_id=API_ID,
    api_hash=API_HASH,
    session_string=SESSION_STRING,
)


# =========================================================
# PyTgCalls
# =========================================================

calls = PyTgCalls(assistant)

players = {}


# =========================================================
# Player Manager
# =========================================================

def get_player(chat_id: int) -> MusicPlayer:
    if chat_id not in players:
        players[chat_id] = MusicPlayer(
            chat_id,
            calls
        )

    return players[chat_id]


# =========================================================
# Stream End Handler
# =========================================================

@calls.on_update(tg_filters.stream_end())
async def stream_end_handler(_, update: StreamEnded):
    player = players.get(update.chat_id)

    if player:
        await player.on_stream_end()


# =========================================================
# START
# =========================================================

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


# =========================================================
# PLAY
# =========================================================

@bot.on_message(filters.command(["play", "p"]))
async def play_cmd(_, message: Message):

    if not message.text:
        return

    parts = message.text.split(
        maxsplit=1
    )

    if len(parts) < 2:
        return await message.reply_text(
            "❌ Usage:\n"
            "`/play song name or YouTube URL`"
        )

    query = parts[1].strip()

    if not query:
        return await message.reply_text(
            "❌ Please provide a song name or URL."
        )

    status = await message.reply_text(
        "🔎 **Searching...**"
    )

    try:

        player = get_player(
            message.chat.id
        )

        user_id = (
            message.from_user.id
            if message.from_user
            else 0
        )

        title = await player.add(
            query,
            user_id
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

        try:
            await status.edit_text(
                f"❌ `{str(exc)[:900]}`"
            )
        except Exception:
            pass


# =========================================================
# PAUSE
# =========================================================

@bot.on_message(filters.command("pause"))
async def pause_cmd(_, message: Message):

    try:

        await get_player(
            message.chat.id
        ).pause()

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


# =========================================================
# RESUME
# =========================================================

@bot.on_message(filters.command("resume"))
async def resume_cmd(_, message: Message):

    try:

        await get_player(
            message.chat.id
        ).resume()

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


# =========================================================
# SKIP
# =========================================================

@bot.on_message(filters.command("skip"))
async def skip_cmd(_, message: Message):

    try:

        title = await get_player(
            message.chat.id
        ).skip()

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


# =========================================================
# STOP / LEAVE
# =========================================================

@bot.on_message(
    filters.command(
        ["stop", "leave"]
    )
)
async def stop_cmd(_, message: Message):

    try:

        await get_player(
            message.chat.id
        ).stop()

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


# =========================================================
# QUEUE
# =========================================================

@bot.on_message(filters.command("queue"))
async def queue_cmd(_, message: Message):

    try:

        text = get_player(
            message.chat.id
        ).queue_text()

        await message.reply_text(
            text
        )

    except Exception as exc:

        log.exception(
            "Queue failed"
        )

        await message.reply_text(
            f"❌ `{str(exc)[:900]}`"
        )


# =========================================================
# NOW PLAYING
# =========================================================

@bot.on_message(filters.command("now"))
async def now_cmd(_, message: Message):

    try:

        text = get_player(
            message.chat.id
        ).now_text()

        await message.reply_text(
            text
        )

    except Exception as exc:

        log.exception(
            "Now failed"
        )

        await message.reply_text(
            f"❌ `{str(exc)[:900]}`"
        )


# =========================================================
# VOLUME
# =========================================================

@bot.on_message(filters.command("volume"))
async def volume_cmd(_, message: Message):

    parts = message.text.split()

    if len(parts) != 2:

        return await message.reply_text(
            "❌ Usage: `/volume 1-200`"
        )

    try:

        value = int(parts[1])

    except ValueError:

        return await message.reply_text(
            "❌ Volume must be a number."
        )

    if not 1 <= value <= 200:

        return await message.reply_text(
            "❌ Volume must be between 1 and 200."
        )

    try:

        await get_player(
            message.chat.id
        ).set_volume(value)

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


# =========================================================
# MAIN
# =========================================================

async def main():

    log.info(
        "Starting command bot..."
    )

    await bot.start()

    log.info(
        "Starting assistant user account..."
    )

    await assistant.start()

    log.info(
        "Starting PyTgCalls..."
    )

    await calls.start()

    try:

        me = await assistant.get_me()

        log.info(
            "Voice assistant logged in as %s (%s)",
            me.first_name,
            me.id,
        )

        print(
            "🎵 Mahabub Music Bot is running."
        )

        await asyncio.Event().wait()

    finally:

        log.info(
            "Stopping PyTgCalls..."
        )

        try:
            await calls.stop()
        except Exception:
            pass

        log.info(
            "Stopping assistant..."
        )

        try:
            await assistant.stop()
        except Exception:
            pass

        log.info(
            "Stopping bot..."
        )

        try:
            await bot.stop()
        except Exception:
            pass


# =========================================================
# RUN
# =========================================================

if __name__ == "__main__":

    try:

        asyncio.run(
            main()
        )

    except KeyboardInterrupt:

        print(
            "\n🛑 Bot stopped."
        )

    except Exception as exc:

        log.exception(
            "Fatal error: %s",
            exc
        )
