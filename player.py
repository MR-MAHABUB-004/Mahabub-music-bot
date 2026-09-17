import asyncio
import os
import re
from dataclasses import dataclass
from typing import Optional

import yt_dlp
from pytgcalls.types import MediaStream

from config import COOKIES_FILE


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

    # YouTube keeps changing which "client" is allowed to fetch
    # playable URLs without a PO Token / sign-in wall. Rather than
    # hard-coding one client (which breaks again in a few months),
    # try several, in order, and use whichever one actually returns
    # a usable stream.
    #   - web_safari: serves HLS (m3u8) formats, no PO Token today
    #   - tv: no PO Token required, but formats are DRM'd without
    #     cookies from a logged-in/guest session
    #   - android: no sign-in wall for most videos, but audio-only
    #     formats can 403 without a PO Token
    #   - web (+cookies, if provided): last resort
    _CLIENT_ATTEMPTS = [
        ["web_safari"],
        ["tv"],
        ["android"],
        ["web"],
    ]

    def _base_options(self) -> dict:

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

        # If a cookies file is present, use it. Required for the
        # "tv" client to unlock non-DRM formats, and helps every
        # other client avoid the sign-in wall too.
        if COOKIES_FILE and os.path.isfile(COOKIES_FILE):
            options["cookiefile"] = COOKIES_FILE

        return options


    @staticmethod
    def _best_media_url(info: dict) -> Optional[str]:

        # yt-dlp already picked a winning format.
        media_url = info.get("url")

        if media_url:
            return media_url

        formats = info.get("formats", []) or []

        def has_url(f):
            return bool(f.get("url"))

        # Prefer real audio-only formats.
        audio_only = [
            f for f in formats
            if has_url(f)
            and f.get("vcodec") in (None, "none")
            and f.get("acodec") not in (None, "none")
        ]

        # Otherwise accept any format with a playable url
        # (muxed audio+video is fine, ffmpeg only needs the URL).
        any_playable = [
            f for f in formats
            if has_url(f)
            and f.get("acodec") not in (None, "none")
        ]

        candidates = audio_only or any_playable

        if not candidates:
            return None

        candidates.sort(
            key=lambda f: (f.get("abr") or f.get("tbr") or 0),
            reverse=True,
        )

        return candidates[0]["url"]


    async def _extract(self, query: str) -> Track:

        loop = asyncio.get_running_loop()


        def extract():

            target = query

            if not re.match(
                r"^https?://",
                query,
                re.IGNORECASE
            ):
                target = f"ytsearch1:{query}"

            last_error: Optional[Exception] = None

            for client in self._CLIENT_ATTEMPTS:

                options = self._base_options()
                options["extractor_args"] = {
                    "youtube": {"player_client": client}
                }

                try:

                    with yt_dlp.YoutubeDL(options) as ydl:

                        info = ydl.extract_info(
                            target,
                            download=False,
                        )

                        if info and info.get("entries"):
                            info = next(
                                (e for e in info["entries"] if e),
                                None,
                            )

                        if not info:
                            last_error = RuntimeError(
                                "Song not found."
                            )
                            continue

                        # Search results (and some client
                        # responses) come back "flat", without
                        # format info. Re-resolve by URL to get
                        # full format data if needed.
                        fresh = info

                        if not fresh.get("formats") and not fresh.get("url"):

                            webpage_url = (
                                fresh.get("webpage_url")
                                or fresh.get("original_url")
                            )

                            if webpage_url:
                                fresh = ydl.extract_info(
                                    webpage_url,
                                    download=False,
                                )

                        media_url = self._best_media_url(fresh)

                        if not media_url:
                            last_error = RuntimeError(
                                f"No playable stream from "
                                f"'{client[0]}' client."
                            )
                            continue

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

                except Exception as exc:
                    last_error = exc
                    continue

            raise RuntimeError(
                "Could not obtain audio stream. "
                f"Last error: {last_error}"
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
