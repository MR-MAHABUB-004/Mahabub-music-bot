import asyncio
import os
import re
from dataclasses import dataclass
from typing import Optional
import yt_dlp
from pytgcalls import PyTgCalls
from pytgcalls.types import AudioPiped
from pytgcalls import idle

@dataclass
class Track:
    query: str
    title: str
    url: str
    duration: int = 0
    requester: int = 0

class MusicPlayer:
    def __init__(self, chat_id, app):
        self.chat_id = chat_id
        self.app = app
        self.call = PyTgCalls(app)
        self.queue = []
        self.current: Optional[Track] = None
        self.started = False
        self.volume = 100
        self.lock = asyncio.Lock()

    async def _search(self, query):
        opts = {
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
            "format": "bestaudio/best",
            "skip_download": True,
            "extract_flat": False,
        }
        loop = asyncio.get_running_loop()
        def work():
            with yt_dlp.YoutubeDL(opts) as ydl:
                data = ydl.extract_info(
                    query if re.match(r"https?://", query) else f"ytsearch1:{query}",
                    download=False,
                )
                if "entries" in data:
                    data = next((x for x in data["entries"] if x), None)
                if not data:
                    raise RuntimeError("Song not found")
                # Refresh the direct media URL immediately before playback.
                return data
        data = await loop.run_in_executor(None, work)
        title = data.get("title", "Unknown")
        webpage = data.get("webpage_url") or data.get("original_url")
        duration = int(data.get("duration") or 0)
        if not webpage and data.get("url"):
            webpage = data["url"]
        if not webpage:
            raise RuntimeError("Could not obtain media URL")
        # Resolve a fresh audio URL for streaming.
        def resolve():
            with yt_dlp.YoutubeDL({
                "quiet": True, "no_warnings": True, "noplaylist": True,
                "format": "bestaudio/best", "skip_download": True
            }) as ydl:
                d=ydl.extract_info(webpage, download=False)
                return d.get("url")
        media_url = await loop.run_in_executor(None, resolve)
        if not media_url:
            raise RuntimeError("Could not obtain audio stream")
        return Track(query, title, media_url, duration)

    async def add(self, query, requester=0):
        track = await self._search(query)
        track.requester = requester
        async with self.lock:
            self.queue.append(track)
        return track.title

    async def start_if_needed(self):
        async with self.lock:
            if self.started or not self.queue:
                return
            self.started = True
        await self._play_next()

    async def _play_next(self):
        async with self.lock:
            if not self.queue:
                self.current = None
                self.started = False
                try:
                    await self.call.leave_group_call(self.chat_id)
                except Exception:
                    pass
                return
            self.current = self.queue.pop(0)
            track = self.current

        try:
            # AudioPiped consumes a direct audio URL and lets Telegram receive
            # the stream without downloading the complete file first.
            await self.call.join_group_call(
                self.chat_id,
                AudioPiped(track.url)
            )
        except Exception:
            async with self.lock:
                self.queue.insert(0, track)
                self.current = None
                self.started = False
            raise

    async def pause(self):
        await self.call.pause_playout(self.chat_id)

    async def resume(self):
        await self.call.resume_playout(self.chat_id)

    async def skip(self):
        await self.call.leave_group_call(self.chat_id)
        async with self.lock:
            old = self.current
            self.current = None
        await self._play_next()
        return self.current.title if self.current else None

    async def stop(self):
        try:
            await self.call.leave_group_call(self.chat_id)
        except Exception:
            pass
        async with self.lock:
            self.queue.clear()
            self.current = None
            self.started = False

    async def set_volume(self, value):
        self.volume = value
        # PyTgCalls volume APIs vary by installed release. Keeping the value
        # here avoids breaking playback across versions.
        return value

    def now_text(self):
        if not self.current:
            return "🎵 Nothing is playing."
        return f"🎵 **Now Playing**\n\n{self.current.title}"

    def queue_text(self):
        if not self.current and not self.queue:
            return "📭 Queue is empty."
        lines=[]
        if self.current:
            lines.append(f"▶️ **Now:** {self.current.title}")
        for i,t in enumerate(self.queue[:20], 1):
            lines.append(f"{i}. {t.title}")
        if len(self.queue)>20:
            lines.append(f"... and {len(self.queue)-20} more")
        return "🎶 **Queue**\n\n" + "\n".join(lines)
