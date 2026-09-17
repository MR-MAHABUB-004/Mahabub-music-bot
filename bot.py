import asyncio
import logging

from pyrogram import Client, filters
from pyrogram.types import Message
from pytgcalls import PyTgCalls
from pytgcalls import filters as tg_filters
from pytgcalls.types import StreamEnded

from config import API_ID, API_HASH, BOT_TOKEN, SESSION_STRING
from player import MusicPlayer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
log = logging.getLogger("MahabubMusicBot")

bot = Client(
    "mahbub_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
)

# A USER account is required for Telegram voice-chat participation.
assistant = Client(
    "mahbub_assistant",
    api_id=API_ID,
    api_hash=API_HASH,
    session_string=SESSION_STRING,
)

calls = PyTgCalls(assistant)
players = {}


def get_player(chat_id: int) -> MusicPlayer:
    if chat_id not in players:
        players[chat_id] = MusicPlayer(chat_id, calls)
    return players[chat_id]


@calls.on_update(tg_filters.stream_end())
async def stream_end_handler(_, update: StreamEnded):
    player = players.get(update.chat_id)
    if player:
        await player.on_stream_end()


@bot.on_message(filters.command("start"))
async def start_cmd(_, message: Message):
    await message.reply_text(
        "🎵 **Mahabub Music Bot**\n\n"
        "Fast Telegram Voice Chat Music Player.\n\n"
        "▶️ `/play <song or YouTube URL>`\n"
        "⏸ `/pause`  ▶️ `/resume`\n"
        "⏭ `/skip`  ⏹ `/stop`\n"
        "📜 `/queue`  🎵 `/now`\n"
        "🔊 `/volume 1-200`"
    )


@bot.on_message(filters.command(["play", "p"]))
async def play_cmd(_, message: Message):
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        return await message.reply_text(
            "❌ Usage: `/play song name or YouTube URL`"
        )

    query = parts[1].strip()
    status = await message.reply_text("🔎 **Searching...**")

    try:
        player = get_player(message.chat.id)
        title = await player.add(query, message.from_user.id if message.from_user else 0)

        if player.current:
            await status.edit_text(f"🎵 **Queued:** {title}")
        else:
            await status.edit_text(f"🎵 **Starting:** {title}")

        await player.start_if_needed()

    except Exception as exc:
        log.exception("Play failed")
        await status.edit_text(f"❌ `{str(exc)[:900]}`")


@bot.on_message(filters.command("pause"))
async def pause_cmd(_, message: Message):
    try:
        await get_player(message.chat.id).pause()
        await message.reply_text("⏸ **Paused**")
    except Exception as exc:
        await message.reply_text(f"❌ `{exc}`")


@bot.on_message(filters.command("resume"))
async def resume_cmd(_, message: Message):
    try:
        await get_player(message.chat.id).resume()
        await message.reply_text("▶️ **Resumed**")
    except Exception as exc:
        await message.reply_text(f"❌ `{exc}`")


@bot.on_message(filters.command("skip"))
async def skip_cmd(_, message: Message):
    try:
        title = await get_player(message.chat.id).skip()
        if title:
            await message.reply_text(f"⏭ **Skipped**\n🎵 **Next:** {title}")
        else:
            await message.reply_text("⏭ Queue finished.")
    except Exception as exc:
        await message.reply_text(f"❌ `{exc}`")


@bot.on_message(filters.command(["stop", "leave"]))
async def stop_cmd(_, message: Message):
    try:
        await get_player(message.chat.id).stop()
        await message.reply_text("⏹ **Stopped and left the voice chat.**")
    except Exception as exc:
        await message.reply_text(f"❌ `{exc}`")


@bot.on_message(filters.command("queue"))
async def queue_cmd(_, message: Message):
    await message.reply_text(get_player(message.chat.id).queue_text())


@bot.on_message(filters.command("now"))
async def now_cmd(_, message: Message):
    await message.reply_text(get_player(message.chat.id).now_text())


@bot.on_message(filters.command("volume"))
async def volume_cmd(_, message: Message):
    parts = message.text.split()
    if len(parts) != 2:
        return await message.reply_text("❌ Usage: `/volume 1-200`")

    try:
        value = int(parts[1])
    except ValueError:
        return await message.reply_text("❌ Volume must be a number.")

    if not 1 <= value <= 200:
        return await message.reply_text("❌ Volume must be between 1 and 200.")

    try:
        await get_player(message.chat.id).set_volume(value)
        await message.reply_text(f"🔊 Volume: **{value}%**")
    except Exception as exc:
        await message.reply_text(f"❌ `{exc}`")


async def main():
    log.info("Starting command bot...")
    await bot.start()

    log.info("Starting assistant user account...")
    await assistant.start()

    log.info("Starting PyTgCalls...")
    await calls.start()

    me = await assistant.get_me()
    log.info("Voice assistant logged in as %s (%s)", me.first_name, me.id)

    print("🎵 Mahabub Music Bot is running.")

    try:
        await asyncio.Event().wait()
    finally:
        await calls.stop()
        await assistant.stop()
        await bot.stop()


if __name__ == "__main__":
    asyncio.run(main())
