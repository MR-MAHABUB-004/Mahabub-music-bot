import os
import sys
from pyrogram import Client


# ==============================
# Telegram API Credentials
# ==============================

API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")


# ==============================
# Check API credentials
# ==============================

if not API_ID or not API_HASH:
    print("❌ API_ID অথবা API_HASH পাওয়া যায়নি!")
    print()
    print("আগে Termux-এ চালাও:")
    print()
    print('export API_ID="YOUR_API_ID"')
    print('export API_HASH="YOUR_API_HASH"')
    print()
    print("তারপর আবার:")
    print("python generate_session.py")
    sys.exit(1)


try:
    API_ID = int(API_ID)
except ValueError:
    print("❌ API_ID অবশ্যই number হতে হবে!")
    sys.exit(1)


# ==============================
# Session Generator
# ==============================

print()
print("=" * 60)
print("        🔐 MAHABUB MUSIC BOT")
print("        Telegram Session Generator")
print("=" * 60)
print()
print("এই session আপনার USER ACCOUNT-এর জন্য তৈরি হবে।")
print("এই account-টাই Voice Chat-এ join করবে।")
print()
print("⚠️ SESSION_STRING কাউকে share করবেন না!")
print()


app = Client(
    "mahabub_user_session",
    api_id=API_ID,
    api_hash=API_HASH,
    in_memory=True
)


try:
    print("🔄 Telegram-এ connecting...")
    print()

    app.start()

    print()
    print("=" * 60)
    print("✅ LOGIN SUCCESSFUL")
    print("=" * 60)
    print()

    session_string = app.export_session_string()

    print("🔑 YOUR SESSION_STRING:")
    print()
    print(session_string)
    print()

    print("=" * 60)
    print("⚠️ IMPORTANT")
    print("=" * 60)
    print("এই SESSION_STRING কাউকে দিবে না।")
    print("Render-এর Environment
