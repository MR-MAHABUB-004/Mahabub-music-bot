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

        self.start_lock = asyncio.Lock()


    # ========================================================
    # Extract YouTube audio
    # ========================================================

    async def _extract(self, query: str) -> Track:

        options = {
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,

            # Audio only
            "format": "bestaudio/best",

            "skip_download": True,

            "source_address": "0.0.0.0",

            # Better compatibility
            "nocheckcertificate": True,
        }

        loop = asyncio.get_running_loop()


        def extract():

            target = query

            if not re.match(
                r"^https?://",
                query,
                re.IGNORECASE
            ):
                target = f"ytsearch1:{query}"


            with yt_dlp.YoutubeDL(
                options
            ) as ydl:

                info = ydl.extract_info(
                    target,
                    download=False
                )


                if info.get("entries"):

                    info = next(
                        (
                            entry
                            for entry in info["entries"]
                            if entry
                        ),
                        None
                    )


                if not info:

                    raise RuntimeError(
                        "Song not found."
                    )


                webpage_url = (
                    info.get("webpage_url")
                    or info.get("original_url")
                    or info.get("url")
                )


                if not webpage_url:

                    raise RuntimeError(
                        "Could not resolve YouTube URL."
                    )


                # Resolve fresh direct audio URL
                fresh = ydl.extract_info(
                    webpage_url,
                    download=False
                )


                media_url = fresh.get("url")


                if not media_url:

                    # Sometimes formats contains the URL
                    formats = fresh.get(
                        "formats",
                        []
                    )

                    audio_formats = [
                        f
                        for f in formats
                        if f.get("url")
                        and (
                            f.get("acodec")
                            not in (
                                None,
                                "none"
                            )
                        )
                    ]


                    if audio_formats:

                        audio_formats.sort(
                            key=lambda x:
                            (
                                x.get("abr")
                                or 0
                            ),
                            reverse=True
                        )

                        media_url = (
                            audio_formats[0]["url"]
                        )


                if not media_url:

                    raise RuntimeError(
                        "Could not obtain audio stream."
                    )


                return Track(
                    query=query,

                    title=(
                        fresh.get("title")
                        or info.get("title")
                        or "Unknown"
                    ),

                    url=media_url,

                    duration=int(
                        fresh.get("duration")
                        or info.get("duration")
                        or 0
                    ),
                )


        return await loop.run_in_executor(
            None,
            extract
        )


    # ========================================================
    # Add song
    # ========================================================

    async def add(
        self,
        query: str,
        requester: int = 0
    ) -> str:

        track = await self._extract(
            query
        )

        track.requester = requester


        async with self.lock:

            self.queue.append(
                track
            )


        return track.title


    # ========================================================
    # Start player
    # ========================================================

    async def start_if_needed(self):

        async with self.start_lock:

            async with self.lock:

                if self.playing:
                    return

                if not self.queue:
                    return

                self.playing = True

            await self._play_next()


    # ========================================================
    # Play next
    # ========================================================

    async def _play_next(self):

        async with self.lock:

            if not self.queue:

                self.current = None
                self.playing = False
                self.paused = False

                should_leave = True

            else:

                self.current = self.queue.pop(0)

                track = self.current

                self.paused = False

                should_leave = False


        if should_leave:

            try:
                await self.calls.leave_call(
                    self.chat_id
                )
            except Exception:
                pass

            return


        try:

            stream = MediaStream(
                track.url,

                video_flags=(
                    MediaStream.Flags.IGNORE
                ),
            )


            await self.calls.play(
                self.chat_id,
                stream
            )


            try:

                await self.calls.change_volume_call(
                    self.chat_id,
                    self.volume
                )

            except Exception:

                # Some versions may not support
                # volume immediately after play.
                pass


        except Exception:

            async with self.lock:

                self.queue.insert(
                    0,
                    track
                )

                self.current = None
                self.playing = False
                self.paused = False

            raise


    # ========================================================
    # Stream ended
    # ========================================================

    async def on_stream_end(self):

        async with self.start_lock:

            await self._play_next()


    # ========================================================
    # Pause
    # ========================================================

    async def pause(self):

        if not self.current:

            raise RuntimeError(
                "Nothing is playing."
            )


        await self.calls.pause(
            self.chat_id
        )

        self.paused = True


    # ========================================================
    # Resume
    # ========================================================

    async def resume(self):

        if not self.current:

            raise RuntimeError(
                "Nothing is playing."
            )


        await self.calls.resume(
            self.chat_id
        )

        self.paused = False


    # ========================================================
    # Skip
    # ========================================================

    async def skip(self) -> Optional[str]:

        if not self.current:

            raise RuntimeError(
                "Nothing is playing."
            )


        try:

            await self.calls.leave_call(
                self.chat_id
            )

        except Exception:

            pass


        async with self.lock:

            self.current = None


        await self._play_next()


        return (
            self.current.title
            if self.current
            else None
        )


    # ========================================================
    # Stop
    # ========================================================

    async def stop(self):

        try:

            await self.calls.leave_call(
                self.chat_id
            )

        except Exception:

            pass


        async with self.lock:

            self.queue.clear()

            self.current = None

            self.playing = False
            self.paused = False


    # ========================================================
    # Volume
    # ========================================================

    async def set_volume(
        self,
        value: int
    ):

        value = max(
            1,
            min(200, int(value))
        )

        self.volume = value


        if self.current:

            await self.calls.change_volume_call(
                self.chat_id,
                value
            )


    # ========================================================
    # Now Playing
    # ========================================================

    def now_text(self) -> str:

        if not self.current:

            return (
                "🎵 **Nothing is playing.**"
            )


        return (
            "🎵 **Now Playing**\n\n"
            f"🎶 {self.current.title}"
        )


    # ========================================================
    # Queue
    # ========================================================

    def queue_text(self) -> str:

        if (
            not self.current
            and not self.queue
        ):

            return (
                "📭 **Queue is empty.**"
            )


        lines = []


        if self.current:

            lines.append(
                f"▶️ **Now:** "
                f"{self.current.title}"
            )


        for index, track in enumerate(
            self.queue[:20],
            1
        ):

            lines.append(
                f"{index}. {track.title}"
            )


        if len(self.queue) > 20:

            lines.append(
                f"... +"
                f"{len(self.queue) - 20}"
                f" more"
            )


        return (
            "🎶 **Queue**\n\n"
            + "\n".join(lines)
        )
