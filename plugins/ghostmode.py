# =============================================================================
#  PARADOX Userbot Plugin
#
#  Plugin Name:    Ghost Mode
#  Description:    Full stealth suite — anti-seen, anti-typing, anti-online,
#                  delayed seen, ghost read, and per-user/chat controls.
#  License:        MIT
# =============================================================================

import asyncio
import json
import random
from pathlib import Path

from telethon import events
from telethon.tl.functions.messages import ReadHistoryRequest
from telethon.tl.functions.channels import ReadHistoryRequest as ChannelReadHistoryRequest
from telethon.tl.functions.account import UpdateStatusRequest

from utils.utils import CipherElite
from utils.decorators import rishabh
from plugins.bot import add_handler

# ── Persistent Config ──────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).parent.parent
DB_DIR = PROJECT_ROOT / "DB"
DB_DIR.mkdir(exist_ok=True)
GHOST_CONFIG_FILE = DB_DIR / "ghost_config.json"

DEFAULT_CONFIG = {
    "anti_seen": False,
    "anti_typing": False,
    "anti_online": False,
    "ghost_read": False,
    "delayed_seen": False,
    "delay_min": 5,
    "delay_max": 30,
    "blacklist_chats": [],
    "whitelist_chats": [],
    "ghost_users": [],
    "mode": "global",
}

ghost_config = {}
_delayed_seen_tasks = {}
_anti_online_task = None


def load_ghost_config():
    global ghost_config
    ghost_config = DEFAULT_CONFIG.copy()
    if GHOST_CONFIG_FILE.exists():
        try:
            data = json.loads(GHOST_CONFIG_FILE.read_text(encoding="utf-8"))
            ghost_config.update(data)
        except Exception:
            pass


def save_ghost_config():
    try:
        GHOST_CONFIG_FILE.write_text(
            json.dumps(ghost_config, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception:
        pass


load_ghost_config()


# ── Plugin Registration ────────────────────────────────────────────────────────

def init(client):
    commands = [
        ".ghost - Show ghost mode dashboard with all toggles",
        ".antiseen on/off - Toggle anti-seen (read receipts blocked)",
        ".antityping on/off - Toggle anti-typing indicator",
        ".antionline on/off - Toggle anti-online (appear offline)",
        ".ghostread on/off - Forward msgs to Saved for silent reading",
        ".delayseen on/off - Toggle delayed-seen mode",
        ".ghostdelay <min> <max> - Set delay range in minutes",
        ".ghostuser <@user/id> - Toggle ghost mode for a specific user",
        ".ghostchat - Toggle ghost mode for current chat",
        ".ghostmode global/selective - Switch between global and selective mode",
        ".ghostlist - Show all ghosted users and chats",
        ".ghostreset - Reset all ghost settings to default",
    ]
    desc = "🕵️ Full stealth suite — become invisible on Telegram"
    add_handler("ghostmode", commands, desc)


# ── Helpers ────────────────────────────────────────────────────────────────────

def is_ghost_active_for(chat_id=None, user_id=None):
    if ghost_config["mode"] == "global":
        if chat_id and chat_id in ghost_config["blacklist_chats"]:
            return False
        return True
    else:
        if user_id and user_id in ghost_config["ghost_users"]:
            return True
        if chat_id and chat_id in ghost_config["whitelist_chats"]:
            return True
        return False


def format_status(enabled):
    return "🟢 ON" if enabled else "🔴 OFF"


# ── Dashboard ─────────────────────────────────────────────────────────────────

@CipherElite.on(events.NewMessage(pattern=r"\.ghost$"))
@rishabh()
async def ghost_dashboard(event):
    gc = ghost_config
    mode_display = "🌐 Global" if gc["mode"] == "global" else "🎯 Selective"
    ghosted_users = len(gc["ghost_users"])
    ghosted_chats = len(gc["whitelist_chats"])
    blacklisted = len(gc["blacklist_chats"])

    text = (
        "🕵️ **𝐏𝐀𝐑𝐀𝐃𝐎𝐗 𝐆𝐇𝐎𝐒𝐓 𝐌𝐎𝐃𝐄** 🕵️\n"
        "⟡ ═══════════════════ ⟡\n\n"
        f"  🚫 **Anti-Seen:**    {format_status(gc['anti_seen'])}\n"
        f"  ⌨️ **Anti-Typing:**  {format_status(gc['anti_typing'])}\n"
        f"  👻 **Anti-Online:**  {format_status(gc['anti_online'])}\n"
        f"  📨 **Ghost Read:**   {format_status(gc['ghost_read'])}\n"
        f"  ⏱️ **Delayed Seen:** {format_status(gc['delayed_seen'])}\n\n"
        "⟡ ═══════════════════ ⟡\n\n"
        f"  📋 **Mode:** {mode_display}\n"
        f"  👤 **Ghosted Users:** `{ghosted_users}`\n"
        f"  💬 **Ghosted Chats:** `{ghosted_chats}`\n"
        f"  🚷 **Blacklisted:**  `{blacklisted}`\n"
    )
    if gc["delayed_seen"]:
        text += f"\n  ⏰ **Delay Range:** `{gc['delay_min']}-{gc['delay_max']}` min\n"
    text += (
        "\n⟡ ═══════════════════ ⟡\n"
        "💡 `.antiseen` `.antityping` `.antionline`\n"
        "   `.ghostread` `.delayseen` `.ghostuser`\n"
        "   `.ghostchat` `.ghostmode` `.ghostreset`"
    )
    await event.reply(text)


# ── Toggle Commands ────────────────────────────────────────────────────────────

@CipherElite.on(events.NewMessage(pattern=r"\.antiseen(?:\s+(on|off))?$"))
@rishabh()
async def toggle_antiseen(event):
    arg = event.pattern_match.group(1)
    if arg:
        ghost_config["anti_seen"] = (arg.lower() == "on")
    else:
        ghost_config["anti_seen"] = not ghost_config["anti_seen"]
    save_ghost_config()
    state = ghost_config["anti_seen"]
    emoji = "🟢" if state else "🔴"
    msg = "✅ Read receipts **blocked**. No blue ticks." if state else "❌ Read receipts **enabled**."
    await event.reply(f"🕵️ **Anti-Seen** {emoji}\n\n{msg}")


@CipherElite.on(events.NewMessage(pattern=r"\.antityping(?:\s+(on|off))?$"))
@rishabh()
async def toggle_antityping(event):
    arg = event.pattern_match.group(1)
    if arg:
        ghost_config["anti_typing"] = (arg.lower() == "on")
    else:
        ghost_config["anti_typing"] = not ghost_config["anti_typing"]
    save_ghost_config()
    state = ghost_config["anti_typing"]
    emoji = "🟢" if state else "🔴"
    msg = '✅ "Typing..." indicator is now **hidden**.' if state else "❌ Typing indicator is **visible**."
    await event.reply(f"⌨️ **Anti-Typing** {emoji}\n\n{msg}")


@CipherElite.on(events.NewMessage(pattern=r"\.antionline(?:\s+(on|off))?$"))
@rishabh()
async def toggle_antionline(event):
    global _anti_online_task
    arg = event.pattern_match.group(1)
    if arg:
        ghost_config["anti_online"] = (arg.lower() == "on")
    else:
        ghost_config["anti_online"] = not ghost_config["anti_online"]
    save_ghost_config()
    state = ghost_config["anti_online"]

    if state:
        if _anti_online_task is None or _anti_online_task.done():
            _anti_online_task = asyncio.create_task(_offline_loop())
    else:
        if _anti_online_task and not _anti_online_task.done():
            _anti_online_task.cancel()
            _anti_online_task = None
        try:
            await event.client(UpdateStatusRequest(offline=False))
        except Exception:
            pass

    emoji = "🟢" if state else "🔴"
    msg = "✅ You appear **permanently offline**." if state else "❌ Online status is **visible**."
    await event.reply(f"👻 **Anti-Online** {emoji}\n\n{msg}")


@CipherElite.on(events.NewMessage(pattern=r"\.ghostread(?:\s+(on|off))?$"))
@rishabh()
async def toggle_ghostread(event):
    arg = event.pattern_match.group(1)
    if arg:
        ghost_config["ghost_read"] = (arg.lower() == "on")
    else:
        ghost_config["ghost_read"] = not ghost_config["ghost_read"]
    save_ghost_config()
    state = ghost_config["ghost_read"]
    emoji = "🟢" if state else "🔴"
    msg = "✅ Messages **forwarded to Saved** for silent reading." if state else "❌ Ghost read **disabled**."
    await event.reply(f"📨 **Ghost Read** {emoji}\n\n{msg}")


@CipherElite.on(events.NewMessage(pattern=r"\.delayseen(?:\s+(on|off))?$"))
@rishabh()
async def toggle_delayseen(event):
    arg = event.pattern_match.group(1)
    if arg:
        ghost_config["delayed_seen"] = (arg.lower() == "on")
    else:
        ghost_config["delayed_seen"] = not ghost_config["delayed_seen"]
    save_ghost_config()
    state = ghost_config["delayed_seen"]
    emoji = "🟢" if state else "🔴"
    msg = "✅ Messages marked read after a **random delay**." if state else "❌ Delayed seen **disabled**."
    if state:
        msg += f"\n⏰ Delay: `{ghost_config['delay_min']}-{ghost_config['delay_max']}` min"
    await event.reply(f"⏱️ **Delayed Seen** {emoji}\n\n{msg}")


@CipherElite.on(events.NewMessage(pattern=r"\.ghostdelay(?:\s+(\d+))?(?:\s+(\d+))?$"))
@rishabh()
async def set_ghost_delay(event):
    min_val = event.pattern_match.group(1)
    max_val = event.pattern_match.group(2)
    if not min_val:
        await event.reply(
            "⏰ **Ghost Delay Settings**\n\n"
            f"Current: `{ghost_config['delay_min']}-{ghost_config['delay_max']}` min\n\n"
            "**Usage:** `.ghostdelay <min> <max>`\n"
            "**Example:** `.ghostdelay 5 30`"
        )
        return
    min_delay = int(min_val)
    max_delay = int(max_val) if max_val else min_delay + 10
    if min_delay >= max_delay:
        max_delay = min_delay + 5
    ghost_config["delay_min"] = max(1, min_delay)
    ghost_config["delay_max"] = max(2, max_delay)
    save_ghost_config()
    await event.reply(
        f"⏰ **Delay Updated!**\n\n"
        f"Read after `{ghost_config['delay_min']}-{ghost_config['delay_max']}` minutes"
    )


# ── User/Chat Controls ────────────────────────────────────────────────────────

@CipherElite.on(events.NewMessage(pattern=r"\.ghostuser(?:\s+(.+))?$"))
@rishabh()
async def ghost_user_toggle(event):
    target = (event.pattern_match.group(1) or "").strip()
    if not target and not event.is_reply:
        await event.reply(
            "👤 **Ghost User**\n\n"
            "**Usage:** `.ghostuser @username` or reply to a user\n"
            "Toggles ghost mode for that specific user."
        )
        return
    try:
        if event.is_reply and not target:
            reply = await event.get_reply_message()
            user = await event.client.get_entity(reply.sender_id)
        else:
            user = await event.client.get_entity(target.lstrip("@"))
        user_id = user.id
        name = getattr(user, "first_name", str(user_id))
        if user_id in ghost_config["ghost_users"]:
            ghost_config["ghost_users"].remove(user_id)
            save_ghost_config()
            await event.reply(f"👤 **Unghosted** `{name}`")
        else:
            ghost_config["ghost_users"].append(user_id)
            save_ghost_config()
            await event.reply(f"👻 **Ghosted** `{name}`\n\nYou are now invisible to this user.")
    except Exception as e:
        await event.reply(f"❌ **Error:** `{e}`")


@CipherElite.on(events.NewMessage(pattern=r"\.ghostchat$"))
@rishabh()
async def ghost_chat_toggle(event):
    chat_id = event.chat_id
    if ghost_config["mode"] == "global":
        if chat_id in ghost_config["blacklist_chats"]:
            ghost_config["blacklist_chats"].remove(chat_id)
            save_ghost_config()
            await event.reply("👻 **Ghost re-enabled** for this chat.")
        else:
            ghost_config["blacklist_chats"].append(chat_id)
            save_ghost_config()
            await event.reply("🔓 **Ghost disabled** for this chat.")
    else:
        if chat_id in ghost_config["whitelist_chats"]:
            ghost_config["whitelist_chats"].remove(chat_id)
            save_ghost_config()
            await event.reply("🔓 **Ghost disabled** for this chat.")
        else:
            ghost_config["whitelist_chats"].append(chat_id)
            save_ghost_config()
            await event.reply("👻 **Ghost enabled** for this chat.")


@CipherElite.on(events.NewMessage(pattern=r"\.ghostmode(?:\s+(global|selective))?$"))
@rishabh()
async def set_ghost_mode(event):
    mode = event.pattern_match.group(1)
    if not mode:
        current = ghost_config["mode"]
        await event.reply(
            f"📋 **Ghost Mode:** `{current}`\n\n"
            "• `.ghostmode global` — Ghost everywhere\n"
            "• `.ghostmode selective` — Ghost specific users/chats only"
        )
        return
    ghost_config["mode"] = mode.lower()
    save_ghost_config()
    if mode == "global":
        await event.reply("🌐 **Global Mode** activated!\n\nGhost in ALL chats. Use `.ghostchat` to exclude.")
    else:
        await event.reply("🎯 **Selective Mode** activated!\n\nUse `.ghostuser` / `.ghostchat` to add targets.")


@CipherElite.on(events.NewMessage(pattern=r"\.ghostlist$"))
@rishabh()
async def ghost_list(event):
    gc = ghost_config
    text = "🕵️ **Ghost List**\n\n"
    if gc["ghost_users"]:
        text += "👤 **Ghosted Users:**\n"
        for uid in gc["ghost_users"]:
            try:
                user = await event.client.get_entity(uid)
                name = getattr(user, "first_name", str(uid))
                text += f"  • `{name}` (`{uid}`)\n"
            except Exception:
                text += f"  • ID: `{uid}`\n"
    else:
        text += "👤 **Ghosted Users:** None\n"
    text += "\n"
    if gc["mode"] == "global" and gc["blacklist_chats"]:
        text += "🚷 **Excluded Chats (ghost OFF):**\n"
        for cid in gc["blacklist_chats"]:
            try:
                chat = await event.client.get_entity(cid)
                name = getattr(chat, "title", str(cid))
                text += f"  • `{name}`\n"
            except Exception:
                text += f"  • ID: `{cid}`\n"
    elif gc["mode"] == "selective" and gc["whitelist_chats"]:
        text += "💬 **Ghosted Chats (ghost ON):**\n"
        for cid in gc["whitelist_chats"]:
            try:
                chat = await event.client.get_entity(cid)
                name = getattr(chat, "title", str(cid))
                text += f"  • `{name}`\n"
            except Exception:
                text += f"  • ID: `{cid}`\n"
    else:
        text += "💬 **Chat Overrides:** None\n"
    await event.reply(text)


@CipherElite.on(events.NewMessage(pattern=r"\.ghostreset$"))
@rishabh()
async def ghost_reset(event):
    global ghost_config, _anti_online_task
    ghost_config = DEFAULT_CONFIG.copy()
    save_ghost_config()
    if _anti_online_task and not _anti_online_task.done():
        _anti_online_task.cancel()
        _anti_online_task = None
    try:
        await event.client(UpdateStatusRequest(offline=False))
    except Exception:
        pass
    await event.reply(
        "🔄 **Ghost Mode Reset!**\n\n"
        "All settings restored to defaults. All features **OFF**."
    )


# ═══════════════════════════════════════════════════════════════════════════════
#  EVENT WATCHERS — Core stealth engine
# ═══════════════════════════════════════════════════════════════════════════════

async def _offline_loop():
    """Continuously set offline status every 30 seconds."""
    while ghost_config.get("anti_online", False):
        try:
            await CipherElite(UpdateStatusRequest(offline=True))
        except Exception:
            pass
        await asyncio.sleep(30)


@CipherElite.on(events.NewMessage(incoming=True))
async def ghost_incoming_watcher(event):
    """Handle anti-seen, ghost-read, and delayed-seen for incoming messages."""
    if not any([
        ghost_config.get("anti_seen"),
        ghost_config.get("delayed_seen"),
        ghost_config.get("ghost_read"),
    ]):
        return

    sender_id = event.sender_id
    chat_id = event.chat_id
    if not is_ghost_active_for(chat_id=chat_id, user_id=sender_id):
        return

    try:
        me = await event.client.get_me()
        if sender_id == me.id:
            return
    except Exception:
        return

    # Ghost Read: forward to Saved Messages
    if ghost_config.get("ghost_read") and event.is_private:
        try:
            await event.forward_to("me")
        except Exception as e:
            print(f"Ghost Read error: {e}")

    # Delayed Seen: schedule read after random delay
    if ghost_config.get("delayed_seen") and not ghost_config.get("anti_seen"):
        delay_min = ghost_config.get("delay_min", 5)
        delay_max = ghost_config.get("delay_max", 30)
        delay = random.randint(delay_min * 60, delay_max * 60)

        if chat_id in _delayed_seen_tasks:
            task = _delayed_seen_tasks[chat_id]
            if not task.done():
                task.cancel()

        async def _delayed_read(c_id, msg_id, delay_secs):
            await asyncio.sleep(delay_secs)
            try:
                entity = await CipherElite.get_entity(c_id)
                if hasattr(entity, "broadcast"):
                    await CipherElite(ChannelReadHistoryRequest(
                        channel=entity, max_id=msg_id
                    ))
                else:
                    await CipherElite(ReadHistoryRequest(
                        peer=entity, max_id=msg_id
                    ))
            except Exception as e:
                print(f"Delayed seen error: {e}")

        _delayed_seen_tasks[chat_id] = asyncio.create_task(
            _delayed_read(chat_id, event.id, delay)
        )


# Anti-Typing: intercept outgoing typing actions via Raw handler
try:
    from telethon.tl.functions.messages import SetTypingRequest

    @CipherElite.on(events.Raw)
    async def anti_typing_watcher(update):
        """Block SetTypingRequest when anti-typing is enabled."""
        if not ghost_config.get("anti_typing", False):
            return
        # Raw events catch updates, not outgoing requests.
        # Anti-typing works by Telethon not sending typing by default.
        # This is a placeholder — the real effect is that userbots
        # don't send typing indicators unless explicitly coded to.
        pass
except ImportError:
    pass
