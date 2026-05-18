# ==============================================================================
#  🎭 PARADOX - Auto Profile Tools
#  PARADOX Userbot
#  All rights reserved.
# ==============================================================================

import asyncio
import os
import ssl
import urllib.request
import json
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
STATE_FILE = os.path.join(ASSETS_DIR, "autoprofile_state.json")

# --- Global State & Animations ---
RUNNING_TASKS = {
    "autoname": {"running": False, "style": "time", "text": "PARADOX", "frame": 0},
    "autobio": {"running": False, "style": "time", "text": "PARADOX", "frame": 0},
    "digitalpfp": {"running": False},
    "forgepfp": {"running": False, "frame": 0, "username": ""},
    "status": {"active": False, "mood": "", "frame": 0, "original_first": None, "original_last": None, "original_bio": None, "last_photo_id": None, "last_photo_hash": None, "paused_tasks": []}
}

def save_state():
    try:
        with open(STATE_FILE, "w") as f:
            json.dump(RUNNING_TASKS, f)
    except Exception:
        pass

def load_state():
    global RUNNING_TASKS
    try:
        if os.path.exists(STATE_FILE):
            with open(STATE_FILE, "r") as f:
                saved = json.load(f)
                for k, v in saved.items():
                    if k in RUNNING_TASKS:
                        RUNNING_TASKS[k].update(v)
    except Exception:
        pass

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

STATUS_MOODS = {
    "coding": {
        "bgs": [
            "https://images.unsplash.com/photo-1526374965328-7f61d4dc18c5?auto=format&fit=crop&w=1024&q=80",
            "https://images.unsplash.com/photo-1542831371-29b0f74f9713?auto=format&fit=crop&w=1024&q=80",
            "https://images.unsplash.com/photo-1555066931-4365d14bab8c?auto=format&fit=crop&w=1024&q=80"
        ],
        "emoji": "💻", "text": "CODING", "bio": "Deep in the code. Expect slow replies.", "suffix": " | [CODING]"
    },
    "sleep": {
        "bgs": [
            "https://images.unsplash.com/photo-1531306728370-53bf9ce45f40?auto=format&fit=crop&w=1024&q=80",
            "https://images.unsplash.com/photo-1516585427167-9f4af9627e6c?auto=format&fit=crop&w=1024&q=80",
            "https://images.unsplash.com/photo-1512438248247-f0f2a5a8b7f0?auto=format&fit=crop&w=1024&q=80"
        ],
        "emoji": "💤", "text": "SLEEPING", "bio": "Currently sleeping. Leave a message.", "suffix": " | [Zzz]"
    },
    "gaming": {
        "bgs": [
            "https://images.unsplash.com/photo-1542751371-adc38448a05e?auto=format&fit=crop&w=1024&q=80",
            "https://images.unsplash.com/photo-1493711662062-fa541adb3fc8?auto=format&fit=crop&w=1024&q=80",
            "https://images.unsplash.com/photo-1552820728-8b83bb6b773f?auto=format&fit=crop&w=1024&q=80"
        ],
        "emoji": "🎮", "text": "GAMING", "bio": "In the zone. Gaming right now.", "suffix": " | [GAMING]"
    },
    "music": {
        "bgs": [
            "https://images.unsplash.com/photo-1511671782779-c97d3d27a1d4?auto=format&fit=crop&w=1024&q=80",
            "https://images.unsplash.com/photo-1470225620780-dba8ba36b745?auto=format&fit=crop&w=1024&q=80",
            "https://images.unsplash.com/photo-1514525253161-7a46d19cd819?auto=format&fit=crop&w=1024&q=80"
        ],
        "emoji": "🎧", "text": "MUSIC", "bio": "Vibing to some music.", "suffix": " | [MUSIC]"
    },
    "dnd": {
        "bgs": [
            "https://images.unsplash.com/photo-1507608616759-54f48f0af0ee?auto=format&fit=crop&w=1024&q=80",
            "https://images.unsplash.com/photo-1494809610410-160faaed4de0?auto=format&fit=crop&w=1024&q=80",
            "https://images.unsplash.com/photo-1482440308425-276ad0f28b19?auto=format&fit=crop&w=1024&q=80"
        ],
        "emoji": "🚫", "text": "DO NOT DISTURB", "bio": "Do Not Disturb. Important work in progress.", "suffix": " | [DND]"
    },
    "workout": {
        "bgs": [
            "https://images.unsplash.com/photo-1517836357463-d25dfeac3438?auto=format&fit=crop&w=1024&q=80",
            "https://images.unsplash.com/photo-1534438327276-14e5300c3a48?auto=format&fit=crop&w=1024&q=80",
            "https://images.unsplash.com/photo-1581009146145-b5ef050c2e1e?auto=format&fit=crop&w=1024&q=80"
        ],
        "emoji": "🏋️‍♂️", "text": "WORKOUT", "bio": "At the gym pushing limits.", "suffix": " | [GYM]"
    },
    "travel": {
        "bgs": [
            "https://images.unsplash.com/photo-1436491865332-7a61a109cc05?auto=format&fit=crop&w=1024&q=80",
            "https://images.unsplash.com/photo-1476514525535-07fb3b4ae5f1?auto=format&fit=crop&w=1024&q=80",
            "https://images.unsplash.com/photo-1488646953014-85cb44e25828?auto=format&fit=crop&w=1024&q=80"
        ],
        "emoji": "✈️", "text": "TRAVELING", "bio": "On the move. Traveling the world.", "suffix": " | [TRAVEL]"
    },
    "anime": {
        "bgs": [
            "https://images.unsplash.com/photo-1578632767115-351597cf2477?auto=format&fit=crop&w=1024&q=80",
            "https://images.unsplash.com/photo-1580477651161-0428bc4bd93b?auto=format&fit=crop&w=1024&q=80",
            "https://images.unsplash.com/photo-1541562232579-512a21360020?auto=format&fit=crop&w=1024&q=80"
        ],
        "emoji": "🎌", "text": "WATCHING ANIME", "bio": "In another world right now. Do not disturb.", "suffix": " | [ANIME]"
    }
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

def generate_status_pfp(mood_key: str, frame: int = 0):
    mood = STATUS_MOODS.get(mood_key)
    if not mood: return None
    
    bgs = mood["bgs"]
    bg_url = bgs[frame % len(bgs)]
    filename = os.path.join(ASSETS_DIR, f"status_bg_{mood_key}_{frame % len(bgs)}.jpg")
    download_file(bg_url, filename)
    
    if os.path.exists(filename):
        try:
            img = Image.open(filename).convert("RGBA").resize((1024, 1024))
        except:
            img = Image.new("RGBA", (1024, 1024), (20, 20, 20, 255))
    else:
        img = Image.new("RGBA", (1024, 1024), (20, 20, 20, 255))
        
    # Dark vignette / overlay for readability
    overlay = Image.new("RGBA", (1024, 1024), (0, 0, 0, 0))
    draw_ov = ImageDraw.Draw(overlay)
    for y in range(1024):
        alpha = int(120 + (100 * (y / 1024))) 
        draw_ov.line([(0, y), (1024, y)], fill=(0, 0, 0, alpha))
    img = Image.alpha_composite(img, overlay)
    
    draw = ImageDraw.Draw(img)
    download_file(FONT_URL, FONT_PATH)
    try:
        title_font = ImageFont.truetype(FONT_PATH, 120)
        subtitle_font = ImageFont.truetype(FONT_PATH, 40)
        watermark_font = ImageFont.truetype(FONT_PATH, 30)
    except:
        title_font = ImageFont.load_default()
        subtitle_font = ImageFont.load_default()
        watermark_font = ImageFont.load_default()
        
    text = mood["text"]
    
    def draw_outlined(d, pos, txt, font, fill, stroke, width=3):
        d.text(pos, txt, font=font, fill=fill, anchor="mm", stroke_width=width, stroke_fill=stroke)

    draw_outlined(draw, (512, 450), "STATUS UPDATE", subtitle_font, "#00ffcc", "black", 2)
    draw_outlined(draw, (512, 530), text, title_font, "white", "black", 5)
    draw_outlined(draw, (512, 950), "🎭 PARADOX PROFILE", watermark_font, (255,255,255,180), "black", 1)
    
    out_path = os.path.join(ASSETS_DIR, "current_status.jpg")
    img.convert("RGB").save(out_path)
    return out_path

def generate_forge_pfp(display_name: str, tg_username: str, frame: int) -> str:
    """Generates a styled PFP using Forge assets with Time, Name, and Username."""
    try:
        from plugins.forge import TEXT_STYLES, _make_gradient_bg, _load_best_font
    except ImportError:
        return ""
        
    style_names = list(TEXT_STYLES.keys())
    style_name = style_names[frame % len(style_names)]
    cfg = TEXT_STYLES[style_name]
    
    bg = _make_gradient_bg(cfg["bg"], (512, 512)).convert("RGBA")
    
    # Add subtle noise overlay
    import random as _rnd
    noise = Image.new("RGBA", (512, 512), (0, 0, 0, 0))
    noise_draw = ImageDraw.Draw(noise)
    for _ in range(600):
        x = _rnd.randint(0, 511)
        y = _rnd.randint(0, 511)
        a = _rnd.randint(10, 40)
        noise_draw.point((x, y), fill=(255, 255, 255, a))
    bg = Image.alpha_composite(bg, noise)
    
    eat_now = get_eat_time()
    time_str = eat_now.strftime("%I:%M %p")
    
    time_font = _load_best_font(110) # Big visible time
    name_font = _load_best_font(45)
    user_font = _load_best_font(30)
    style_font = _load_best_font(18)
    
    draw = ImageDraw.Draw(bg)
    
    def draw_styled_text(draw, text, font, y_pos, cfg):
        try:
            bbox = draw.textbbox((0, 0), text, font=font)
            tw = bbox[2] - bbox[0]
        except Exception:
            tw = len(text) * 20
        tx = (512 - tw) // 2
        ty = y_pos
        
        outline_col = (*cfg["outline"][:3], 255)
        for ox, oy in [(-2,-2),(2,-2),(-2,2),(2,2),(-3,0),(3,0),(0,-3),(0,3)]:
            draw.text((tx + ox, ty + oy), text, font=font, fill=outline_col)

        shadow_col = (*cfg["shadow"][:3], 180)
        draw.text((tx + 5, ty + 5), text, font=font, fill=shadow_col)
        draw.text((tx + 4, ty + 4), text, font=font, fill=shadow_col)

        text_col = (*cfg["text"][:3], 255)
        draw.text((tx, ty), text, font=font, fill=text_col)

    # ── Draw Elements ───────────────────────────────────────
    # 1. Massive Time at top center
    draw_styled_text(draw, time_str, time_font, 140, cfg)
    
    # 2. Display Name in the middle
    display = display_name.upper()[:20]
    draw_styled_text(draw, display, name_font, 300, cfg)
    
    # 3. Username / Handle slightly smaller below
    draw_styled_text(draw, tg_username, user_font, 360, cfg)
    
    # 4. Small watermark in corner
    if style_font:
        draw.text((16, 485), "PARADOX", font=style_font, fill=(*cfg["text"][:3], 150))
        draw.text((16, 16), "UPDATES EVERY 5 MIN", font=style_font, fill=(*cfg["text"][:3], 150))
    
    path = os.path.join(ASSETS_DIR, "forge_pfp.jpg")
    bg.convert("RGB").save(path, "JPEG")
    return path

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
        await asyncio.sleep(300)

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
        await asyncio.sleep(300)

async def loop_digitalpfp(client):
    while RUNNING_TASKS["digitalpfp"]["running"]:
        try:
            pfp_file = generate_time_pfp()
            if os.path.exists(pfp_file):
                file = await client.upload_file(pfp_file)
                res = await client(functions.photos.UploadProfilePhotoRequest(file=file))
                
                # Delete previous auto-generated PFP
                last_id = RUNNING_TASKS["digitalpfp"].get("last_photo_id")
                last_hash = RUNNING_TASKS["digitalpfp"].get("last_photo_hash")
                if last_id and last_hash:
                    try:
                        from telethon.tl.types import InputPhoto
                        from telethon.tl.functions.photos import DeletePhotosRequest
                        await client(DeletePhotosRequest(id=[InputPhoto(id=last_id, access_hash=last_hash, file_reference=b'')]))
                    except Exception:
                        pass
                
                RUNNING_TASKS["digitalpfp"]["last_photo_id"] = getattr(res.photo, "id", None)
                RUNNING_TASKS["digitalpfp"]["last_photo_hash"] = getattr(res.photo, "access_hash", None)
                save_state()
                
                os.remove(pfp_file)
            else:
                await notify_user(client, "⚠️ PFP Gen Error")
        except FloodWaitError as e:
            wait_mins = round(e.seconds / 60)
            await notify_user(client, f"⏳ **Digital PFP FloodWait!**\nTelegram blocked profile changes for **{wait_mins} minutes** ({e.seconds}s).\nAuto-resuming after the wait...")
            await asyncio.sleep(e.seconds + 10)
            continue
        except RPCError as e:
            await notify_user(client, f"⚠️ **Digital PFP RPC Error:** `{e}`\nRetrying in 3 minutes...")
            await asyncio.sleep(180)
            continue
        except Exception as e:
            await notify_user(client, f"❌ **PFP Error:** `{str(e)}`\nRetrying in 3 minutes...")
            await asyncio.sleep(180)
            continue
        await asyncio.sleep(180)

async def loop_forgepfp(client):
    while RUNNING_TASKS["forgepfp"]["running"]:
        try:
            me = await client.get_me()
            
            # 1. Get the cleanest Display Name
            if RUNNING_TASKS["autoname"]["running"]:
                display_name = RUNNING_TASKS["autoname"]["text"]
            else:
                first = me.first_name or "USER"
                if "|" in first:
                    first = first.split("|")[-1].strip()
                last = f" {me.last_name}" if me.last_name else ""
                display_name = f"{first}{last}".strip()
                
            # 2. Get the @username
            tg_username = f"@{me.username}" if me.username else "PARADOX USER"
            
            frame = RUNNING_TASKS["forgepfp"]["frame"]
            
            pfp_file = generate_forge_pfp(display_name, tg_username, frame)
            if os.path.exists(pfp_file):
                file = await client.upload_file(pfp_file)
                res = await client(functions.photos.UploadProfilePhotoRequest(file=file))
                
                # Delete previous auto-generated PFP
                last_id = RUNNING_TASKS["forgepfp"].get("last_photo_id")
                last_hash = RUNNING_TASKS["forgepfp"].get("last_photo_hash")
                if last_id and last_hash:
                    try:
                        from telethon.tl.types import InputPhoto
                        from telethon.tl.functions.photos import DeletePhotosRequest
                        await client(DeletePhotosRequest(id=[InputPhoto(id=last_id, access_hash=last_hash, file_reference=b'')]))
                    except Exception:
                        pass
                        
                RUNNING_TASKS["forgepfp"]["last_photo_id"] = getattr(res.photo, "id", None)
                RUNNING_TASKS["forgepfp"]["last_photo_hash"] = getattr(res.photo, "access_hash", None)
                save_state()
                
                os.remove(pfp_file)
                RUNNING_TASKS["forgepfp"]["frame"] += 1
            else:
                await notify_user(client, "⚠️ Forge PFP Gen Error")
        except FloodWaitError as e:
            wait_mins = round(e.seconds / 60)
            # Delete current forge PFP to restore original profile picture
            last_id = RUNNING_TASKS["forgepfp"].get("last_photo_id")
            last_hash = RUNNING_TASKS["forgepfp"].get("last_photo_hash")
            if last_id and last_hash:
                try:
                    from telethon.tl.types import InputPhoto
                    from telethon.tl.functions.photos import DeletePhotosRequest
                    await client(DeletePhotosRequest(id=[InputPhoto(id=last_id, access_hash=last_hash, file_reference=b'')]))
                    RUNNING_TASKS["forgepfp"]["last_photo_id"] = None
                    RUNNING_TASKS["forgepfp"]["last_photo_hash"] = None
                    save_state()
                except Exception:
                    pass
            await notify_user(client, f"⏳ **Forge PFP FloodWait!**\nRestored original profile picture.\nTelegram blocked changes for **{wait_mins} minutes** ({e.seconds}s).\nAuto-resuming after the wait...")
            await asyncio.sleep(e.seconds + 10)
            continue
        except RPCError as e:
            await notify_user(client, f"⚠️ **Forge PFP RPC Error:** `{e}`\nRetrying in 5 minutes...")
            await asyncio.sleep(300)
            continue
        except Exception as e:
            await notify_user(client, f"❌ **Forge PFP Error:** `{str(e)}`\nRetrying in 5 minutes...")
            await asyncio.sleep(300)
            continue
        await asyncio.sleep(300)

async def loop_status(client):
    while RUNNING_TASKS["status"]["active"]:
        try:
            mood_key = RUNNING_TASKS["status"].get("mood")
            if not mood_key or mood_key not in STATUS_MOODS:
                await asyncio.sleep(60)
                continue
                
            frame = RUNNING_TASKS["status"].get("frame", 0)
            pfp_file = generate_status_pfp(mood_key, frame)
            
            if pfp_file and os.path.exists(pfp_file):
                file = await client.upload_file(pfp_file)
                res = await client(functions.photos.UploadProfilePhotoRequest(file=file))
                
                last_id = RUNNING_TASKS["status"].get("last_photo_id")
                last_hash = RUNNING_TASKS["status"].get("last_photo_hash")
                if last_id and last_hash:
                    try:
                        from telethon.tl.types import InputPhoto
                        from telethon.tl.functions.photos import DeletePhotosRequest
                        await client(DeletePhotosRequest(id=[InputPhoto(id=last_id, access_hash=last_hash, file_reference=b'')]))
                    except Exception:
                        pass
                        
                RUNNING_TASKS["status"]["last_photo_id"] = getattr(res.photo, "id", None)
                RUNNING_TASKS["status"]["last_photo_hash"] = getattr(res.photo, "access_hash", None)
                RUNNING_TASKS["status"]["frame"] = frame + 1
                save_state()
            else:
                await notify_user(client, "⚠️ Status PFP Gen Error")
        except FloodWaitError as e:
            await notify_user(client, f"⏳ **Status PFP FloodWait:** {e.seconds}s.")
            await asyncio.sleep(e.seconds + 10)
            continue
        except Exception as e:
            await notify_user(client, f"❌ **Status PFP Error:** `{str(e)}`")
            await asyncio.sleep(300)
            continue
        await asyncio.sleep(300)

# --- Plugin Init ---

def init(client_instance):
    commands = [
        ".autoname <style> <text> - Rotating custom emojis in Name",
        ".autobio <style> <text> - Rotating custom emojis in Bio",
        ".digitalpfp - Start Bold Time PFP",
        ".forgepfp - Start dynamically styled Forge Time PFP",
        ".setstatus <mood> - Set profile status (coding, sleep, gaming, etc.)",
        ".setstatus reverse - Revert to original profile",
        ".nstyles - List all available styles",
        ".end <task> - Stop task"
    ]
    description = "🎭 Profile Tools - Auto Updates"
    add_handler("autoprofile", commands, description)

async def register_commands():
    load_state()
    if RUNNING_TASKS["autoname"]["running"]:
        CipherElite.loop.create_task(loop_autoname(CipherElite))
    if RUNNING_TASKS["autobio"]["running"]:
        CipherElite.loop.create_task(loop_autobio(CipherElite))
    if RUNNING_TASKS["digitalpfp"]["running"]:
        CipherElite.loop.create_task(loop_digitalpfp(CipherElite))
    if RUNNING_TASKS["forgepfp"]["running"]:
        CipherElite.loop.create_task(loop_forgepfp(CipherElite))
    if RUNNING_TASKS["status"]["active"]:
        CipherElite.loop.create_task(loop_status(CipherElite))

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
        save_state()
        
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
        save_state()
        
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
            res = await event.client(functions.photos.UploadProfilePhotoRequest(file=file))
            
            # Delete previous auto-generated PFP
            last_id = RUNNING_TASKS["digitalpfp"].get("last_photo_id")
            last_hash = RUNNING_TASKS["digitalpfp"].get("last_photo_hash")
            if last_id and last_hash:
                try:
                    from telethon.tl.types import InputPhoto
                    from telethon.tl.functions.photos import DeletePhotosRequest
                    await event.client(DeletePhotosRequest(id=[InputPhoto(id=last_id, access_hash=last_hash, file_reference=b'')]))
                except Exception:
                    pass
            
            RUNNING_TASKS["digitalpfp"]["last_photo_id"] = getattr(res.photo, "id", None)
            RUNNING_TASKS["digitalpfp"]["last_photo_hash"] = getattr(res.photo, "access_hash", None)
            RUNNING_TASKS["digitalpfp"]["running"] = True
            save_state()
            CipherElite.loop.create_task(loop_digitalpfp(event.client))
            await status.edit("🎭 **Digital PFP Started**\nIf your image is missing, a backup Cyberpunk image was used.")
        except FloodWaitError as e:
            await status.edit(f"❌ FloodWait: {e.seconds}s")
        except Exception as e:
            await status.edit(f"❌ Error: {str(e)}")

    @CipherElite.on(events.NewMessage(pattern=r"^\.forgepfp$"))
    @rishabh()
    async def enable_forgepfp(event):
        if RUNNING_TASKS["forgepfp"]["running"]: return await event.reply("⚠️ Forge PFP already running.")
        status = await event.reply("🔄 **Starting Forge PFP...**")
        
        try:
            RUNNING_TASKS["forgepfp"]["running"] = True
            save_state()
            CipherElite.loop.create_task(loop_forgepfp(event.client))
            await status.edit("🎭 **Forge PFP Started!**\nAutomatically changing profile picture styles every 5 minutes.")
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
            save_state()
            await event.reply(f"🛑 Stopped {task}")
        else:
            await event.reply("❌ Invalid task")

    @CipherElite.on(events.NewMessage(pattern=r"^\.setstatus(?:\s+(.+))?$"))
    @rishabh()
    async def cmd_setstatus(event):
        mood_key = (event.pattern_match.group(1) or "").strip().lower()
        
        if not mood_key:
            moods_list = ", ".join(STATUS_MOODS.keys())
            return await event.reply(f"🎭 **PARADOX Status Modes**\n\n**Available:** `{moods_list}`\n\n**Usage:** `.setstatus coding`\n**Revert:** `.setstatus reverse`")
            
        if mood_key == "reverse":
            if not RUNNING_TASKS["status"]["active"]:
                return await event.reply("⚠️ No active status to reverse.")
                
            msg = await event.reply("🔄 **Reversing status to original...**")
            me = await event.client.get_me()
            
            # Revert PFP
            last_id = RUNNING_TASKS["status"].get("last_photo_id")
            last_hash = RUNNING_TASKS["status"].get("last_photo_hash")
            if last_id and last_hash:
                try:
                    from telethon.tl.types import InputPhoto
                    from telethon.tl.functions.photos import DeletePhotosRequest
                    await event.client(DeletePhotosRequest(id=[InputPhoto(id=last_id, access_hash=last_hash, file_reference=b'')]))
                except Exception:
                    pass
            
            # Revert Bio and Name
            orig_first = RUNNING_TASKS["status"].get("original_first") or (me.first_name if me.first_name else "User")
            orig_last = RUNNING_TASKS["status"].get("original_last") or ""
            orig_bio = RUNNING_TASKS["status"].get("original_bio") or ""
            
            try:
                await event.client(functions.account.UpdateProfileRequest(
                    first_name=orig_first,
                    last_name=orig_last,
                    about=orig_bio
                ))
            except Exception:
                pass
                
            paused_tasks = RUNNING_TASKS["status"].get("paused_tasks", [])
            restarted_msg = ""
            for t in paused_tasks:
                if t in RUNNING_TASKS:
                    RUNNING_TASKS[t]["running"] = True
                    if t == "autoname": CipherElite.loop.create_task(loop_autoname(event.client))
                    elif t == "autobio": CipherElite.loop.create_task(loop_autobio(event.client))
                    elif t == "digitalpfp": CipherElite.loop.create_task(loop_digitalpfp(event.client))
                    elif t == "forgepfp": CipherElite.loop.create_task(loop_forgepfp(event.client))
            if paused_tasks:
                restarted_msg = f"\n▶️ **Restarted tasks:** `{', '.join(paused_tasks)}`"
                
            RUNNING_TASKS["status"] = {"active": False, "mood": "", "frame": 0, "original_first": None, "original_last": None, "original_bio": None, "last_photo_id": None, "last_photo_hash": None, "paused_tasks": []}
            save_state()
            await msg.edit(f"✅ **Original profile restored.**{restarted_msg}")
            return

        if mood_key not in STATUS_MOODS:
            return await event.reply(f"❌ **Invalid mood!** Choose from: `{', '.join(STATUS_MOODS.keys())}`")
            
        mood = STATUS_MOODS[mood_key]
        msg = await event.reply(f"🔄 **Setting Status:** `{mood['text']}`...")
        
        if not RUNNING_TASKS["status"]["active"]:
            paused_tasks = []
            for t in ["autoname", "autobio", "digitalpfp", "forgepfp"]:
                if t in RUNNING_TASKS and isinstance(RUNNING_TASKS[t], dict) and RUNNING_TASKS[t].get("running"):
                    paused_tasks.append(t)
                    RUNNING_TASKS[t]["running"] = False
            RUNNING_TASKS["status"]["paused_tasks"] = paused_tasks
            
            me = await event.client.get_me()
            try:
                full = await event.client(functions.users.GetFullUserRequest(id="me"))
                bio = getattr(full.full_user, 'about', "") or ""
            except Exception:
                try:
                    full = await event.client(functions.users.GetFullUserRequest(id=me.id))
                    bio = getattr(full.full_user, 'about', "") or ""
                except Exception:
                    bio = ""
                
            first = me.first_name or "USER"
            if " | " in first:
                first = first.split(" | ")[0].strip()
                
            RUNNING_TASKS["status"]["original_first"] = first
            RUNNING_TASKS["status"]["original_last"] = me.last_name or ""
            RUNNING_TASKS["status"]["original_bio"] = bio
        else:
            for t in ["autoname", "autobio", "digitalpfp", "forgepfp"]:
                if t in RUNNING_TASKS and isinstance(RUNNING_TASKS[t], dict) and RUNNING_TASKS[t].get("running"):
                    RUNNING_TASKS[t]["running"] = False
                    
        RUNNING_TASKS["status"]["active"] = True
        
        # 1. Update Name and Bio
        new_first = f"{RUNNING_TASKS['status']['original_first']}{mood['suffix']}"
        new_bio = f"{mood['emoji']} {mood['bio']}"
        
        try:
            await event.client(functions.account.UpdateProfileRequest(
                first_name=new_first[:64], 
                about=new_bio[:70]
            ))
        except FloodWaitError as e:
            await msg.edit(f"❌ **FloodWait:** {e.seconds}s. Try again later.")
            return
            
        RUNNING_TASKS["status"]["mood"] = mood_key
        RUNNING_TASKS["status"]["frame"] = 0
        
        save_state()
        CipherElite.loop.create_task(loop_status(event.client))
        await msg.edit(f"🎭 **Status Updated!**\n\n✨ **Mood:** `{mood['text']}`\n✅ **Profile synced.**\n🔄 _PFP will animate every 5 mins._\n\n_Use `.setstatus reverse` to revert._")
