import asyncio
import logging
from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.errors import RPCError
from config import API_ID, API_HASH, BOT_TOKEN
from player import MusicPlayer

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("MahabubMusicBot")

app = Client(
    "mahbub_music_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
)

players = {}

def get_player(chat_id):
    if chat_id not in players:
        players[chat_id] = MusicPlayer(chat_id, app)
    return players[chat_id]

@app.on_message(filters.command("start"))
async def start(_, m: Message):
    await m.reply_text(
        "🎵 **Mahabub Music Bot**\n\n"
        "Fast Telegram Voice Chat Music Player.\n\n"
        "Use `/play song name` to start.\n"
        "`/pause` `/resume` `/skip` `/stop` `/queue` `/now` `/volume 1-100`"
    )

@app.on_message(filters.command(["play", "p"]))
async def play(_, m: Message):
    query = m.text.split(maxsplit=1)[1] if len(m.text.split(maxsplit=1)) > 1 else None
    if not query:
        return await m.reply_text("❌ Usage: `/play song name or YouTube URL`")
    msg = await m.reply_text("🔎 Searching...")
    try:
        player = get_player(m.chat.id)
        title = await player.add(query, m.from_user.id if m.from_user else 0)
        await msg.edit_text(f"🎵 **Queued:** {title}")
        await player.start_if_needed()
    except Exception as e:
        log.exception("play failed")
        await msg.edit_text(f"❌ Error: `{str(e)[:800]}`")

@app.on_message(filters.command("pause"))
async def pause(_, m: Message):
    try:
        await get_player(m.chat.id).pause()
        await m.reply_text("⏸ Paused")
    except Exception as e:
        await m.reply_text(f"❌ {e}")

@app.on_message(filters.command("resume"))
async def resume(_, m: Message):
    try:
        await get_player(m.chat.id).resume()
        await m.reply_text("▶️ Resumed")
    except Exception as e:
        await m.reply_text(f"❌ {e}")

@app.on_message(filters.command("skip"))
async def skip(_, m: Message):
    try:
        title = await get_player(m.chat.id).skip()
        await m.reply_text(f"⏭ Skipped.\n🎵 Next: **{title}**" if title else "⏭ Queue finished.")
    except Exception as e:
        await m.reply_text(f"❌ {e}")

@app.on_message(filters.command("stop"))
async def stop(_, m: Message):
    try:
        await get_player(m.chat.id).stop()
        await m.reply_text("⏹ Stopped and left the voice chat.")
    except Exception as e:
        await m.reply_text(f"❌ {e}")

@app.on_message(filters.command("leave"))
async def leave(_, m: Message):
    try:
        await get_player(m.chat.id).stop()
        await m.reply_text("👋 Left the voice chat.")
    except Exception as e:
        await m.reply_text(f"❌ {e}")

@app.on_message(filters.command("queue"))
async def queue(_, m: Message):
    q = get_player(m.chat.id).queue_text()
    await m.reply_text(q)

@app.on_message(filters.command("now"))
async def now(_, m: Message):
    await m.reply_text(get_player(m.chat.id).now_text())

@app.on_message(filters.command("volume"))
async def volume(_, m: Message):
    parts=m.text.split()
    if len(parts)!=2 or not parts[1].isdigit() or not 1 <= int(parts[1]) <= 100:
        return await m.reply_text("❌ Usage: `/volume 1-100`")
    try:
        await get_player(m.chat.id).set_volume(int(parts[1]))
        await m.reply_text(f"🔊 Volume set to {parts[1]}%")
    except Exception as e:
        await m.reply_text(f"❌ {e}")

if __name__ == "__main__":
    print("🎵 Mahabub Music Bot starting...")
    app.run()
