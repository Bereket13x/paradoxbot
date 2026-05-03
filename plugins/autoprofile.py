# ==============================================================================
#  🎭 PARADOX - Auto Profile Tools
#  PARADOX Userbot
#  All rights reserved.
# ==============================================================================

import asyncio
import os
import ssl
import urllib.request
from datetime import datetime, timedelta
from PIL import Image, ImageDraw, ImageFont
from telethon import functions, events
from telethon.errors import FloodWaitError, RPCError
from utils.utils import CipherElite
from utils.decorators import rishabh
from plugins.bot import add_handler

# --- Configuration & Assets ---
ASSETS_DIR = "cipher_assets"
if not os.path.exists(ASSETS_DIR):
    os.makedirs(ASSETS_DIR)


USER_BG_URL = "https://raw.githubusercontent.com/rishabhops/CipherElite/elite/images/1000083995.jpg"


BACKUP_BG_URL = "https://images.unsplash.com/photo-1550751827-4bd374c3f58b?ixlib=rb-1.2.1&auto=format&fit=crop&w=1024&q=80"

# Font (Roboto Black)
FONT_URL = "https://github.com/google/fonts/raw/main/apache/roboto/static/Roboto-Black.ttf"
FONT_PATH = os.path.join(ASSETS_DIR, "bold.ttf")
PFP_PATH = os.path.join(ASSETS_DIR, "current_pfp.jpg")
BG_PATH = os.path.join(ASSETS_DIR, "bg.jpg")

# --- Global State & Animations ---
RUNNING_TASKS = {
    "autoname": {"running": False, "style": "time", "text": "PARADOX", "frame": 0},
    "autobio": {"running": False, "style": "time", "text": "PARADOX", "frame": 0},
    "digitalpfp": {"running": False}
}

ANIMATIONS = {
    "premium": ["⭐", "🌟", "✨", "⚡", "🔥"],
    "moon": ["🌑", "🌒", "🌓", "🌔", "🌕", "🌖", "🌗", "🌘"],
    "earth": ["🌍", "🌎", "🌏"],
    "clock": ["🕛", "🕐", "🕑", "🕒", "🕓", "🕔", "🕕", "🕖", "🕗", "🕘", "🕙", "🕚"],
    "hearts": ["❤️", "🧡", "💛", "💚", "💙", "💜", "🖤", "🤍", "🤎"],
    "music": ["🎵", "🎶", "🎧", "🎸", "🎹", "🎺", "🎻", "🥁"],
    "space": ["🚀", "🛸", "☄️", "🪐", "🛰️"],
    "stars": ["✧", "✦", "✨", "💫", "⭐", "🌟"],
    "crown": ["👑", "🥇", "🏆", "🎖️", "🏅"],
    "diamond": ["🔹", "🟦", "🔷", "💠", "💎", "💍"],
    "pulse": ["◎", "◉", "●", "◉", "◎", "◯"],
    "radar": ["▖", "▘", "▝", "▗"],
    "loading": ["[>   ]", "[=>  ]", "[==> ]", "[===>]", "[ ===]", "[  ==]", "[   =]", "[    ]"],
    "battery": ["🔋 [■□□□□]", "🔋 [■■□□□]", "🔋 [■■■□□]", "🔋 [■■■■□]", "🔋 [■■■■■]"],
    "cyber": ["[ • • • ]", "[ = • • ]", "[ = = • ]", "[ = = = ]", "[ • = = ]", "[ • • = ]"],
    "hacker": ["█▓▒░", "▓▒░█", "▒░█▓", "░█▓▒"],
    "braille": ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"],
}

# --- Helper Functions ---

def get_eat_time():
    """Returns current Ethiopian Time (EAT = UTC+3)."""
    utc_now = datetime.utcnow()
    eat_now = utc_now + timedelta(hours=3)
    return eat_now

def download_file(url, filename):
    """Downloads file with Strong SSL Bypass & User-Agent."""
    try:
        if os.path.exists(filename) and os.path.getsize(filename) > 0:
            return True
            
        # Create unverified context to bypass SSL errors
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        
        opener = urllib.request.build_opener(urllib.request.HTTPSHandler(context=ctx))
        opener.addheaders = [('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)')]
        urllib.request.install_opener(opener)
        
        urllib.request.urlretrieve(url, filename)
        return True
    except Exception as e:
        print(f"⚠️ Download Failed for {url}: {e}")
        return False

async def notify_user(client, message):
    try:
        await client.send_message("me", message)
    except:
        pass

def generate_time_pfp():
    """Generates a PFP with the current EAT time."""
    
    # 1. Try to download User Image
    if not download_file(USER_BG_URL, BG_PATH):
        # 2. If Failed, Download Backup Image
        print("User image failed. Downloading backup...")
        download_file(BACKUP_BG_URL, BG_PATH)
    
    download_file(FONT_URL, FONT_PATH)
    
    # Load Background
    if os.path.exists(BG_PATH):
        img = Image.open(BG_PATH).convert("RGBA").resize((1024, 1024))
    else:
        # Last Resort: Dark Blue (Better than black)
        img = Image.new("RGBA", (1024, 1024), (10, 10, 30, 255))
        
    draw = ImageDraw.Draw(img)
    eat_now = get_eat_time()
    time_str = eat_now.strftime("%I:%M %p")
    
    # Load Font
    try:
        font = ImageFont.truetype(FONT_PATH, 400) if os.path.exists(FONT_PATH) else ImageFont.load_default()
        small_font = ImageFont.truetype(FONT_PATH, 70) if os.path.exists(FONT_PATH) else ImageFont.load_default()
    except:
        font = ImageFont.load_default()
        small_font = ImageFont.load_default()

    # Draw Time - CENTERED with OUTLINE
    draw.text(
        (512, 512), 
        time_str, 
        font=font, 
        fill="#00ffcc", 
        anchor="mm", 
        stroke_width=15, 
        stroke_fill="black"
    )
    
    # Draw Watermark
    draw.text(
        (512, 850), 
        "PARADOX", 
        font=small_font, 
        fill="#ffffff", 
        anchor="mm",
        stroke_width=5,
        stroke_fill="black"
    )

    img.convert("RGB").save(PFP_PATH)
    return PFP_PATH

# --- Async Loops ---

async def loop_autoname(client):
    while RUNNING_TASKS["autoname"]["running"]:
        try:
            style = RUNNING_TASKS["autoname"]["style"]
            text = RUNNING_TASKS["autoname"]["text"]
            frame = RUNNING_TASKS["autoname"]["frame"]
            
            if style == "time":
                eat_now = get_eat_time()
                time_str = eat_now.strftime("%I:%M %p")
                new_name = f"⚡ {time_str} | {text}"
            elif style in ANIMATIONS:
                anim = ANIMATIONS[style]
                emoji = anim[frame % len(anim)]
                new_name = f"{emoji} {text}"
                RUNNING_TASKS["autoname"]["frame"] += 1
            else:
                new_name = text
                
            await client(functions.account.UpdateProfileRequest(first_name=new_name))
        except FloodWaitError as e:
            await notify_user(client, f"⏳ AutoName FloodWait: {e.seconds}s")
            await asyncio.sleep(e.seconds)
        except Exception:
            pass
        await asyncio.sleep(60)

async def loop_autobio(client):
    while RUNNING_TASKS["autobio"]["running"]:
        try:
            style = RUNNING_TASKS["autobio"]["style"]
            text = RUNNING_TASKS["autobio"]["text"]
            frame = RUNNING_TASKS["autobio"]["frame"]
            
            if style == "time":
                eat_now = get_eat_time()
                time_str = eat_now.strftime("%I:%M %p")
                date_str = eat_now.strftime("%d-%b")
                new_bio = f"📅 {date_str} | {text} | ⌚ {time_str}"
            elif style in ANIMATIONS:
                anim = ANIMATIONS[style]
                emoji = anim[frame % len(anim)]
                new_bio = f"{emoji} {text} {emoji}"
                RUNNING_TASKS["autobio"]["frame"] += 1
            else:
                new_bio = text

            await client(functions.account.UpdateProfileRequest(about=new_bio))
        except FloodWaitError as e:
            await notify_user(client, f"⏳ AutoBio FloodWait: {e.seconds}s")
            await asyncio.sleep(e.seconds)
        except Exception:
            pass
        await asyncio.sleep(60)

async def loop_digitalpfp(client):
    while RUNNING_TASKS["digitalpfp"]["running"]:
        try:
            pfp_file = generate_time_pfp()
            if os.path.exists(pfp_file):
                file = await client.upload_file(pfp_file)
                await client(functions.photos.UploadProfilePhotoRequest(file=file))
                os.remove(pfp_file)
            else:
                await notify_user(client, "⚠️ PFP Gen Error")
        except FloodWaitError as e:
            await notify_user(client, f"🛑 PFP Stopped: FloodWait {e.seconds}s")
            RUNNING_TASKS["digitalpfp"]["running"] = False
            break
        except Exception as e:
            await notify_user(client, f"❌ PFP Error: {str(e)}")
        await asyncio.sleep(60)

# --- Plugin Init ---

def init(client_instance):
    commands = [
        ".autoname <style> <text> - Rotating custom emojis in Name",
        ".autobio <style> <text> - Rotating custom emojis in Bio",
        ".digitalpfp - Start Bold Time PFP",
        ".nstyles - List all available styles",
        ".end <task> - Stop task"
    ]
    description = "🎭 Profile Tools - Auto Updates"
    add_handler("autoprofile", commands, description)

async def register_commands():
    @CipherElite.on(events.NewMessage(pattern=r"^\.nstyles$"))
    @rishabh()
    async def show_styles(event):
        styles_list = "\n".join([f"✨ `{k}` : {v[0]} ➡️ {v[1]}" for k, v in ANIMATIONS.items() if len(v) > 1])
        msg = f"🎭 **Available Autoprofile Styles**\n\n{styles_list}\n✨ `time` : ⌚ 12:45 PM\n\n**Usage:** `.autoname <style> <text>`"
        await event.reply(msg)

    @CipherElite.on(events.NewMessage(pattern=r"^\.autoname(?:\s+(\w+))?(?:\s+(.+))?"))
    @rishabh()
    async def enable_autoname(event):
        style = (event.pattern_match.group(1) or "time").lower()
        text = event.pattern_match.group(2) or "PARADOX"
        
        if style not in ANIMATIONS and style != "time":
            styles_str = ", ".join(list(ANIMATIONS.keys()) + ["time"])
            return await event.reply(f"❌ **Invalid style!**\nChoose from: `{styles_str}`")
            
        RUNNING_TASKS["autoname"]["style"] = style
        RUNNING_TASKS["autoname"]["text"] = text
        RUNNING_TASKS["autoname"]["frame"] = 0
        
        if not RUNNING_TASKS["autoname"]["running"]:
            RUNNING_TASKS["autoname"]["running"] = True
            CipherElite.loop.create_task(loop_autoname(event.client))
            
        await event.reply(f"🎭 **AutoName Started**\n✨ **Style:** `{style}`\n📝 **Text:** `{text}`")

    @CipherElite.on(events.NewMessage(pattern=r"^\.autobio(?:\s+(\w+))?(?:\s+(.+))?"))
    @rishabh()
    async def enable_autobio(event):
        style = (event.pattern_match.group(1) or "time").lower()
        text = event.pattern_match.group(2) or "PARADOX"
        
        if style not in ANIMATIONS and style != "time":
            styles_str = ", ".join(list(ANIMATIONS.keys()) + ["time"])
            return await event.reply(f"❌ **Invalid style!**\nChoose from: `{styles_str}`")
            
        RUNNING_TASKS["autobio"]["style"] = style
        RUNNING_TASKS["autobio"]["text"] = text
        RUNNING_TASKS["autobio"]["frame"] = 0
        
        if not RUNNING_TASKS["autobio"]["running"]:
            RUNNING_TASKS["autobio"]["running"] = True
            CipherElite.loop.create_task(loop_autobio(event.client))
            
        await event.reply(f"🎭 **AutoBio Started**\n✨ **Style:** `{style}`\n📝 **Text:** `{text}`")

    @CipherElite.on(events.NewMessage(pattern=r"^\.digitalpfp$"))
    @rishabh()
    async def enable_digitalpfp(event):
        if RUNNING_TASKS["digitalpfp"]["running"]: return await event.reply("⚠️ Running")
        status = await event.reply("🔄 **Starting PFP...**")
        
        # Cleanup old buggy file if it exists
        if os.path.exists(BG_PATH): os.remove(BG_PATH)
        
        try:
            test_path = generate_time_pfp()
            if not os.path.exists(test_path): return await status.edit("❌ Gen Error")
            file = await event.client.upload_file(test_path)
            await event.client(functions.photos.UploadProfilePhotoRequest(file=file))
            RUNNING_TASKS["digitalpfp"]["running"] = True
            CipherElite.loop.create_task(loop_digitalpfp(event.client))
            await status.edit("🎭 **Digital PFP Started**\nIf your image is missing, a backup Cyberpunk image was used.")
        except FloodWaitError as e:
            await status.edit(f"❌ FloodWait: {e.seconds}s")
        except Exception as e:
            await status.edit(f"❌ Error: {str(e)}")

    @CipherElite.on(events.NewMessage(pattern=r"\.end\s+(.+)"))
    @rishabh()
    async def end_task(event):
        task = event.pattern_match.group(1).lower().strip()
        if task in RUNNING_TASKS:
            RUNNING_TASKS[task]["running"] = False
            await event.reply(f"🛑 Stopped {task}")
        else:
            await event.reply("❌ Invalid task")

