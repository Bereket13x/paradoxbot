import asyncio
import logging
from telethon import TelegramClient
from telethon.sessions import StringSession
from config.config import Config
from utils.thanos import thanos_protect
from startup.startup import start_bot

logging.basicConfig(
    format='[%(levelname) 5s/%(asctime)s] %(name)s: %(message)s',
    level=logging.WARNING
)

if __name__ == "__main__":
    if Config.STRING_SESSION == "INVALID_SESSION" or Config.API_ID == 0 or Config.API_HASH == "INVALID_API_HASH":
        print("\n" + "="*50)
        print("[CRITICAL ERROR] MISSING ENVIRONMENT VARIABLES")
        print("="*50)
        print("Please ensure you have set the following in your deployment dashboard:")
        print("1. API_ID")
        print("2. API_HASH")
        print("3. ELITE_SESSION")
        print("="*50 + "\n")
        exit(1)

    # Initialize Telegram client
    eliteses = thanos_protect(Config.STRING_SESSION)
    client = TelegramClient(
        StringSession(eliteses),
        Config.API_ID,
        Config.API_HASH
    )

    with client:
        client.loop.run_until_complete(start_bot(client))
