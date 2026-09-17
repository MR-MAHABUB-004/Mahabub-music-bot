import asyncio
import glob
import os
import re
import time
import urllib.request
from dataclasses import dataclass
from typing import Optional

import yt_dlp
from pytgcalls.types import MediaStream

from config import (
    COOKIES_FILE,
    AUDIO_CACHE_DIR,
    AUDIO_CACHE_MAX_MB,
)

os.makedirs(AUDIO_CACHE_DIR, exist_ok=True)


# ============================================================
# YouTube "visitor_data" — this is a per-session ID that
# YouTube's own player fetches from the homepage. Sending it
# with requests makes traffic from a datacenter/VPS IP look
# far less like a bare scraper, which reduces (not eliminates)
# how often the "Sign in to confirm you're not a bot" wall
# shows up. Refreshed every 2 hours, best-effort only.
# ============================================================

_visitor_data: Optional[str] = None
_visitor_data_fetched_at: float = 0.0
_VISITOR_DATA_TTL = 2 * 60 * 60


def _get_visitor_data() -> Optional[str]:

    global _visitor_data, _visitor_data_fetched_at

    now = time.time()

    if (
        _visitor_data
        and (now - _visitor_data_fetched_at) < _VISITOR_DATA_TTL
    ):
        return _visitor_data

    try:
        req = urllib.request.Request(
            "https://www.youtube.com/",
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/131.0.0.0 Safari/537.36"
                )
            },
        )

        with urllib.request.urlopen(req, timeout=10) as resp:
            html = resp.read().decode("utf-8", "ignore")

        match = re.search(r'"visitorData":"([^"]+)"', html)

        if match:
            _visitor_data = match.group(1)
            _visitor_data_fetched_at = now

    except Exception:
        # Best-effort only — fine to proceed without it.
        pass

    return _visitor_data


# ============================================================
# Disk cache housekeeping
# ============================================================

def _trim_cache():

    try:
        files = [
            os.path.join(AUDIO_CACHE_DIR, f)
            for f in os.listdir(AUDIO_CACHE_DIR)
        ]
        files = [f for f in files if os.path.isfile(f)]

        total = sum(os.path.getsize(f) for f in files)
        limit = AUDIO_CACHE_MAX_MB * 1024 * 1024

        if total <= limit:
            return

        # Oldest (by last modified) first.
        files.sort(key=os.path.getmtime)

        for f in files:
            if total <= limit:
                break
            try:
                total -= os.path.getsize(f)
                os.remove(f)
            except OSError:
                pass

    except Exception:
        pass


def _find_cached(video_id: str) -> Optional[str]:

    matches = glob.glob(
        os.path.join(AUDIO_CACHE_DIR, f"{video_id}.*")
    )

    for m in matches:
        if os.path.isfile(m) and os.path.getsize(m) > 0:
            return m

    return None


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
    # playable audio without a PO Token / sign-in wall. Rather than
    # hard-coding one client (which breaks again in a few months),
    # try several, in order, and use whichever one actually works.
    #   - web_safari: serves HLS (m3u8), no PO Token today
    #   - tv: no PO Token required, but needs cookies to avoid DRM
    #   - android: usually no sign-in wall, may 403 on audio-only
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

            "format": "bestaudio/best",

            "source_address": "0.0.0.0",
            "nocheckcertificate": True,

            "outtmpl": os.path.join(
                AUDIO_CACHE_DIR, "%(extractor)s-%(id)s.%(ext)s"
            ),

            # Don't re-download a track we already have cached.
            "overwrites": False,
        }

        if COOKIES_FILE and os.path.isfile(COOKIES_FILE):
            options["cookiefile"] = COOKIES_FILE

        return options

    @staticmethod
    def _downloaded_path(info: dict):

        downloads = info.get("requested_downloads") or []

        if downloads and downloads[0].get("filepath"):
            path = downloads[0]["filepath"]
            if os.path.isfile(path):
                return path

        return None

    async def _extract(self, query: str) -> Track:

        loop = asyncio.get_running_loop()

        def download_via_youtube(target: str):

            last_error = None
            visitor_data = _get_visitor_data()

            for client in self._CLIENT_ATTEMPTS:

                options = self._base_options()

                yt_args = {"player_client": client}
                if visitor_data:
                    yt_args["visitor_data"] = [visitor_data]

                options["extractor_args"] = {"youtube": yt_args}

                try:

                    with yt_dlp.YoutubeDL(options) as ydl:

                        info = ydl.extract_info(
                            target,
                            download=True,
                        )

                        if info and info.get("entries"):
                            info = next(
                                (e for e in info["entries"] if e),
                                None,
                            )

                        if not info:
                            last_error = RuntimeError("Song not found.")
                            continue

                        path = (
                            self._downloaded_path(info)
                            or _find_cached(
                                f"{info.get('extractor', 'youtube')}"
                                f"-{info.get('id', '')}"
                            )
                        )

                        if not path:
                            last_error = RuntimeError(
                                f"Download via '{client[0]}' "
                                f"client produced no file."
                            )
                            continue

                        return Track(
                            query=query,
                            title=info.get("title") or "Unknown",
                            url=path,
                            duration=int(info.get("duration") or 0),
                        )

                except Exception as exc:
                    last_error = exc
                    continue

            raise RuntimeError(str(last_error))

        def download_via_soundcloud(search_query: str):

            options = self._base_options()

            with yt_dlp.YoutubeDL(options) as ydl:

                info = ydl.extract_info(
                    f"scsearch1:{search_query}",
                    download=True,
                )

                if info and info.get("entries"):
                    info = next(
                        (e for e in info["entries"] if e),
                        None,
                    )

                if not info:
                    raise RuntimeError("Song not found on SoundCloud.")

                path = self._downloaded_path(info) or _find_cached(
                    f"{info.get('extractor', 'soundcloud')}"
                    f"-{info.get('id', '')}"
                )

                if not path:
                    raise RuntimeError(
                        "SoundCloud download produced no file."
                    )

                return Track(
                    query=search_query,
                    title=info.get("title") or "Unknown",
                    url=path,
                    duration=int(info.get("duration") or 0),
                )

        def extract():

            is_url = bool(re.match(r"^https?://", query, re.IGNORECASE))
            target = query if is_url else f"ytsearch1:{query}"

            try:
                track = download_via_youtube(target)
                _trim_cache()
                return track

            except Exception as yt_error:

                if is_url:
                    raise RuntimeError(
                        f"Could not obtain audio stream. ({yt_error})"
                    )

                try:
                    track = download_via_soundcloud(query)
                    _trim_cache()
                    return track

                except Exception as sc_error:
                    raise RuntimeError(
                        "Could not obtain audio stream.\n"
                        f"YouTube: {yt_error}\n"
                        f"SoundCloud: {sc_error}"
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
