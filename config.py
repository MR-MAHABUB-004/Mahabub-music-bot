import os

from dotenv import load_dotenv

load_dotenv()

API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
SESSION_STRING = os.getenv("SESSION_STRING", "")

# Path to a Netscape-format cookies.txt used by yt-dlp to avoid
# YouTube's "Sign in to confirm you're not a bot" check.
# Leave the file missing/empty to run without cookies.
COOKIES_FILE = os.getenv("COOKIES_FILE", "cookies.txt")

# Where downloaded audio files are cached on disk. We download the
# full track before playing it (instead of streaming a live YouTube
# URL), since expiring/PO-Token-gated URLs are what was causing
# "Could not obtain audio stream".
AUDIO_CACHE_DIR = os.getenv("AUDIO_CACHE_DIR", "/tmp/mahabub_audio_cache")

# Soft cap on the cache directory size; oldest files are trimmed
# past this to keep disk usage bounded on small VPS instances.
AUDIO_CACHE_MAX_MB = int(os.getenv("AUDIO_CACHE_MAX_MB", "1000"))

if not API_ID:
    raise RuntimeError("API_ID is missing.")

if not API_HASH:
    raise RuntimeError("API_HASH is missing.")

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is missing.")

if not SESSION_STRING:
    raise RuntimeError(
        "SESSION_STRING is missing. A user account is required for voice chats."
    )
