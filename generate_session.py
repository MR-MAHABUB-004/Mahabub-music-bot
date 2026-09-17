from pyrogram import Client
from config import API_ID, API_HASH

print("Telegram User Session Generator")
print("Use the phone number of the USER account that will join voice chats.")

with Client(
    "session_generator",
    api_id=API_ID,
    api_hash=API_HASH,
    in_memory=True,
) as app:
    print("\nYour SESSION_STRING:\n")
    print(app.export_session_string())
    print("\nCopy it to Render as SESSION_STRING.")
