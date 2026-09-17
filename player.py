import asyncio
import re
from dataclasses import dataclass
from typing import Optional

import yt_dlp
from pytgcalls.types import MediaStream


@dataclass
class Track:
    query: str
    title: str
    url: str
    duration: int = 0
    requester: int = 0


class MusicPlayer:
    def __init__(self, chat_id: int, calls):
        self.chat_id = chat_id
        self.calls = calls
        self.queue: list[Track] = []
        self.current: Optional[Track] = None
        self.playing = False
        self.paused = False
        self.volume = 100
        self.lock = asyncio.Lock()

    async def _extract(self, query: str) -> Track:
        options = {
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
            "format": "bestaudio/best",
            "skip_download": True,
            "source_address": "0.0.0.0",
        }

        loop = asyncio.get_running_loop()

        def extract():
            target = query
            if not re.match(r"https?://", query):
                target = f"ytsearch1:{query}"

            with yt_dlp.YoutubeDL(options) as ydl:
                info = ydl.extract_info(target, download=False)

                if info.get("entries"):
                    info = next(
                        (entry for entry in info["entries"] if entry),
                        None,
                    )

                if not info:
                    raise RuntimeError("Song not found.")

                webpage_url = info.get("webpage_url") or info.get("original_url")
                if not webpage_url:
                    raise RuntimeError("Could not resolve YouTube URL.")

                # Resolve a fresh direct media URL.
                fresh = ydl.extract_info(webpage_url, download=False)
                media_url = fresh.get("url")

                if not media_url:
                    raise RuntimeError("Could not obtain audio stream.")

                return Track(
                    query=query,
                    title=fresh.get("title") or info.get("title") or "Unknown",
                    url=media_url,
                    duration=int(fresh.get("duration") or 0),
                )

        return await loop.run_in_executor(None, extract)

    async def add(self, query: str, requester: int = 0) -> str:
        track = await self._extract(query)
        track.requester = requester

        async with self.lock:
            self.queue.append(track)

        return track.title

    async def start_if_needed(self):
        async with self.lock:
            if self.playing or not self.queue:
                return
            self.playing = True

        await self._play_next()

    async def _play_next(self):
        async with self.lock:
            if not self.queue:
                self.current = None
                self.playing = False
                self.paused = False
                try:
                    await self.calls.leave_call(self.chat_id)
                except Exception:
                    pass
                return

            self.current = self.queue.pop(0)
            track = self.current
            self.paused = False

        try:
            # Current PyTgCalls uses MediaStream, not the old AudioPiped API.
            stream = MediaStream(
                track.url,
                video_flags=MediaStream.Flags.IGNORE,
            )

            await self.calls.play(self.chat_id, stream)
            await self.calls.change_volume_call(self.chat_id, self.volume)

        except Exception:
            async with self.lock:
                self.queue.insert(0, track)
                self.current = None
                self.playing = False
            raise

    async def on_stream_end(self):
        await self._play_next()

    async def pause(self):
        if not self.current:
            raise RuntimeError("Nothing is playing.")

        await self.calls.pause(self.chat_id)
        self.paused = True

    async def resume(self):
        if not self.current:
            raise RuntimeError("Nothing is playing.")

        await self.calls.resume(self.chat_id)
        self.paused = False

    async def skip(self) -> Optional[str]:
        if not self.current:
            raise RuntimeError("Nothing is playing.")

        await self.calls.leave_call(self.chat_id)

        async with self.lock:
            self.current = None

        await self._play_next()
        return self.current.title if self.current else None

    async def stop(self):
        try:
            await self.calls.leave_call(self.chat_id)
        except Exception:
            pass

        async with self.lock:
            self.queue.clear()
            self.current = None
            self.playing = False
            self.paused = False

    async def set_volume(self, value: int):
        self.volume = value

        if self.current:
            await self.calls.change_volume_call(self.chat_id, value)

    def now_text(self) -> str:
        if not self.current:
            return "🎵 **Nothing is playing.**"

        return f"🎵 **Now Playing**\n\n{self.current.title}"

    def queue_text(self) -> str:
        if not self.current and not self.queue:
            return "📭 **Queue is empty.**"

        lines = []

        if self.current:
            lines.append(f"▶️ **Now:** {self.current.title}")

        for index, track in enumerate(self.queue[:20], 1):
            lines.append(f"{index}. {track.title}")

        if len(self.queue) > 20:
            lines.append(f"... +{len(self.queue) - 20} more")

        return "🎶 **Queue**\n\n" + "\n".join(lines)
