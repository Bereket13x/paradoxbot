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
import time
from datetime import datetime
from pathlib import Path

from telethon import events, functions, types
from telethon.tl.functions.messages import (
    ReadHistoryRequest,
    GetMessagesViewsRequest,
)
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

# Default settings
DEFAULT_CONFIG = {
    "anti_seen": False,
    "anti_typing": False,
    "anti_online": False,
    "ghost_read": False,
    "delayed_seen": False,
    "delay_min": 5,        # minutes min
    "delay_max": 30,       # minutes max
    "blacklist_chats": [],  # chat IDs where ghost is DISABLED (whitelist mode)
    "whitelist_chats": [],  # chat IDs where ghost is ENABLED (blacklist mode)
    "ghost_users": [],      # user IDs to ghost specifically
    "mode": "global",       # "global" = ghost everywhere, "selective" = only ghost_users/whitelist
}

ghost_config = {}
_delayed_seen_tasks = {}  # chat_id -> asyncio.Task
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
    """Check if ghost mode applies to this chat/user."""
    if ghost_config["mode"] == "global":
        # Global mode: active everywhere EXCEPT blacklisted chats
        if chat_id and chat_id in ghost_config["blacklist_chats"]:
            return False
        return True
    else:
        # Selective mode: only active for whitelisted chats / specific users
        if user_id and user_id in ghost_config["ghost_users"]:
            return True
        if chat_id and chat_id in ghost_config["whitelist_chats"]:
            return True
        return False


def format_status(enabled):
    return "🟢 ON" if enabled else "🔴 OFF"


# ── Dashboard Command ─────────────────────────────────────────────────────────

@CipherElite.on(events.NewMessage(pattern=r"\.ghost$"))
@rishabh()
async def ghost_dashboard(event):
    """Show the ghost mode control panel."""
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
        "💡 **Commands:** `.antiseen` `.antityping`\n"
        "   `.antionline` `.ghostread` `.delayseen`\n"
        "   `.ghostuser` `.ghostchat` `.ghostmode`"
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
    await event.reply(
        f"🕵️ **Anti-Seen** {emoji}\n\n"
        f"{'✅ Read receipts are now **blocked**. Senders will never see blue ticks from you.' if state else '❌ Read receipts are **enabled** again. Normal behavior restored.'}"
    )


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
    await event.reply(
        f"⌨️ **Anti-Typing** {emoji}\n\n"
        f"{'✅ \"Typing...\" indicator is now **hidden**. No one sees when you type.' if state else '❌ Typing indicator is **visible** again.'}"
    )


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

    # Start/stop the offline status loop
    if state:
        if _anti_online_task is None or _anti_online_task.done():
            _anti_online_task = asyncio.create_task(_offline_loop())
    else:
        if _anti_online_task and not _anti_online_task.done():
            _anti_online_task.cancel()
            _anti_online_task = None
        # Set back to online
        try:
            await event.client(UpdateStatusRequest(offline=False))
        except Exception:
            pass

    emoji = "🟢" if state else "🔴"
    await event.reply(
        f"👻 **Anti-Online** {emoji}\n\n"
        f"{'✅ You now appear **permanently offline** even while active.' if state else '❌ Online status is **visible** again.'}"
    )


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
    await event.reply(
        f"📨 **Ghost Read** {emoji}\n\n"
        f"{'✅ Incoming messages will be **forwarded to Saved Messages** for silent reading.' if state else '❌ Ghost read is **disabled**. Normal reading resumed.'}"
    )


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
    delay_info = f"\n⏰ Delay range: `{ghost_config['delay_min']}-{ghost_config['delay_max']}` minutes" if state else ""
    await event.reply(
        f"⏱️ **Delayed Seen** {emoji}\n\n"
        f"{'✅ Messages will be marked as read after a **random delay** (looks human).' if state else '❌ Delayed seen is **disabled**.'}"
        f"{delay_info}"
    )


@CipherElite.on(events.NewMessage(pattern=r"\.ghostdelay(?:\s+(\d+))?(?:\s+(\d+))?$"))
@rishabh()
async def set_ghost_delay(event):
    min_val = event.pattern_match.group(1)
    max_val = event.pattern_match.group(2)

    if not min_val:
        await event.reply(
            "⏰ **Ghost Delay Settings**\n\n"
            f"Current range: `{ghost_config['delay_min']}-{ghost_config['delay_max']}` min\n\n"
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
        f"Messages will be marked read after `{ghost_config['delay_min']}-{ghost_config['delay_max']}` minutes"
    )


# ── User/Chat Ghost Controls ──────────────────────────────────────────────────

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
            await event.reply(f"👤 **Unghosted** `{name}`\n\nThey can now see your read receipts and typing.")
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
        # In global mode, toggle blacklist (disable ghost for this chat)
        if chat_id in ghost_config["blacklist_chats"]:
            ghost_config["blacklist_chats"].remove(chat_id)
            save_ghost_config()
            await event.reply("👻 **Ghost re-enabled** for this chat.\n\nStealth mode is active here again.")
        else:
            ghost_config["blacklist_chats"].append(chat_id)
            save_ghost_config()
            await event.reply("🔓 **Ghost disabled** for this chat.\n\nNormal behavior in this chat.")
    else:
        # In selective mode, toggle whitelist (enable ghost for this chat)
        if chat_id in ghost_config["whitelist_chats"]:
            ghost_config["whitelist_chats"].remove(chat_id)
            save_ghost_config()
            await event.reply("🔓 **Ghost disabled** for this chat.")
        else:
            ghost_config["whitelist_chats"].append(chat_id)
            save_ghost_config()
            await event.reply("👻 **Ghost enabled** for this chat.\n\nStealth mode is now active here.")


@CipherElite.on(events.NewMessage(pattern=r"\.ghostmode(?:\s+(global|selective))?$"))
@rishabh()
async def set_ghost_mode(event):
    mode = event.pattern_match.group(1)
    if not mode:
        current = ghost_config["mode"]
        await event.reply(
            f"📋 **Ghost Mode:** `{current}`\n\n"
            "**Options:**\n"
            "• `.ghostmode global` — Ghost everywhere (use `.ghostchat` to exclude)\n"
            "• `.ghostmode selective` — Ghost only specific users/chats"
        )
        return

    ghost_config["mode"] = mode.lower()
    save_ghost_config()

    if mode == "global":
        await event.reply("🌐 **Global Mode** activated!\n\nGhost is active in ALL chats.\nUse `.ghostchat` to exclude specific ones.")
    else:
        await event.reply("🎯 **Selective Mode** activated!\n\nGhost is only active for users/chats you specify.\nUse `.ghostuser` and `.ghostchat` to add targets.")


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
        "All ghost settings have been restored to defaults.\n"
        "All features are now **OFF**."
    )


# ═══════════════════════════════════════════════════════════════════════════════
#  EVENT WATCHERS — The core stealth engine
# ═══════════════════════════════════════════════════════════════════════════════

# ── Anti-Online: Background loop to keep status offline ────────────────────────

async def _offline_loop():
    """Continuously set offline status every 30 seconds."""
    while ghost_config.get("anti_online", False):
        try:
            await CipherElite(UpdateStatusRequest(offline=True))
        except Exception:
            pass
        await asyncio.sleep(30)


# Start offline loop on boot if it was enabled
if ghost_config.get("anti_online", False):
    try:
        _anti_online_task = asyncio.get_event_loop().create_task(_offline_loop())
    except RuntimeError:
        pass  # event loop not running yet, will be started on first toggle


# ── Anti-Seen: Intercept read receipts ─────────────────────────────────────────

@CipherElite.on(events.NewMessage(incoming=True))
async def anti_seen_watcher(event):
    """
    When anti_seen is ON: don't mark incoming messages as read.
    When delayed_seen is ON: schedule a delayed mark-as-read.
    When ghost_read is ON: forward message to Saved Messages.
    """
    if not any([
        ghost_config.get("anti_seen"),
        ghost_config.get("delayed_seen"),
        ghost_config.get("ghost_read"),
    ]):
        return

    # Check if ghost applies to this chat/user
    sender_id = event.sender_id
    chat_id = event.chat_id
    if not is_ghost_active_for(chat_id=chat_id, user_id=sender_id):
        return

    me = await event.client.get_me()
    if sender_id == me.id:
        return

    # ── Ghost Read: forward to Saved Messages ──────────────────────────────
    if ghost_config.get("ghost_read") and event.is_private:
        try:
            sender = await event.get_sender()
            sender_name = getattr(sender, "first_name", "Unknown")
            # Forward the message to saved messages
            await event.forward_to("me")
        except Exception as e:
            print(f"Ghost Read error: {e}")

    # ── Delayed Seen: schedule read after random delay ─────────────────────
    if ghost_config.get("delayed_seen") and not ghost_config.get("anti_seen"):
        delay_min = ghost_config.get("delay_min", 5)
        delay_max = ghost_config.get("delay_max", 30)
        delay = random.randint(delay_min * 60, delay_max * 60)

        # Cancel previous task for this chat if exists
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


# ── Anti-Typing: Block typing action from being sent ──────────────────────────
# Note: Telethon doesn't send typing actions automatically.
# This intercepts the SetTypingRequest if any plugin or code triggers it.

_original_invoke = None

async def _patched_invoke(self, request, *args, **kwargs):
    """Intercept SetTypingRequest when anti-typing is enabled."""
    if ghost_config.get("anti_typing", False):
        # Block typing indicators
        if hasattr(request, "CONSTRUCTOR_ID"):
            # SetTypingRequest constructor ID
            req_name = type(request).__name__
            if "typing" in req_name.lower() or "SetTyping" in req_name:
                return None  # silently block
    return await _original_invoke(self, request, *args, **kwargs)


# Monkey-patch the client's __call__ to intercept typing requests
# We do this safely by checking if it hasn't been patched already
def _apply_typing_patch():
    global _original_invoke
    if _original_invoke is None:
        _original_invoke = type(CipherElite).__call__
        type(CipherElite).__call__ = _patched_invoke


try:
    _apply_typing_patch()
except Exception:
    pass  # Will work once client is ready
