# =============================================================================
#  CipherElite Userbot Plugin
#
#  Plugin Name:    Username Tester
#  Description:    Generates, scores, and tests premium Telegram usernames.
# =============================================================================

import re
import asyncio
import random
import io
from telethon import events
from telethon.tl.functions.account import CheckUsernameRequest
from telethon.errors import FloodWaitError, UsernameInvalidError

from plugins.bot import add_handler
from utils.utils import CipherElite
from utils.decorators import rishabh

# Predefined keyword boosts (Expanded for better generation)
HIGH_DEMAND_ROOTS = [
    "ai", "fx", "pay", "hub", "lab", "x", "coin", "lux", "vip", "bot", 
    "app", "pro", "zen", "go", "hq", "meta", "web", "net", "sys", "sec", 
    "vpn", "dex", "cex", "swap", "trade", "fund", "bank", "cash", "bet", 
    "win", "play", "game", "art", "pic", "vid", "cam", "chat", "msg", 
    "sms", "call", "tap", "now", "new", "hot", "og", "ez", "api", "os", 
    "vr", "ar", "sol", "eth", "btc", "rizz", "gyat", "cap", "slay", "lit",
    "vibe", "sus", "drip", "goat", "npc", "mid", "flex", "sick", "fr", "ong"
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

def rate_username(uname: str) -> int:
    """Rates a username based on the user's specific rules out of 100."""
    uname = uname.lower()
    score = 50  # Base logic score
    
    length = len(uname)
    
    # 1. Length priority (Rule 1 & Rule 9)
    # The shorter the better, max priority to 5 (since 3-4 is blocked).
    if length == 5: score += 25
    elif length == 6: score += 15
    elif length == 7: score += 10
    elif length == 8: score += 5
    elif length > 13: score -= (length - 13) * 3
    elif length < 5: score -= 50  # Invalid for standard users
        
    # 2. Number & Underscore penalty (Rule 6)
    nums = len(re.findall(r'\d', uname))
    if nums > 0:
        score -= (nums * 15)  # Harsh penalty
    if "_" in uname:
        score -= min(uname.count("_") * 15, 30)
        
    # 3. High Demand Niches (Rule 4)
    for root in HIGH_DEMAND_ROOTS:
        if root in uname:
            score += 15
            break
            
    # 4. Repeating letters / symmetry  (Rule 7)
    if re.search(r'([a-z])\1', uname):
        score += 5
        
    # 5. Unpronounceable penalty - 3 or more continuous consonants (Rule 5)
    # Treating 'y' as a consonant for stricter testing
    if re.search(r'[bcdfghjklmnpqrstvwxz]{3,}', uname):
        score -= 25
        
    # 6. Pronounceability Boost - Alternating Vowel/Consonant combinations
    vowels = "aeiou"
    alternating_score = 0
    for i in range(len(uname) - 1):
        if (uname[i] in vowels) != (uname[i+1] in vowels):
            alternating_score += 4
    score += min(alternating_score, 20)  # Max +20 boost for very pronounceable names

    # Cap score boundaries
    return min(max(int(score), 0), 100)

def generate_candidates(keyword: str):
    """Permutates the keyword intelligently to find 5-13 chars combinations."""
    keyword = keyword.lower()
    keyword = re.sub(r'[^a-z]', '', keyword)  # Sanitize
    
    candidates = set()
    if 5 <= len(keyword) <= 13:
        candidates.add(keyword)
    
    # Prefixes
    for p in PREFIXES:
        cand = p + keyword
        if 5 <= len(cand) <= 13: candidates.add(cand)
        
    # Suffixes
    for s in SUFFIXES:
        cand = keyword + s
        if 5 <= len(cand) <= 13: candidates.add(cand)
        
    # Roots combinations
    for r in HIGH_DEMAND_ROOTS:
        cand1 = keyword + r
        cand2 = r + keyword
        if 5 <= len(cand1) <= 13: candidates.add(cand1)
        if 5 <= len(cand2) <= 13: candidates.add(cand2)

    return list(candidates)

def generate_auto_candidates(count=100):
    """Generates pure random premium candidates without a specific keyword."""
    candidates = set()
    roots_list = HIGH_DEMAND_ROOTS
    
    # Generate by combining 2 roots, or prefix+root, or root+suffix
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
            
        if 5 <= len(cand) <= 13:
            candidates.add(cand)
            
    return list(candidates)


def init(client):
    commands = [
        ".uname rate <username> - Rate a username from 0-100",
        ".uname test [keyword] - Generate & test best available usernames (auto-generates if no keyword)"
    ]
    desc = "Score & automatically test brandable 5-13 character Telegram usernames."
    add_handler("username", commands, desc)


@CipherElite.on(events.NewMessage(pattern=r"\.uname\s+rate\s+([a-zA-Z0-9_]+)"))
@rishabh()
async def rate_cmd(event):
    uname = event.pattern_match.group(1).lstrip("@")
    score = rate_username(uname)
    
    msg = f"🔍 **Username:** `@{uname}`\n"
    msg += f"📊 **Score:** `{score}/100`"
    if score >= 80:
        msg += " ✨ (**Premium Tier**)"
    elif score >= 60:
        msg += " 👍 (**Good Tier**)"
    else:
        msg += " 🛑 (**Poor Tier**)"
        
    await event.reply(msg)

@CipherElite.on(events.NewMessage(pattern=r"\.uname\s+test(?:\s+(.+))?"))
@rishabh()
async def test_cmd(event):
    keyword = event.pattern_match.group(1)
    
    if keyword:
        keyword = keyword.strip()
        status = await event.reply(f"⏳ **Generating candidates for:** `{keyword}`...")
        candidates = generate_candidates(keyword)
        fail_msg = "❌ Could not generate valid 5-13 character candidates. Try a shorter keyword."
    else:
        status = await event.reply(f"⏳ **Auto-generating premium candidates...**")
        candidates = generate_auto_candidates(75)
        fail_msg = "❌ Failed to auto-generate candidates."
        keyword = "Auto-Gen"

    if not candidates:
        return await status.edit(fail_msg)
        
    # Score them
    scored = [(cand, rate_username(cand)) for cand in candidates]
    
    # Sort all by score (descending)
    all_candidates = sorted(scored, key=lambda x: x[1], reverse=True)
        
    await status.edit(f"🔍 **Found {len(all_candidates)} candidates.**\n"
                      f"Testing availability with Telegram API (this will take a moment)...")
    
    available = []
    checked_count = 0
    error_count = 0
    
    for uname, score in all_candidates:
        checked_count += 1
        
        # Update progress every 15 checks so the bot doesn't seem stuck
        if checked_count % 15 == 0:
            try:
                await status.edit(f"🔍 **Found {len(all_candidates)} candidates.**\n"
                                  f"Testing availability... (Checked {checked_count}/{len(all_candidates)})")
            except Exception:
                pass
                
        try:
            # Pings telegram to check if uname is unassigned unconditionally
            is_free = await event.client(CheckUsernameRequest(uname))
            if is_free:
                available.append(f"✅ `@{uname}` — **Score: {score}**")
                
            # Only store up to 100 available max as specified by user
            if len(available) >= 100:
                break
                
            await asyncio.sleep(2)  # Delay between requests to avoid rapid FloodWait
            error_count = 0  # Reset error count on success
            
        except FloodWaitError as e:
            # We must respect Telegram's API FloodWaits fully
            await event.reply(f"⚠️ **Telegram API Limit Reached.**\n"
                              f"Checked stopped. We must wait **{e.seconds} seconds** before checking more.\n"
                              f"Proceeding with what we found...")
            break
        except UsernameInvalidError:
            continue
        except Exception as e:
            err_name = type(e).__name__
            if "UsernamePurchaseAvailable" in err_name:
                # It's not fully free, but available for purchase on Telegram Fragment!
                available.append(f"💎 `@{uname}` — **Score: {score}** (Fragment Purchase)")
                continue
            elif "Occupied" in err_name or "Taken" in err_name:
                continue
            else:
                error_count += 1
                await event.reply(f"⚠️ **Internal Error on `@{uname}`:** {err_name}: {str(e)}. Skipping...")
                if error_count >= 3:
                    await event.reply(f"🛑 **Too many consecutive errors. Cancelling remaining checks...**")
                    break
                continue
            
    if available:
        if len(available) > 15:
            # Export to file to avoid spamming the chat
            clean_text = f"Top Available Usernames for '{keyword}'\n" + "="*40 + "\n"
            for item in available:
                # Remove markdown characters for the text file
                clean_item = item.replace("**", "").replace("`", "")
                clean_text += f"{clean_item}\n"
                
            file = io.BytesIO(clean_text.encode('utf-8'))
            file.name = f"Available_Usernames.txt"
            
            await event.reply(f"🎯 **Found {len(available)} available usernames!** (Checked {checked_count}/{len(all_candidates)})\n"
                              f"Uploading results as a file to keep chat clean...", file=file)
            await status.delete()
        else:
            text = f"🎯 **Available Usernames for `{keyword}` (Checked {checked_count}/{len(all_candidates)})**\n\n"
            text += "\n".join(available)
            await status.edit(text)
    else:
        text = f"❌ **All generated usernames for `{keyword}` are already taken or invalid. (Checked {checked_count}/{len(all_candidates)})**"
        await status.edit(text)
