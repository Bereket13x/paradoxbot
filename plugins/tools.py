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
import os
import re
import time
import textwrap
import tempfile
import platform
import psutil
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from io import BytesIO
from plugins.bot import add_handler
from utils.utils import CipherElite
from utils.decorators import rishabh

TEMP_DIR = tempfile.gettempdir()

def init(client_instance):
    commands = [
        ".id - Get user/chat ID",
        ".dc - Get DC info",
        ".sd <time> <text> - Self-destruct message (e.g. .sd 10s Secret msg)",
        ".q - Reply to a message to create a stunning quote card"
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

    @CipherElite.on(events.NewMessage(pattern=r"^\.q$", outgoing=True))
    @rishabh()
    async def quote_card(event):
        if not event.is_reply:
            return await event.edit("❌ **Reply to a message to create a quote card!**")

        reply = await event.get_reply_message()
        msg_text = reply.text or reply.message
        if not msg_text:
            return await event.edit("❌ **That message has no text.**")

        await event.edit("🎨 **Creating quote card...**")

        try:
            # Get sender info
            sender = await reply.get_sender()
            first = sender.first_name or ""
            last = sender.last_name or ""
            sender_name = f"{first} {last}".strip() or "Unknown"
            username = f"@{sender.username}" if sender.username else ""

            # Download sender's profile pic
            pfp_img = None
            try:
                pfp_path = await event.client.download_profile_photo(sender, TEMP_DIR)
                if pfp_path:
                    pfp_img = Image.open(pfp_path).convert("RGBA").resize((120, 120))
            except Exception:
                pass

            # ── Card dimensions & colors ─────────────────────────────────
            W, PADDING = 800, 40
            BG_TOP = (15, 15, 35)       # dark navy
            BG_BOT = (30, 10, 50)       # deep purple
            ACCENT = (0, 200, 180)      # teal
            TEXT_COL = (240, 240, 255)   # near-white
            SUB_COL = (160, 160, 200)    # muted lavender
            QUOTE_COL = (0, 200, 180, 60)

            # ── Load font ────────────────────────────────────────────────
            font_path = os.path.join("cipher_assets", "bold.ttf")
            try:
                quote_font = ImageFont.truetype(font_path, 28) if os.path.exists(font_path) else ImageFont.load_default()
                name_font = ImageFont.truetype(font_path, 22) if os.path.exists(font_path) else ImageFont.load_default()
                small_font = ImageFont.truetype(font_path, 16) if os.path.exists(font_path) else ImageFont.load_default()
            except Exception:
                quote_font = ImageFont.load_default()
                name_font = ImageFont.load_default()
                small_font = ImageFont.load_default()

            # ── Wrap text ────────────────────────────────────────────────
            wrapped = textwrap.fill(msg_text, width=45)
            lines = wrapped.split("\n")
            line_height = 36
            text_block_h = len(lines) * line_height

            # ── Calculate card height ────────────────────────────────────
            H = PADDING + 140 + text_block_h + 60 + PADDING
            H = max(H, 300)

            # ── Create gradient background ───────────────────────────────
            card = Image.new("RGBA", (W, H), BG_TOP)
            draw = ImageDraw.Draw(card)
            for y in range(H):
                ratio = y / H
                r = int(BG_TOP[0] + (BG_BOT[0] - BG_TOP[0]) * ratio)
                g = int(BG_TOP[1] + (BG_BOT[1] - BG_TOP[1]) * ratio)
                b = int(BG_TOP[2] + (BG_BOT[2] - BG_TOP[2]) * ratio)
                draw.line([(0, y), (W, y)], fill=(r, g, b))

            draw = ImageDraw.Draw(card)

            # ── Accent line on left ──────────────────────────────────────
            draw.rectangle([PADDING - 8, PADDING, PADDING - 3, H - PADDING], fill=ACCENT)

            # ── Big quote mark ───────────────────────────────────────────
            try:
                big_q = ImageFont.truetype(font_path, 120) if os.path.exists(font_path) else None
            except Exception:
                big_q = None
            if big_q:
                draw.text((W - 140, PADDING - 20), "“", font=big_q, fill=(*ACCENT[:3], 40))

            # ── Profile picture (circular mask) ──────────────────────────
            pfp_y = PADDING + 10
            pfp_x = PADDING + 12
            if pfp_img:
                mask = Image.new("L", (120, 120), 0)
                mask_draw = ImageDraw.Draw(mask)
                mask_draw.ellipse([0, 0, 119, 119], fill=255)
                card.paste(pfp_img, (pfp_x, pfp_y), mask)
                # Ring around PFP
                draw.ellipse([pfp_x-2, pfp_y-2, pfp_x+121, pfp_y+121], outline=ACCENT, width=2)
            else:
                # Draw placeholder circle
                draw.ellipse([pfp_x, pfp_y, pfp_x+119, pfp_y+119], fill=(50, 50, 80), outline=ACCENT, width=2)
                draw.text((pfp_x + 35, pfp_y + 35), sender_name[0].upper(), font=quote_font, fill=ACCENT)

            # ── Sender name & username ────────────────────────────────────
            name_x = pfp_x + 140
            draw.text((name_x, pfp_y + 25), sender_name, font=name_font, fill=TEXT_COL)
            if username:
                draw.text((name_x, pfp_y + 55), username, font=small_font, fill=SUB_COL)

            # ── Quote text ───────────────────────────────────────────────
            text_y = pfp_y + 140
            for line in lines:
                draw.text((PADDING + 12, text_y), line, font=quote_font, fill=TEXT_COL)
                text_y += line_height

            # ── Bottom watermark ─────────────────────────────────────────
            draw.text((W - 160, H - PADDING - 10), "⟨ PARADOX ⟩", font=small_font, fill=SUB_COL)

            # ── Save and send ────────────────────────────────────────────
            out_path = os.path.join(TEMP_DIR, "paradox_quote.png")
            card.convert("RGB").save(out_path, "PNG")

            await event.client.send_file(
                event.chat_id,
                out_path,
                reply_to=reply.id,
            )
            await event.delete()

            # Cleanup
            os.remove(out_path)
            if pfp_path and os.path.exists(pfp_path):
                os.remove(pfp_path)

        except Exception as e:
            await event.edit(f"❌ **Error:** `{e}`")


# Initialize start time
START_TIME = datetime.now()
