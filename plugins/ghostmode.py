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
from telethon.tl.functions.messages import ReadHistoryRequest, MarkDialogUnreadRequest
from telethon.tl.functions.channels import ReadHistoryRequest as ChannelReadHistoryRequest
from telethon.tl.functions.account import UpdateStatusRequest
from telethon.tl.types import InputDialogPeer

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
            # Merge properly so lists aren't replaced with wrong type
            for k, v in data.items():
                ghost_config[k] = v
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
    """Called by startup loader after client is ready."""
    global _anti_online_task

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

    # ── Resume anti-online loop if it was enabled before restart ──────────────
    if ghost_config.get("anti_online", False):
        try:
            loop = asyncio.get_event_loop()
            _anti_online_task = loop.create_task(_offline_loop())
            print("👻 Ghost Mode: Anti-Online loop started (resumed from config)")
        except Exception as e:
            print(f"Ghost Mode: Could not start anti-online loop: {e}")


# ── Helpers ────────────────────────────────────────────────────────────────────

def is_ghost_active_for(chat_id=None, user_id=None):
    """Returns True if ghost features should apply to this chat/user."""
    if ghost_config["mode"] == "global":
        # Active everywhere except blacklisted chats
        if chat_id and chat_id in ghost_config["blacklist_chats"]:
            return False
        return True
    else:
        # Selective: only for whitelisted chats/users
        if user_id and user_id in ghost_config["ghost_users"]:
            return True
        if chat_id and chat_id in ghost_config["whitelist_chats"]:
            return True
        return False


def fmt(enabled):
    return "🟢 ON" if enabled else "🔴 OFF"


# ── Dashboard ─────────────────────────────────────────────────────────────────

@CipherElite.on(events.NewMessage(pattern=r"\.ghost$"))
@rishabh()
async def ghost_dashboard(event):
    gc = ghost_config
    mode_display = "🌐 Global" if gc["mode"] == "global" else "🎯 Selective"
    text = (
        "🕵️ **𝐏𝐀𝐑𝐀𝐃𝐎𝐗 𝐆𝐇𝐎𝐒𝐓 𝐌𝐎𝐃𝐄** 🕵️\n"
        "⟡ ═══════════════════ ⟡\n\n"
        f"  🚫 **Anti-Seen:**    {fmt(gc['anti_seen'])}\n"
        f"  ⌨️ **Anti-Typing:**  {fmt(gc['anti_typing'])}\n"
        f"  👻 **Anti-Online:**  {fmt(gc['anti_online'])}\n"
        f"  📨 **Ghost Read:**   {fmt(gc['ghost_read'])}\n"
        f"  ⏱️ **Delayed Seen:** {fmt(gc['delayed_seen'])}\n\n"
        "⟡ ═══════════════════ ⟡\n\n"
        f"  📋 **Mode:** {mode_display}\n"
        f"  👤 **Ghosted Users:** `{len(gc['ghost_users'])}`\n"
        f"  💬 **Ghosted Chats:** `{len(gc['whitelist_chats'])}`\n"
        f"  🚷 **Excluded Chats:** `{len(gc['blacklist_chats'])}`\n"
    )
    if gc["delayed_seen"]:
        text += f"\n  ⏰ **Delay Range:** `{gc['delay_min']}-{gc['delay_max']}` min\n"
    text += (
        "\n⟡ ═══════════════════ ⟡\n"
        "💡 `.antiseen` `.antityping` `.antionline`\n"
        "   `.ghostread` `.delayseen` `.ghostreset`"
    )
    await event.reply(text)


# ── Toggle Commands ────────────────────────────────────────────────────────────

@CipherElite.on(events.NewMessage(pattern=r"\.antiseen(?:\s+(on|off))?$"))
@rishabh()
async def toggle_antiseen(event):
    arg = event.pattern_match.group(1)
    ghost_config["anti_seen"] = (arg.lower() == "on") if arg else not ghost_config["anti_seen"]
    # If turning on, disable delayed_seen (they conflict)
    if ghost_config["anti_seen"]:
        ghost_config["delayed_seen"] = False
    save_ghost_config()
    state = ghost_config["anti_seen"]
    msg = (
        "✅ **Active!** Senders will **never see blue ticks** from you.\n\n"
        "⚠️ This only works if you read messages through the userbot.\n"
        "If your phone/PC Telegram app is open, it will still send receipts."
        if state else
        "❌ Read receipts **enabled** again."
    )
    await event.reply(f"🚫 **Anti-Seen** {'🟢 ON' if state else '🔴 OFF'}\n\n{msg}")


@CipherElite.on(events.NewMessage(pattern=r"\.antityping(?:\s+(on|off))?$"))
@rishabh()
async def toggle_antityping(event):
    arg = event.pattern_match.group(1)
    ghost_config["anti_typing"] = (arg.lower() == "on") if arg else not ghost_config["anti_typing"]
    save_ghost_config()
    state = ghost_config["anti_typing"]
    msg = (
        '✅ **Active!** "Typing..." indicator is **suppressed**.\n\n'
        "ℹ️ Telethon userbots don't broadcast typing by default.\n"
        "This blocks any plugin that might trigger it."
        if state else
        "❌ Anti-typing **disabled**."
    )
    await event.reply(f"⌨️ **Anti-Typing** {'🟢 ON' if state else '🔴 OFF'}\n\n{msg}")


@CipherElite.on(events.NewMessage(pattern=r"\.antionline(?:\s+(on|off))?$"))
@rishabh()
async def toggle_antionline(event):
    global _anti_online_task
    arg = event.pattern_match.group(1)
    ghost_config["anti_online"] = (arg.lower() == "on") if arg else not ghost_config["anti_online"]
    save_ghost_config()
    state = ghost_config["anti_online"]

    if state:
        # Start the offline keep-alive loop
        if _anti_online_task is None or _anti_online_task.done():
            _anti_online_task = asyncio.create_task(_offline_loop())
        msg = (
            "✅ **Active!** You now appear **permanently offline**.\n\n"
            "⚠️ If your phone Telegram app is open, it may override this.\n"
            "For best results, close all other Telegram sessions."
        )
    else:
        # Stop the loop and set back to online
        if _anti_online_task and not _anti_online_task.done():
            _anti_online_task.cancel()
            _anti_online_task = None
        try:
            await event.client(UpdateStatusRequest(offline=False))
        except Exception:
            pass
        msg = "❌ Anti-Online **disabled**. Online status is visible again."

    await event.reply(f"👻 **Anti-Online** {'🟢 ON' if state else '🔴 OFF'}\n\n{msg}")


@CipherElite.on(events.NewMessage(pattern=r"\.ghostread(?:\s+(on|off))?$"))
@rishabh()
async def toggle_ghostread(event):
    arg = event.pattern_match.group(1)
    ghost_config["ghost_read"] = (arg.lower() == "on") if arg else not ghost_config["ghost_read"]
    save_ghost_config()
    state = ghost_config["ghost_read"]
    msg = (
        "✅ **Active!** Incoming PMs will be **silently forwarded** to your Saved Messages.\n"
        "Read them there — no blue ticks sent to the sender."
        if state else
        "❌ Ghost Read **disabled**."
    )
    await event.reply(f"📨 **Ghost Read** {'🟢 ON' if state else '🔴 OFF'}\n\n{msg}")


@CipherElite.on(events.NewMessage(pattern=r"\.delayseen(?:\s+(on|off))?$"))
@rishabh()
async def toggle_delayseen(event):
    arg = event.pattern_match.group(1)
    ghost_config["delayed_seen"] = (arg.lower() == "on") if arg else not ghost_config["delayed_seen"]
    # Delayed seen and anti_seen conflict — turn off anti_seen if enabling delayed
    if ghost_config["delayed_seen"]:
        ghost_config["anti_seen"] = False
    save_ghost_config()
    state = ghost_config["delayed_seen"]
    msg = (
        f"✅ **Active!** Messages marked read after `{ghost_config['delay_min']}-{ghost_config['delay_max']}` random minutes.\nLooks human — not instant!"
        if state else
        "❌ Delayed Seen **disabled**."
    )
    await event.reply(f"⏱️ **Delayed Seen** {'🟢 ON' if state else '🔴 OFF'}\n\n{msg}")


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
    mn = max(1, int(min_val))
    mx = max(mn + 1, int(max_val) if max_val else mn + 10)
    ghost_config["delay_min"] = mn
    ghost_config["delay_max"] = mx
    save_ghost_config()
    await event.reply(f"⏰ **Delay updated!**\n\nMessages marked read after `{mn}-{mx}` minutes.")


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
        uid = user.id
        name = getattr(user, "first_name", str(uid))
        if uid in ghost_config["ghost_users"]:
            ghost_config["ghost_users"].remove(uid)
            save_ghost_config()
            await event.reply(f"👤 **Unghosted** `{name}`\n\nNormal behavior restored for this user.")
        else:
            ghost_config["ghost_users"].append(uid)
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
            await event.reply("👻 **Ghost re-enabled** for this chat.\n\nStealth mode is now active here.")
        else:
            ghost_config["blacklist_chats"].append(chat_id)
            save_ghost_config()
            await event.reply("🔓 **Ghost disabled** for this chat.\n\nNormal behavior in this chat.")
    else:
        if chat_id in ghost_config["whitelist_chats"]:
            ghost_config["whitelist_chats"].remove(chat_id)
            save_ghost_config()
            await event.reply("🔓 **Ghost disabled** for this chat.")
        else:
            ghost_config["whitelist_chats"].append(chat_id)
            save_ghost_config()
            await event.reply("👻 **Ghost enabled** for this chat.\n\nStealth mode now active here.")


@CipherElite.on(events.NewMessage(pattern=r"\.ghostmode(?:\s+(global|selective))?$"))
@rishabh()
async def set_ghost_mode(event):
    mode = event.pattern_match.group(1)
    if not mode:
        current = ghost_config["mode"]
        await event.reply(
            f"📋 **Ghost Mode:** `{current}`\n\n"
            "• `.ghostmode global` — Ghost everywhere (blacklist to exclude)\n"
            "• `.ghostmode selective` — Ghost specific users/chats only"
        )
        return
    ghost_config["mode"] = mode.lower()
    save_ghost_config()
    if mode == "global":
        await event.reply("🌐 **Global Mode** activated!\n\nGhost active in ALL chats. Use `.ghostchat` to exclude specific ones.")
    else:
        await event.reply("🎯 **Selective Mode** activated!\n\nGhost OFF everywhere. Use `.ghostuser` / `.ghostchat` to enable per target.")


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
                text += f"  • `{getattr(chat, 'title', str(cid))}`\n"
            except Exception:
                text += f"  • ID: `{cid}`\n"
    elif gc["mode"] == "selective" and gc["whitelist_chats"]:
        text += "💬 **Ghosted Chats (ghost ON):**\n"
        for cid in gc["whitelist_chats"]:
            try:
                chat = await event.client.get_entity(cid)
                text += f"  • `{getattr(chat, 'title', str(cid))}`\n"
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
    await event.reply("🔄 **Ghost Mode Reset!**\n\nAll settings restored to defaults. All features **OFF**.")


# ═══════════════════════════════════════════════════════════════════════════════
#  STEALTH ENGINE — Background Workers & Event Watchers
# ═══════════════════════════════════════════════════════════════════════════════

async def _offline_loop():
    """
    Anti-Online core: sends UpdateStatus(offline=True) every 25 seconds.
    Telegram resets "last seen" to online whenever you do anything, so we
    continuously push it back to offline.
    """
    print("👻 Ghost Mode: Anti-Online loop running...")
    while True:
        if not ghost_config.get("anti_online", False):
            break
        try:
            await CipherElite(UpdateStatusRequest(offline=True))
        except Exception as e:
            print(f"Ghost Mode anti-online error: {e}")
        await asyncio.sleep(25)
    print("👻 Ghost Mode: Anti-Online loop stopped.")


@CipherElite.on(events.NewMessage(incoming=True))
async def ghost_incoming_watcher(event):
    """
    Core watcher for:
    - Anti-Seen: marks dialog as unread immediately after receiving
    - Ghost Read: forwards message to Saved Messages
    - Delayed Seen: schedules a read receipt after a random delay
    """
    gc = ghost_config

    # Quick check — bail out if nothing is active
    if not any([gc.get("anti_seen"), gc.get("delayed_seen"), gc.get("ghost_read")]):
        return

    sender_id = event.sender_id
    chat_id = event.chat_id

    # Don't process our own messages (e.g., from Saved Messages)
    try:
        me = await event.client.get_me()
        if sender_id == me.id:
            return
    except Exception:
        return

    # Check scope
    if not is_ghost_active_for(chat_id=chat_id, user_id=sender_id):
        return

    # ── Ghost Read: forward to Saved Messages silently ─────────────────────
    if gc.get("ghost_read") and event.is_private:
        try:
            await event.forward_to("me")
        except Exception as e:
            print(f"Ghost Read forward error: {e}")

    # ── Anti-Seen: mark dialog as unread right after receiving ─────────────
    if gc.get("anti_seen") and event.is_private:
        try:
            # Small delay to let Telegram process the receipt first, then unmark
            await asyncio.sleep(1)
            peer = await event.client.get_input_entity(chat_id)
            await event.client(MarkDialogUnreadRequest(
                peer=InputDialogPeer(peer=peer),
                unread=True
            ))
        except Exception as e:
            print(f"Ghost Mode anti-seen error: {e}")

    # ── Delayed Seen: schedule read receipt after random delay ─────────────
    if gc.get("delayed_seen") and not gc.get("anti_seen"):
        delay_min = gc.get("delay_min", 5)
        delay_max = gc.get("delay_max", 30)
        delay_secs = random.randint(delay_min * 60, delay_max * 60)

        # Cancel any existing pending read task for this chat
        if chat_id in _delayed_seen_tasks:
            old = _delayed_seen_tasks[chat_id]
            if not old.done():
                old.cancel()

        async def _delayed_read(c_id, msg_id, secs):
            await asyncio.sleep(secs)
            if not ghost_config.get("delayed_seen"):
                return  # was turned off while waiting
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
            _delayed_read(chat_id, event.id, delay_secs)
        )
