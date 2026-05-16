# =============================================================================
#  CipherElite Userbot Plugin
#
#  Plugin Name:    tools
#  Author:         CipherElite Dev (@rishabhops)
#  Repository:     https://github.com/rishabhops/CipherElite
#
#  License:        MIT
#
#  IMPORTANT:
#    • If you copy, fork, or include this plugin in your own bot,
#      you MUST keep this header intact.
#    • You MUST give proper credit to the CipherElite Userbot author:
#        – GitHub:    https://github.com/rishabhops/CipherElite
#        – Telegram:  @thanosceo
#
#  Thank you for respecting open-source software!
# =============================================================================
from telethon import events
import asyncio
import re
import time
import platform
import psutil
from datetime import datetime
from plugins.bot import add_handler
from utils.utils import CipherElite
from utils.decorators import rishabh

def init(client_instance):
    commands = [
        ".id - Get user/chat ID",
        ".dc - Get DC info",
        ".sd <time> <text> - Self-destruct message (e.g. .sd 10s Secret msg)"
    ]
    description = "Useful utility tools for your userbot 🔧"
    add_handler("tools", commands, description)

async def register_commands():

    @CipherElite.on(events.NewMessage(pattern=r"\.id"))
    @rishabh()
    async def get_id(event):
        if event.is_reply:
            msg = await event.get_reply_message()
            user_id = msg.sender_id
            chat_id = event.chat_id
            await event.reply(f" **User ID:** `{user_id}`\n **Chat ID:** `{chat_id}`")
        else:
            await event.reply(f" **Chat ID:** `{event.chat_id}`")



    @CipherElite.on(events.NewMessage(pattern=r"\.dc"))
    @rishabh()
    async def dc(event):
        if event.is_reply:
            msg = await event.get_reply_message()
            user = await event.client.get_entity(msg.sender_id)
        else:
            user = await event.client.get_me()
        
        dc_id = user.photo.dc_id if user.photo else "No profile photo"
        await event.reply(f"🌐 **DC ID:** `{dc_id}`")

    @CipherElite.on(events.NewMessage(pattern=r"^\.sd(?:\s+(\d+[smh]))?(?:\s+([\s\S]+))?", outgoing=True))
    @rishabh()
    async def self_destruct(event):
        time_arg = event.pattern_match.group(1)
        text = event.pattern_match.group(2)

        if not time_arg or not text:
            return await event.edit(
                "💀 **Self-Destruct Messages**\n\n"
                "**Usage:** `.sd <time> <message>`\n\n"
                "**Examples:**\n"
                "`.sd 10s This vanishes in 10 seconds`\n"
                "`.sd 5m Gone in 5 minutes`\n"
                "`.sd 1h Disappears in 1 hour`"
            )

        # Parse time
        amount = int(time_arg[:-1])
        unit = time_arg[-1]
        if unit == "s":
            seconds = amount
        elif unit == "m":
            seconds = amount * 60
        elif unit == "h":
            seconds = amount * 3600
        else:
            seconds = amount

        # Format display time
        if seconds < 60:
            display = f"{seconds}s"
        elif seconds < 3600:
            display = f"{seconds // 60}m"
        else:
            display = f"{seconds // 3600}h"

        # Send the message with a subtle indicator
        await event.edit(f"{text}\n\n`💀 This message self-destructs in {display}`")

        # Wait and destroy
        await asyncio.sleep(seconds)
        try:
            await event.delete()
        except Exception:
            pass


# Initialize start time
START_TIME = datetime.now()
