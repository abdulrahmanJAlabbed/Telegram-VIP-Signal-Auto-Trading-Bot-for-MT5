import asyncio
from telethon import TelegramClient
import logging
import os
from dotenv import load_dotenv

load_dotenv()  # Load environment variables from .env file

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Load credentials from environment variables
API_ID = os.getenv('TELEGRAM_API_ID')
API_HASH = os.getenv('TELEGRAM_API_HASH')
SESSION_NAME = os.getenv('TELEGRAM_SESSION_NAME', 'session')  # Default session name

if not API_ID or not API_HASH:
    logging.error("Missing TELEGRAM_API_ID or TELEGRAM_API_HASH in .env file.")
    exit(1)

async def main():
    client = TelegramClient(SESSION_NAME, API_ID, API_HASH)
    await client.start()  
    logging.info("Listing all accessible channels:")
    async for dialog in client.iter_dialogs():
        if dialog.is_channel:
            username = dialog.entity.username if hasattr(dialog.entity, 'username') else 'None (Private)'
            logging.info(f"Channel Name: {dialog.title}, ID: {dialog.id}, Username: @{username}")

    await client.disconnect()

if __name__ == '__main__':
    asyncio.run(main())