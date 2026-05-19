import re
import asyncio
import random
import io
import aiohttp
from telethon import events

from plugins.bot import add_handler
from utils.utils import CipherElite
from utils.decorators import rishabh

TIKTOK_ROOTS = [
    "fyp", "viral", "trend", "tok", "vibe", "clip", "cast", "ai", "hub", "lab", "x", 
    "lux", "vip", "bot", "app", "pro", "zen", "go", "hq", "meta", "web", "net", 
    "sys", "sec", "vpn", "dex", "cex", "swap", "trade", "fund", "bank", "cash", 
    "bet", "win", "play", "game", "art", "pic", "vid", "cam", "chat", "msg", 
    "sms", "call", "tap", "now", "new", "hot", "og", "ez", "api", "os", 
    "vr", "ar", "sol", "eth", "btc", "rizz", "gyat", "cap", "slay", "lit",
    "sus", "drip", "goat", "npc", "mid", "flex", "sick", "fr", "ong"
]

PREFIXES = [
    "neo", "ultra", "meta", "alpha", "prime", "nova", "zen", "astro", "luna",
    "quant", "hyper", "elite", "royal", "gold", "silver", "crypto", "coin",
    "block", "chain", "vault", "trade", "fin", "cash", "bank", "pay", "smart",
    "auto", "rapid", "turbo", "speed", "flash", "storm", "volt", "pixel",
    "cyber", "data", "byte", "code", "logic", "matrix", "core", "dark",
    "light", "blue", "red", "black", "white", "green", "urban", "global",
    "world", "city", "sky", "star", "sun", "moon", "cloud", "air", "fire",
    "ice", "wave", "ocean", "terra", "eco", "bio", "med", "health", "vita",
    "fit", "sport", "game", "play", "pro", "vip", "max", "mega", "super",
    "top", "best", "first", "next", "future", "trend", "rise", "peak",
    "edge", "plus", "x", "z", "q", "omni", "infi", "pure", "true", "swift"
]

SUFFIXES = [
    "x", "z", "pro", "vip", "hub", "lab", "zone", "world", "base", "core",
    "point", "space", "net", "link", "chain", "vault", "bank", "pay", "coin",
    "cash", "trade", "fund", "capital", "market", "flow", "wave", "storm",
    "boost", "drive", "jet", "shift", "sync", "grid", "node", "logic", "byte",
    "code", "data", "tech", "ware", "soft", "host", "cloud", "ai", "bot",
    "app", "go", "now", "plus", "max", "prime", "elite", "royal", "gold",
    "one", "first", "top", "best", "star", "sky", "nova", "zen", "ly", "ify",
    "ster", "ifyx", "verse", "port", "land", "city", "spot", "arena", "club",
    "house", "room", "desk", "line", "lane", "path", "gate", "door", "view",
    "vision", "scope", "rise", "peak", "edge", "pulse", "spark", "mint",
    "fox", "hawk", "lion", "wolf", "labs", "io"
]

def rate_tiktok_uname(uname: str) -> int:
    uname = uname.lower()
    score = 50 
    
    length = len(uname)
    if length == 2: score += 40
    elif length == 3: score += 35
    elif length == 4: score += 25
    elif length == 5: score += 15
    elif length == 6: score += 10
    elif length == 7: score += 5
    elif length > 15: score -= (length - 15) * 3
    elif length < 2: score -= 50

    if re.search(r'[bcdfghjklmnpqrstvwxz]{3,}', uname):
        score -= 25
        
    vowels = "aeiou"
    alternating_score = 0
    for i in range(len(uname) - 1):
        if (uname[i] in vowels) != (uname[i+1] in vowels):
            alternating_score += 4
    score += min(alternating_score, 20)

    return min(max(int(score), 0), 100)

def generate_tiktok_candidates(keyword: str):
    keyword = keyword.lower()
    keyword = re.sub(r'[^a-z0-9]', '', keyword) 
    
    candidates = set()
    if 2 <= len(keyword) <= 15:
        candidates.add(keyword)
    
    for p in PREFIXES:
        cand = p + keyword
        if 2 <= len(cand) <= 15: candidates.add(cand)
        
    for s in SUFFIXES:
        cand = keyword + s
        if 2 <= len(cand) <= 15: candidates.add(cand)
        
    for r in TIKTOK_ROOTS:
        cand1 = keyword + r
        cand2 = r + keyword
        if 2 <= len(cand1) <= 15: candidates.add(cand1)
        if 2 <= len(cand2) <= 15: candidates.add(cand2)

    return list(candidates)

def generate_tiktok_auto_candidates(count=100):
    candidates = set()
    roots_list = TIKTOK_ROOTS
    
    attempts = 0
    while len(candidates) < count and attempts < count * 5:
        attempts += 1
        choice = random.randint(1, 4)
        if choice == 1:
            cand = random.choice(PREFIXES) + random.choice(roots_list)
        elif choice == 2:
            cand = random.choice(roots_list) + random.choice(SUFFIXES)
        elif choice == 3:
            cand = random.choice(roots_list) + random.choice(roots_list)
        else:
            cand = random.choice(PREFIXES) + random.choice(roots_list) + random.choice(SUFFIXES)
            
        if 2 <= len(cand) <= 15:
            candidates.add(cand)
            
    return list(candidates)

def init(client):
    commands = [
        ".tiktok rate <username> - Rate a TikTok username from 0-100",
        ".tiktok test [keyword] - Generate & test best available TikTok usernames"
    ]
    desc = "Score & test super premium 2-15 character TikTok usernames without triggering bans."
    add_handler("tiktok_tester", commands, desc)

@CipherElite.on(events.NewMessage(pattern=r"\.tiktok\s+rate\s+([a-zA-Z0-9]+)"))
@rishabh()
async def rate_tiktok_cmd(event):
    uname = event.pattern_match.group(1)
    score = rate_tiktok_uname(uname)
    
    msg = f"🎵 **TikTok Username:** `@{uname}`\n"
    msg += f"📊 **Score:** `{score}/100`"
    if score >= 80: msg += " ✨ (**Premium Tier**)"
    elif score >= 60: msg += " 👍 (**Good Tier**)"
    else: msg += " 🛑 (**Poor Tier**)"
        
    await event.reply(msg)

@CipherElite.on(events.NewMessage(pattern=r"\.tiktok\s+test(?:\s+(.+))?"))
@rishabh()
async def test_tiktok_cmd(event):
    keyword = event.pattern_match.group(1)
    
    if keyword:
        keyword = keyword.strip()
        status = await event.reply(f"⏳ **Generating TikTok candidates for:** `{keyword}`...")
        candidates = generate_tiktok_candidates(keyword)
        fail_msg = "❌ Could not generate valid 2-15 character candidates. Try a shorter keyword."
    else:
        status = await event.reply(f"⏳ **Auto-generating premium TikTok candidates...**")
        candidates = generate_tiktok_auto_candidates(75)
        fail_msg = "❌ Failed to auto-generate candidates."
        keyword = "Auto-Gen"

    if not candidates:
        return await status.edit(fail_msg)
        
    scored = [(cand, rate_tiktok_uname(cand)) for cand in candidates]
    all_candidates = sorted(scored, key=lambda x: x[1], reverse=True)
        
    available = []
    checked_count = 0
    error_count = 0
    
    async with aiohttp.ClientSession() as session:
        for uname, score in all_candidates:
            checked_count += 1
            
            if checked_count % 10 == 0:
                try:
                    await status.edit(f"🔍 **Found {len(all_candidates)} candidates.**\n"
                                      f"Testing TikTok availability via stealth web scraper... (Checked {checked_count}/{len(all_candidates)})\n"
                                      f"*(Taking 4 seconds per check to avoid CAPTCHA blocks)*")
                except Exception:
                    pass
                    
            try:
                url = f"https://www.tiktok.com/@{uname}"
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.4896.127 Safari/537.36"
                }
                async with session.get(url, headers=headers, timeout=10) as response:
                    # TikTok returns 404 naturally for missing users (often)
                    if response.status == 404:
                        available.append(f"✅ `@{uname}` — **Score: {score}**")
                    elif response.status == 200:
                        text = await response.text()
                        if "Couldn't find this account" in text:
                            available.append(f"✅ `@{uname}` — **Score: {score}**")
                    elif response.status == 429: # Rate limited
                        await event.reply(f"⚠️ **TikTok Rate Limit Reached.**\n"
                                          f"Checked stopped to protect IP. Please wait before trying again.")
                        break
                    
                if len(available) >= 100:
                    break
                    
                await asyncio.sleep(4)  # Safety delay 4 secs
                error_count = 0  # Reset error count on success
                
            except asyncio.TimeoutError:
                error_count += 1
                await event.reply(f"⚠️ **Timeout checking `@{uname}`.** Skipping...")
                if error_count >= 3:
                    await event.reply(f"🛑 **Too many consecutive errors. Cancelling remaining checks...**")
                    break
                continue
            except Exception as e:
                error_count += 1
                await event.reply(f"⚠️ **Web Scraper Error on `@{uname}`:** {type(e).__name__}: {str(e)}. Skipping...")
                if error_count >= 3:
                    await event.reply(f"🛑 **Too many consecutive errors. Cancelling remaining checks...**")
                    break
                continue
                
    if available:
        if len(available) > 15:
            clean_text = f"Top Available TikTok Usernames for '{keyword}'\n" + "="*40 + "\n"
            for item in available:
                clean_item = item.replace("**", "").replace("`", "")
                clean_text += f"{clean_item}\n"
                
            file = io.BytesIO(clean_text.encode('utf-8'))
            file.name = f"Available_TikToks.txt"
            
            await event.reply(f"🎵 **Found {len(available)} available TikToks!** (Checked {checked_count}/{len(all_candidates)})\n"
                              f"Uploading results as a file to keep chat clean...", file=file)
            await status.delete()
        else:
            text = f"🎵 **Available TikToks for `{keyword}` (Checked {checked_count}/{len(all_candidates)})**\n\n"
            text += "\n".join(available)
            await status.edit(text)
    else:
        text = f"❌ **All generated TikToks for `{keyword}` are already taken or invalid. (Checked {checked_count}/{len(all_candidates)})**"
        await status.edit(text)
