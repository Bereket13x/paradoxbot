# =============================================================================
#  CipherElite Userbot Plugin
#
#  Plugin Name:    Channel Creator (mkchan)
#  Author:         CipherElite Plugins
#  Description:    Create Telegram channels with custom or auto-generated
#                  names and usernames. Supports bulk creation.
# =============================================================================

import asyncio
import random
import re
import string

from telethon import events, functions
from telethon.errors import (
    FloodWaitError,
    UsernameInvalidError,
    UsernameNotModifiedError,
    UsernameOccupiedError,
)
from telethon.tl.functions.account import CheckUsernameRequest
from telethon.tl.functions.channels import CreateChannelRequest, UpdateUsernameRequest

from plugins.bot import add_handler
from utils.utils import CipherElite
from utils.decorators import rishabh

# ── Word Pool for Auto Generation ─────────────────────────────────────────────

_PREFIXES = [
    "apex", "nova", "nexus", "cipher", "phantom", "echo", "vortex", "pulse",
    "sigma", "delta", "alpha", "omega", "neon", "prism", "arc", "zenith",
    "orbit", "solar", "ultra", "hyper", "meta", "cyber", "ghost", "blaze",
    "storm", "swift", "sharp", "dark", "stark", "void", "steel", "iron",
    "flux", "byte", "code", "axon", "halo", "dusk", "dawn", "peak",
]

_SUFFIXES = [
    "hub", "net", "lab", "base", "core", "zone", "wave", "link", "grid",
    "feed", "node", "vault", "space", "gate", "point", "source", "stream",
    "pulse", "forge", "edge", "realm", "studio", "media", "world", "unit",
    "center", "tower", "bay", "clan", "crew", "squad", "house", "data",
    "bot", "ai", "tech", "pro", "plus", "x", "hq", "official",
]

_DISPLAY_ADJECTIVES = [
    "Apex", "Nova", "Nexus", "Cipher", "Phantom", "Echo", "Vortex", "Pulse",
    "Sigma", "Alpha", "Neon", "Prism", "Zenith", "Orbit", "Hyper",
    "Cyber", "Blaze", "Storm", "Swift", "Dark", "Void", "Steel", "Flux",
    "Byte", "Axon", "Halo", "Dawn", "Peak", "Ultra", "Meta",
]

_DISPLAY_NOUNS = [
    "Hub", "Network", "Labs", "Base", "Core", "Zone", "Link", "Grid",
    "Feed", "Vault", "Space", "Gate", "Forge", "Edge", "Realm",
    "Studio", "Media", "World", "Tower", "Squad", "House", "Tech",
    "Channel", "Official", "HQ", "Stream", "Data", "Intelligence",
]


# ── Plugin Registration ────────────────────────────────────────────────────────

def init(client):
    commands = [
        ".mkchan <title> [@username]       — Create 1 channel (auto username if omitted)",
        ".mkchan <title> [@username] <n>   — Create n channels (username gets _2, _3 …)",
        ".mkchan auto [n]                  — Create n fully auto channels (default: 1)",
    ]
    desc = (
        "📢 Create Telegram channels instantly — manual, semi-auto, or fully auto "
        "with availability-checked usernames. Supports bulk creation."
    )
    add_handler("mkchan", commands, desc)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _random_username() -> str:
    """Generate a plausible, Telegram-valid username (5–32 chars, a-z0-9_)."""
    prefix = random.choice(_PREFIXES)
    suffix = random.choice(_SUFFIXES)
    # Optionally insert a short number for uniqueness
    mid = str(random.randint(0, 999)) if random.random() < 0.4 else ""
    sep = "_" if random.random() < 0.5 else ""
    candidate = f"{prefix}{sep}{mid}{suffix}" if mid else f"{prefix}{sep}{suffix}"
    # Telegram: 5–32 chars, only a-z A-Z 0-9 _
    candidate = re.sub(r"[^a-z0-9_]", "", candidate.lower())
    # Ensure minimum length
    if len(candidate) < 5:
        candidate += "".join(random.choices(string.digits, k=5 - len(candidate)))
    return candidate[:32]


def _random_display_name() -> str:
    """Generate a clean human-readable channel display name."""
    adj = random.choice(_DISPLAY_ADJECTIVES)
    noun = random.choice(_DISPLAY_NOUNS)
    # Sometimes add a number suffix for uniqueness
    suffix = f" {random.randint(2, 99)}" if random.random() < 0.3 else ""
    return f"{adj} {noun}{suffix}"


async def _is_username_available(client, username: str) -> bool:
    """Return True if the username is free to use."""
    try:
        result = await client(CheckUsernameRequest(username=username))
        return bool(result)
    except (UsernameInvalidError, UsernameOccupiedError):
        return False
    except Exception:
        return False


async def _find_available_username(client, base: str, retries: int = 20) -> str | None:
    """
    Try `base` first; if taken, append random digits and retry up to `retries` times.
    Returns the first available username found, or None.
    """
    # Try the exact base first
    clean = re.sub(r"[^a-z0-9_]", "", base.lower().lstrip("@"))[:32]
    if len(clean) >= 5 and await _is_username_available(client, clean):
        return clean

    for _ in range(retries):
        candidate = _random_username()
        if await _is_username_available(client, candidate):
            return candidate
        await asyncio.sleep(0.3)   # small delay to avoid hammering

    return None


async def _create_one_channel(client, title: str, username: str | None, status_msg, label: str) -> dict:
    """
    Creates a single channel, optionally sets its username.
    Returns dict with keys: title, username, link, ok, error.
    """
    try:
        result = await client(
            CreateChannelRequest(
                title=title,
                about=f"Channel created by PARADOX • {title}",
                broadcast=True,
                megagroup=False,
            )
        )
        channel = result.chats[0]
        set_username = None

        if username:
            try:
                await client(UpdateUsernameRequest(channel=channel, username=username))
                set_username = username
            except (UsernameOccupiedError, UsernameInvalidError):
                set_username = None   # username was taken at the last second
            except UsernameNotModifiedError:
                set_username = username

        link = f"t.me/{set_username}" if set_username else f"tg://openmessage?chat_id={channel.id}"
        return {"title": title, "username": set_username, "link": link, "ok": True, "error": None}

    except FloodWaitError as e:
        return {"title": title, "username": None, "link": None, "ok": False, "error": f"FloodWait {e.seconds}s"}
    except Exception as e:
        return {"title": title, "username": None, "link": None, "ok": False, "error": str(e)}


# ── Commands ──────────────────────────────────────────────────────────────────

@CipherElite.on(events.NewMessage(pattern=r"\.mkchan(?:\s+([\s\S]+))?$"))
@rishabh()
async def mkchan_cmd(event):
    """
    Usage:
      .mkchan <title> [@username]         → 1 channel, optional custom username
      .mkchan <title> [@username] <n>     → n channels, custom username base
      .mkchan auto [n]                    → n fully auto channels
    """
    raw = (event.pattern_match.group(1) or "").strip()
    if not raw:
        return await event.reply(
            "📢 **Channel Creator — Usage:**\n\n"
            "`.mkchan My Channel` — creates 1 channel, auto username\n"
            "`.mkchan My Channel @mychan` — creates 1 channel with `@mychan`\n"
            "`.mkchan My Channel @mychan 5` — creates 5 channels (`@mychan`, `@mychan_2`…)\n"
            "`.mkchan auto 3` — creates 3 fully auto channels\n\n"
            "⚠️ Username availability is checked before each channel is created."
        )

    client = event.client
    msg = await event.reply("⏳ **Processing your request...**")

    # ── Mode 1: Fully auto ────────────────────────────────────────────────────
    if raw.startswith("auto"):
        parts = raw.split()
        count = 1
        if len(parts) >= 2 and parts[1].isdigit():
            count = max(1, min(int(parts[1]), 20))  # cap at 20

        await msg.edit(f"🤖 **Auto Channel Creator**\nGenerating **{count}** channel(s)...")

        results = []
        for i in range(count):
            await msg.edit(
                f"🤖 **Auto Channel Creator**\n"
                f"⏳ Creating channel **{i+1}/{count}** — finding available username..."
            )
            title = _random_display_name()
            username = await _find_available_username(client, _random_username())
            res = await _create_one_channel(client, title, username, msg, f"{i+1}/{count}")
            results.append(res)
            await asyncio.sleep(1.5)  # pace between creations

        # Build summary
        ok = [r for r in results if r["ok"]]
        fail = [r for r in results if not r["ok"]]
        lines = ["📢 **Auto Channel Creation — Done!**\n"]
        for r in ok:
            u = f"@{r['username']}" if r["username"] else "_(no username set)_"
            lines.append(f"✅ **{r['title']}** • {u} • [Open]({r['link']})")
        for r in fail:
            lines.append(f"❌ **{r['title']}** — `{r['error']}`")
        lines.append(f"\n**{len(ok)}/{count}** created successfully.")
        return await msg.edit("\n".join(lines), link_preview=False)

    # ── Parse: title, optional @username, optional count ──────────────────────
    # Patterns:
    #   "My Channel"
    #   "My Channel @handle"
    #   "My Channel @handle 5"
    #   "My Channel 5"
    count = 1
    username_base = None

    # Try to pull trailing integer (count)
    count_m = re.search(r"\s+(\d+)$", raw)
    if count_m:
        count = max(1, min(int(count_m.group(1)), 20))
        raw = raw[:count_m.start()].strip()

    # Try to pull a @username token anywhere in raw
    uname_m = re.search(r"@([a-zA-Z][a-zA-Z0-9_]{3,31})", raw)
    if uname_m:
        username_base = uname_m.group(1).lower()
        raw = (raw[:uname_m.start()] + raw[uname_m.end():]).strip()

    title_base = raw.strip()
    if not title_base:
        return await msg.edit("❌ Please provide a channel title.")

    await msg.edit(
        f"📢 **Channel Creator**\n"
        f"📝 Title: `{title_base}`\n"
        f"🔤 Username: `{'@' + username_base if username_base else 'auto'}`\n"
        f"📦 Count: `{count}`\n\n"
        f"⏳ Finding available usernames..."
    )

    results = []
    for i in range(count):
        # Build title for this iteration
        title = title_base if count == 1 else f"{title_base} {i+1}"

        # Build username for this iteration
        if username_base:
            candidate_base = username_base if i == 0 else f"{username_base}_{i+1}"
        else:
            candidate_base = _random_username()

        await msg.edit(
            f"📢 **Channel Creator** — `{i+1}/{count}`\n"
            f"📝 Title: `{title}`\n"
            f"🔍 Checking username availability..."
        )

        username = await _find_available_username(client, candidate_base)
        if not username:
            results.append({
                "title": title, "username": None, "link": None,
                "ok": False, "error": "No available username found after retries"
            })
            await asyncio.sleep(1)
            continue

        await msg.edit(
            f"📢 **Channel Creator** — `{i+1}/{count}`\n"
            f"📝 Title: `{title}`\n"
            f"✅ Username available: `@{username}`\n"
            f"⏳ Creating channel..."
        )

        res = await _create_one_channel(client, title, username, msg, f"{i+1}/{count}")
        results.append(res)
        await asyncio.sleep(2)  # Avoid FloodWait between bulk creates

    # ── Final Summary ──────────────────────────────────────────────────────────
    ok = [r for r in results if r["ok"]]
    fail = [r for r in results if not r["ok"]]
    lines = [f"📢 **Channel Creation Complete!**\n"]
    for r in ok:
        u = f"@{r['username']}" if r["username"] else "_(no username set)_"
        lines.append(f"✅ **{r['title']}** • {u}\n   👉 [Open Channel]({r['link']})")
    for r in fail:
        lines.append(f"❌ **{r['title']}** — `{r['error']}`")
    lines.append(f"\n**{len(ok)}/{count}** created successfully.")
    await msg.edit("\n".join(lines), link_preview=False)
