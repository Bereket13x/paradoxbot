# =============================================================================
#  PARADOX Userbot Plugin
#
#  Plugin Name:    QR Tools
#  Description:    Advanced QR code generator and reader. Create standard,
#                  styled (colored), WiFi, and Crypto QR codes. Read any QR
#                  code from an image.
#  License:        MIT
# =============================================================================

import os
import asyncio
from pathlib import Path
from io import BytesIO

from PIL import Image
from telethon import events
import qrcode
from qrcode.image.styledpil import StyledPilImage
from qrcode.image.styles.colormasks import RadialGradiantColorMask, SolidFillColorMask
from pyzbar.pyzbar import decode

from utils.utils import CipherElite
from utils.decorators import rishabh
from plugins.bot import add_handler

TMP_DIR = Path("/tmp/qrtools")
TMP_DIR.mkdir(parents=True, exist_ok=True)

# ── Plugin Registration ────────────────────────────────────────────────────────

def init(client):
    commands = [
        ".qr <text/url> - Generate a standard QR code",
        ".qr wifi <ssid> <password> - Generate a WiFi QR code",
        ".qr read <reply to image> - Read a QR code from an image",
        ".qr styled <color> <text> - Generate a colored QR code (red, blue, green, gold, pink)",
        ".qr crypto <btc/eth/ltc> <address> - Generate a Crypto payment QR code",
        ".qr help - Show QR tools help",
    ]
    desc = "🧬 QR Tools — Advanced QR code creator and reader"
    add_handler("qrtools", commands, desc)

# ── Helpers ────────────────────────────────────────────────────────────────────

COLORS = {
    "red": (255, 0, 0),
    "blue": (0, 0, 255),
    "green": (0, 255, 0),
    "gold": (255, 215, 0),
    "pink": (255, 20, 147),
}

def generate_qr(data: str, filename: str) -> str:
    """Generate a standard QR code."""
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=4,
    )
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    path = str(TMP_DIR / filename)
    img.save(path)
    return path

def generate_styled_qr(data: str, color_name: str, filename: str) -> str:
    """Generate a colored QR code."""
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=4,
    )
    qr.add_data(data)
    qr.make(fit=True)
    
    color_rgb = COLORS.get(color_name.lower(), (0, 0, 0))
    
    img = qr.make_image(
        image_factory=StyledPilImage,
        color_mask=SolidFillColorMask(front_color=color_rgb)
    )
    path = str(TMP_DIR / filename)
    img.save(path)
    return path

async def read_qr(event) -> str:
    """Read a QR code from a replied image."""
    if not event.is_reply:
        return "❌ Please reply to an image containing a QR code."
    
    reply = await event.get_reply_message()
    if not (reply.photo or reply.document):
         return "❌ The replied message does not contain a valid image."
         
    try:
        data = await event.client.download_media(reply, bytes)
        img = Image.open(BytesIO(data))
        decoded = decode(img)
        
        if not decoded:
            return "❌ No QR code found in the image."
            
        result = "**🔍 QR Code Decoded:**\n\n"
        for obj in decoded:
            result += f"`{obj.data.decode('utf-8')}`\n"
        return result
    except Exception as e:
        return f"❌ Failed to decode image: `{e}`"

# ── Command Handlers ───────────────────────────────────────────────────────────

@CipherElite.on(events.NewMessage(pattern=r"\.qr(?:\s+(.+))?$"))
@rishabh()
async def qr_handler(event):
    args = event.pattern_match.group(1)
    
    if not args:
        await event.reply("❌ Please provide text/URL or use `.qr help` for commands.")
        return
        
    parts = args.split(" ", 1)
    sub = parts[0].lower()
    extra = parts[1] if len(parts) > 1 else ""

    # ── .qr help ───────────────────────────────────────────────────────────────
    if sub == "help":
         text = (
            "🧬 **QR Tools Help**\n"
            "⟡ ═══════════════════ ⟡\n\n"
            "**Commands:**\n"
            "  `.qr <text/url>` — Generate standard QR code\n"
            "  `.qr read` (reply to image) — Decode QR code\n"
            "  `.qr wifi <ssid> <password>` — Generate WiFi connect QR\n"
            "  `.qr styled <color> <text>` — Generate colored QR\n"
            "  `.qr crypto <btc/eth/ltc> <address>` — Crypto payment QR\n\n"
            "**Supported Colors:** red, blue, green, gold, pink"
         )
         await event.reply(text)
         return
         
    # ── .qr read ───────────────────────────────────────────────────────────────
    if sub == "read":
        msg = await event.reply("🔍 Scanning QR code...")
        result = await read_qr(event)
        await msg.edit(result)
        return

    # ── .qr wifi ───────────────────────────────────────────────────────────────
    if sub == "wifi":
        if not extra:
             await event.reply("❌ Usage: `.qr wifi <SSID> <Password>`")
             return
             
        wifi_parts = extra.split(" ", 1)
        if len(wifi_parts) < 2:
            await event.reply("❌ Usage: `.qr wifi <SSID> <Password>`")
            return
            
        ssid = wifi_parts[0]
        password = wifi_parts[1]
        
        # WPA/WPA2 format
        wifi_str = f"WIFI:T:WPA;S:{ssid};P:{password};;"
        
        msg = await event.reply(f"🧬 Generating WiFi QR for `{ssid}`...")
        try:
            path = generate_qr(wifi_str, "wifi_qr.png")
            await event.client.send_file(
                event.chat_id, 
                path, 
                caption=f"📱 **WiFi QR Code**\nSSID: `{ssid}`\nScan to connect!",
                force_document=False
            )
            await msg.delete()
            os.remove(path)
        except Exception as e:
            await msg.edit(f"❌ Error: `{e}`")
        return

    # ── .qr crypto ─────────────────────────────────────────────────────────────
    if sub == "crypto":
        if not extra:
             await event.reply("❌ Usage: `.qr crypto <btc/eth/ltc> <address>`")
             return
             
        crypto_parts = extra.split(" ", 1)
        if len(crypto_parts) < 2:
            await event.reply("❌ Usage: `.qr crypto <coin> <address>`")
            return
            
        coin = crypto_parts[0].lower()
        address = crypto_parts[1]
        
        scheme_map = {
            "btc": "bitcoin",
            "eth": "ethereum",
            "ltc": "litecoin",
        }
        
        scheme = scheme_map.get(coin)
        if not scheme:
            await event.reply(f"❌ Unsupported coin: `{coin}`. Supported: btc, eth, ltc")
            return
            
        crypto_str = f"{scheme}:{address}"
        
        msg = await event.reply(f"💰 Generating {coin.upper()} QR...")
        try:
            path = generate_qr(crypto_str, f"{coin}_qr.png")
            await event.client.send_file(
                event.chat_id, 
                path, 
                caption=f"💰 **{coin.upper()} Payment Address**\n`{address}`",
                force_document=False
            )
            await msg.delete()
            os.remove(path)
        except Exception as e:
            await msg.edit(f"❌ Error: `{e}`")
        return

    # ── .qr styled ─────────────────────────────────────────────────────────────
    if sub == "styled":
        if not extra:
             await event.reply("❌ Usage: `.qr styled <color> <text>`")
             return
             
        style_parts = extra.split(" ", 1)
        if len(style_parts) < 2:
             await event.reply("❌ Usage: `.qr styled <color> <text>`")
             return
             
        color = style_parts[0].lower()
        text = style_parts[1]
        
        if color not in COLORS:
             await event.reply(f"❌ Invalid color. Supported: {', '.join(COLORS.keys())}")
             return
             
        msg = await event.reply(f"🎨 Generating {color} QR code...")
        try:
            path = generate_styled_qr(text, color, "styled_qr.png")
            await event.client.send_file(
                event.chat_id, 
                path, 
                caption="🧬 **Custom QR Code**",
                force_document=False
            )
            await msg.delete()
            os.remove(path)
        except Exception as e:
            await msg.edit(f"❌ Error: `{e}`")
        return

    # ── .qr <text> (Standard) ──────────────────────────────────────────────────
    msg = await event.reply("🧬 Generating QR code...")
    try:
        path = generate_qr(args, "standard_qr.png")
        await event.client.send_file(
            event.chat_id, 
            path, 
            caption="🧬 **QR Code Generated**",
            force_document=False
        )
        await msg.delete()
        os.remove(path)
    except Exception as e:
         await msg.edit(f"❌ Error: `{e}`")
