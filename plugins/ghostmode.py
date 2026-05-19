import asyncio
import json
import random
import os
from pathlib import Path

from telethon import events
from telethon.tl.functions.messages import ReadHistoryRequest, MarkDialogUnreadRequest
from telethon.tl.functions.channels import ReadHistoryRequest as ChannelReadHistoryRequest
from telethon.tl.functions.account import UpdateStatusRequest
from telethon.tl.types import InputDialogPeer
from telethon.utils import get_display_name, get_peer_id

from utils.utils import CipherElite
from utils.decorators import rishabh
from plugins.bot import add_handler

# ── Persistent Config ──────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).parent.parent
DB_DIR = PROJECT_ROOT / "DB"
DB_DIR.mkdir(exist_ok=True)
GHOST_CONFIG_FILE = DB_DIR / "ghost_config.json"

DEFAULT_CONFIG = {
    # Original Ghost Mode
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
    
    # Vaults
    "ghost_vault": False,
    "flash_vault": False,
    "private_ghost_vault": True,
    "vault_monitored_chats": [],
    "vault_dest": "me"
}

ghost_config = {}
_delayed_seen_tasks = {}
_anti_online_task = None

# Message Cache for Vault
MESSAGE_CACHE = {} 
MAX_CACHE_SIZE = 5000
cache_keys = []

def load_ghost_config():
    global ghost_config
    ghost_config = DEFAULT_CONFIG.copy()
    if GHOST_CONFIG_FILE.exists():
        try:
            data = json.loads(GHOST_CONFIG_FILE.read_text(encoding="utf-8"))
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

# ── Vault Cache Functions ──────────────────────────────────────────────────────
def cache_message(chat_id, msg_id, message_obj):
    global cache_keys
    key = f"{chat_id}_{msg_id}"
    if key not in MESSAGE_CACHE:
        cache_keys.append(key)
    MESSAGE_CACHE[key] = message_obj
    if len(cache_keys) > MAX_CACHE_SIZE:
        oldest_key = cache_keys.pop(0)
        MESSAGE_CACHE.pop(oldest_key, None)

def get_cached_message(chat_id, msg_id):
    if chat_id:
        return MESSAGE_CACHE.get(f"{chat_id}_{msg_id}")
    suffix = f"_{msg_id}"
    for key, msg in MESSAGE_CACHE.items():
        if key.endswith(suffix):
            true_chat_id = key.split("_")[0]
            return true_chat_id, msg
    return None, None

def fmt(enabled):
    return "🟢 ON" if enabled else "🔴 OFF"

# ── Plugin Registration ────────────────────────────────────────────────────────
def init(client):
    global _anti_online_task

    commands = [
        ".ghost - Show unified ghost & vault dashboard",
        ".antiseen on/off - Toggle anti-seen (read receipts blocked)",
        ".antityping on/off - Toggle anti-typing indicator",
        ".antionline on/off - Toggle anti-online (appear offline)",
        ".ghostread on/off - Forward msgs silently to Vault Dest",
        ".delayseen on/off - Toggle delayed-seen mode",
        ".ghostdelay <min> <max> - Set delay range in minutes",
        ".ghostuser <@user/id> - Toggle ghost mode for a specific user",
        ".ghostchat - Toggle ghost mode for current chat",
        ".ghostmode global/selective - Switch between global and selective mode",
        ".ghostlist - Show all ghosted users and chats",
        ".ghostreset - Reset all ghost & vault settings to default",
        
        ".ghostvault on/off - Toggle Global Anti-Delete/Edit",
        ".flashvault on/off - Toggle Global Anti-View-Once",
        ".vaultpm on/off - Toggle Anti-Delete for Private Chats",
        ".vaultchat on/off - Toggle monitoring for the current chat",
        ".vaultdest set/me - Set universal log destination (GhostRead & Vaults)",
        ".saveflash - Reply to media to manually save it"
    ]
    desc = "🕵️ Full Stealth & Vault suite — become invisible & track everything"
    add_handler("ghostmode", commands, desc)

    if ghost_config.get("anti_online", False):
        try:
            loop = asyncio.get_event_loop()
            _anti_online_task = loop.create_task(_offline_loop())
        except Exception as e:
            pass

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

# ── Dashboard ─────────────────────────────────────────────────────────────────
@CipherElite.on(events.NewMessage(pattern=r"\.ghost$"))
@rishabh()
async def ghost_dashboard(event):
    gc = ghost_config
    mode_display = "🌐 Global" if gc["mode"] == "global" else "🎯 Selective"
    
    vdest = gc.get("vault_dest", "me")
    vdest_name = "Saved Msgs" if str(vdest) == "me" else f"Group ({vdest})"

    text = (
        "🕵️ **𝐏𝐀𝐑𝐀𝐃𝐎𝐗 𝐆𝐇𝐎𝐒𝐓 & 𝐕𝐀𝐔𝐋𝐓𝐒** 🕵️\n"
        "⟡ ═══════════════════ ⟡\n\n"
        f"  🚫 **Anti-Seen:**    {fmt(gc['anti_seen'])}\n"
        f"  ⌨️ **Anti-Typing:**  {fmt(gc['anti_typing'])}\n"
        f"  👻 **Anti-Online:**  {fmt(gc['anti_online'])}\n"
        f"  📨 **Ghost Read:**   {fmt(gc['ghost_read'])}\n"
        f"  ⏱️ **Delayed Seen:** {fmt(gc['delayed_seen'])}\n\n"
        "⟡ ═══════════════════ ⟡\n\n"
        f"  🗑 **Ghost Vault:**  {fmt(gc['ghost_vault'])}\n"
        f"  📸 **Flash Vault:**  {fmt(gc['flash_vault'])}\n"
        f"  👤 **PM Vault Auto:** {fmt(gc.get('private_ghost_vault', True))}\n"
        f"  📥 **Universal Log:** {vdest_name}\n\n"
        "⟡ ═══════════════════ ⟡\n\n"
        f"  📋 **Mode:** {mode_display}\n"
        f"  👤 **Ghost Users:**  `{len(gc['ghost_users'])}`\n"
        f"  💬 **Ghost Chats:**  `{len(gc['whitelist_chats'])}` (W) / `{len(gc['blacklist_chats'])}` (B)\n"
        f"  🛡 **Vault Chats:**  `{len(gc.get('vault_monitored_chats', []))}`\n"
    )
    if gc["delayed_seen"]:
        text += f"\n  ⏰ **Delay Range:** `{gc['delay_min']}-{gc['delay_max']}` min\n"
        
    await event.reply(text)

# ── Ghost Mode Commands ────────────────────────────────────────────────────────
@CipherElite.on(events.NewMessage(pattern=r"\.antiseen(?:\s+(on|off))?$"))
@rishabh()
async def toggle_antiseen(event):
    arg = event.pattern_match.group(1)
    ghost_config["anti_seen"] = (arg.lower() == "on") if arg else not ghost_config["anti_seen"]
    if ghost_config["anti_seen"]: ghost_config["delayed_seen"] = False
    save_ghost_config()
    await event.reply(f"🚫 **Anti-Seen** {fmt(ghost_config['anti_seen'])}")

@CipherElite.on(events.NewMessage(pattern=r"\.antityping(?:\s+(on|off))?$"))
@rishabh()
async def toggle_antityping(event):
    arg = event.pattern_match.group(1)
    ghost_config["anti_typing"] = (arg.lower() == "on") if arg else not ghost_config["anti_typing"]
    save_ghost_config()
    await event.reply(f"⌨️ **Anti-Typing** {fmt(ghost_config['anti_typing'])}")

@CipherElite.on(events.NewMessage(pattern=r"\.antionline(?:\s+(on|off))?$"))
@rishabh()
async def toggle_antionline(event):
    global _anti_online_task
    arg = event.pattern_match.group(1)
    ghost_config["anti_online"] = (arg.lower() == "on") if arg else not ghost_config["anti_online"]
    save_ghost_config()
    
    if ghost_config["anti_online"]:
        if _anti_online_task is None or _anti_online_task.done():
            _anti_online_task = asyncio.create_task(_offline_loop())
    else:
        if _anti_online_task and not _anti_online_task.done():
            _anti_online_task.cancel()
            _anti_online_task = None
        try: await event.client(UpdateStatusRequest(offline=False))
        except: pass
    await event.reply(f"👻 **Anti-Online** {fmt(ghost_config['anti_online'])}")

@CipherElite.on(events.NewMessage(pattern=r"\.ghostread(?:\s+(on|off))?$"))
@rishabh()
async def toggle_ghostread(event):
    arg = (event.pattern_match.group(1) or "").strip().lower()
    ghost_config["ghost_read"] = (arg == "on") if arg in ["on", "off"] else not ghost_config["ghost_read"]
    save_ghost_config()
    await event.reply(f"📨 **Ghost Read** {fmt(ghost_config['ghost_read'])}")

@CipherElite.on(events.NewMessage(pattern=r"\.delayseen(?:\s+(on|off))?$"))
@rishabh()
async def toggle_delayseen(event):
    arg = event.pattern_match.group(1)
    ghost_config["delayed_seen"] = (arg.lower() == "on") if arg else not ghost_config["delayed_seen"]
    if ghost_config["delayed_seen"]: ghost_config["anti_seen"] = False
    save_ghost_config()
    await event.reply(f"⏱️ **Delayed Seen** {fmt(ghost_config['delayed_seen'])}")

@CipherElite.on(events.NewMessage(pattern=r"\.ghostdelay(?:\s+(\d+))?(?:\s+(\d+))?$"))
@rishabh()
async def set_ghost_delay(event):
    mn = event.pattern_match.group(1)
    mx = event.pattern_match.group(2)
    if not mn: return await event.reply(f"⏰ **Ghost Delay:** `{ghost_config['delay_min']}-{ghost_config['delay_max']}` min\nUse: `.ghostdelay 5 30`")
    ghost_config["delay_min"] = max(1, int(mn))
    ghost_config["delay_max"] = max(ghost_config["delay_min"] + 1, int(mx) if mx else ghost_config["delay_min"] + 10)
    save_ghost_config()
    await event.reply(f"⏰ **Delay updated!** `{ghost_config['delay_min']}-{ghost_config['delay_max']}` min")

@CipherElite.on(events.NewMessage(pattern=r"\.ghostuser(?:\s+(.+))?$"))
@rishabh()
async def ghost_user_toggle(event):
    target = (event.pattern_match.group(1) or "").strip()
    if not target and not event.is_reply: return await event.reply("Use: `.ghostuser @user` or reply.")
    try:
        user = await event.client.get_entity(target.lstrip("@")) if not event.is_reply else await event.client.get_entity((await event.get_reply_message()).sender_id)
        if user.id in ghost_config["ghost_users"]:
            ghost_config["ghost_users"].remove(user.id)
            save_ghost_config()
            await event.reply(f"👤 **Unghosted User!**")
        else:
            ghost_config["ghost_users"].append(user.id)
            save_ghost_config()
            await event.reply(f"👻 **Ghosted User!**")
    except Exception as e: await event.reply(f"❌ Error: {e}")

@CipherElite.on(events.NewMessage(pattern=r"\.ghostchat$"))
@rishabh()
async def ghost_chat_toggle(event):
    cid = event.chat_id
    if ghost_config["mode"] == "global":
        if cid in ghost_config["blacklist_chats"]:
            ghost_config["blacklist_chats"].remove(cid)
            msg = "👻 **Ghost re-enabled for this chat.**"
        else:
            ghost_config["blacklist_chats"].append(cid)
            msg = "🔓 **Ghost disabled for this chat.**"
    else:
        if cid in ghost_config["whitelist_chats"]:
            ghost_config["whitelist_chats"].remove(cid)
            msg = "🔓 **Ghost disabled for this chat.**"
        else:
            ghost_config["whitelist_chats"].append(cid)
            msg = "👻 **Ghost enabled for this chat.**"
    save_ghost_config()
    await event.reply(msg)

@CipherElite.on(events.NewMessage(pattern=r"\.ghostmode(?:\s+(global|selective))?$"))
@rishabh()
async def set_ghost_mode(event):
    mode = event.pattern_match.group(1)
    if not mode: return await event.reply(f"📋 **Ghost Mode:** `{ghost_config['mode']}`\nUse: `.ghostmode global/selective`")
    ghost_config["mode"] = mode.lower()
    save_ghost_config()
    await event.reply(f"🌐 **Mode activated:** `{mode.upper()}`")

@CipherElite.on(events.NewMessage(pattern=r"\.ghostlist$"))
@rishabh()
async def ghost_list(event):
    gc = ghost_config
    text = f"🕵️ **Ghost List**\n\n👤 Ghosted Users: `{len(gc['ghost_users'])}`\n💬 Ghosted Chats (Whitelist): `{len(gc['whitelist_chats'])}`\n🚷 Excluded Chats (Blacklist): `{len(gc['blacklist_chats'])}`\n🛡 Vault Chats: `{len(gc.get('vault_monitored_chats', []))}`"
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
    try: await event.client(UpdateStatusRequest(offline=False))
    except: pass
    await event.reply("🔄 **Ghost & Vaults Reset!** All defaults restored.")

# ── Vault Toggle Commands ──────────────────────────────────────────────────────
@CipherElite.on(events.NewMessage(pattern=r"^\.ghostvault(?:\s+(on|off))?$"))
@rishabh()
async def toggle_ghostvault(event):
    arg = event.pattern_match.group(1)
    if not arg: return await event.reply("❌ **Use:** `.ghostvault on/off`")
    ghost_config["ghost_vault"] = (arg.lower() == "on")
    save_ghost_config()
    await event.reply(f"👻 **Global Ghost Vault:** {fmt(ghost_config['ghost_vault'])}")

@CipherElite.on(events.NewMessage(pattern=r"^\.flashvault(?:\s+(on|off))?$"))
@rishabh()
async def toggle_flashvault(event):
    arg = event.pattern_match.group(1)
    if not arg: return await event.reply("❌ **Use:** `.flashvault on/off`")
    ghost_config["flash_vault"] = (arg.lower() == "on")
    save_ghost_config()
    await event.reply(f"📸 **Global Flash Vault:** {fmt(ghost_config['flash_vault'])}")

@CipherElite.on(events.NewMessage(pattern=r"^\.vaultpm(?:\s+(on|off))?$"))
@rishabh()
async def toggle_vaultpm(event):
    arg = event.pattern_match.group(1)
    if not arg: return await event.reply("❌ **Use:** `.vaultpm on/off`")
    ghost_config["private_ghost_vault"] = (arg.lower() == "on")
    save_ghost_config()
    await event.reply(f"👤 **Private Chat Vault:** {fmt(ghost_config['private_ghost_vault'])}")

@CipherElite.on(events.NewMessage(pattern=r"^\.vaultchat(?:\s+(on|off))?$"))
@rishabh()
async def toggle_vaultchat(event):
    arg = event.pattern_match.group(1)
    if not arg: return await event.reply("❌ **Use:** `.vaultchat on/off`")
    chat_id = str(get_peer_id(event.chat_id))
    if arg.lower() == "on":
        if chat_id not in ghost_config.setdefault("vault_monitored_chats", []):
            ghost_config["vault_monitored_chats"].append(chat_id)
            save_ghost_config()
        await event.reply("🔐 **Vault is now monitoring THIS chat!**")
    else:
        if chat_id in ghost_config.get("vault_monitored_chats", []):
            ghost_config["vault_monitored_chats"].remove(chat_id)
            save_ghost_config()
        await event.reply("💤 **Vault stopped monitoring this chat.**")

@CipherElite.on(events.NewMessage(pattern=r"^\.vaultdest(?:\s+(.+))?$"))
@rishabh()
async def toggle_vaultdest(event):
    arg = (event.pattern_match.group(1) or "").strip().lower()
    if arg == "set":
        ghost_config["vault_dest"] = event.chat_id
        save_ghost_config()
        await event.reply("✅ **Universal Destination Set!**\nGhost Read & Vault logs will now be sent HERE.")
    elif arg in ["me", "saved"]:
        ghost_config["vault_dest"] = "me"
        save_ghost_config()
        await event.reply("✅ **Universal Destination Reset!**\nGhost Read & Vault logs will go to Saved Msgs.")
    else:
        await event.reply("❌ **Use:** `.vaultdest set` or `.vaultdest me`")

@CipherElite.on(events.NewMessage(pattern=r"^\.saveflash$"))
@rishabh()
async def manual_flash_download(event):
    reply = await event.get_reply_message()
    if not reply or not reply.media: return await event.reply("❌ **Reply to a media message to save it!**")
    status = await event.reply("📥 **Downloading...**")
    try:
        dl = await reply.download_media()
        if dl:
            dest = ghost_config.get("vault_dest", "me")
            await event.client.send_file(dest, dl, caption="📸 **Manually Saved Flash Media**")
            os.remove(dl)
            await status.edit("✅ **Saved successfully!**")
    except Exception as e:
        await status.edit(f"❌ Error: {e}")

# ── STEALTH ENGINE (Workers & Listeners) ───────────────────────────────────────

async def _offline_loop():
    while True:
        if not ghost_config.get("anti_online", False): break
        try: await CipherElite(UpdateStatusRequest(offline=True))
        except: pass
        await asyncio.sleep(25)

async def get_vault_log_peer(client):
    dest = ghost_config.get("vault_dest", "me")
    try:
        if dest != "me": return await client.get_entity(dest)
    except: pass
    return "me"

@CipherElite.on(events.NewMessage(incoming=True))
async def combined_incoming_watcher(event):
    gc = ghost_config
    sender_id = event.sender_id
    num_chat_id = event.chat_id
    str_chat_id = str(get_peer_id(num_chat_id)) if num_chat_id else None

    try:
        me = await event.client.get_me()
        if sender_id == me.id: return
    except: pass

    # 1. FLASH VAULT
    if event.media:
        is_view_once = getattr(event.media, 'ttl_seconds', None) is not None
        if is_view_once:
            if gc.get("flash_vault") or (str_chat_id and str_chat_id in gc.get("vault_monitored_chats", [])):
                try:
                    dl = await event.download_media()
                    if dl:
                        sender = await event.get_sender()
                        sender_name = get_display_name(sender) if sender else "Unknown"
                        caption = f"📸 **INTERCEPTED VIEW-ONCE MEDIA**\n\n👤 **From:** {sender_name}\n💬 **Chat:** `{str_chat_id}`"
                        log_peer = await get_vault_log_peer(event.client)
                        await event.client.send_file(log_peer, dl, caption=caption)
                        os.remove(dl)
                except Exception as e: print(f"FlashVault Error: {e}")

    # 2. GHOST VAULT CACHER
    if gc.get("ghost_vault") or (gc.get("private_ghost_vault", True) and event.is_private) or (str_chat_id and str_chat_id in gc.get("vault_monitored_chats", [])):
        cache_message(str_chat_id, event.id, event.message)

    # 3. GHOST MODE (Read/Seen)
    if not any([gc.get("anti_seen"), gc.get("delayed_seen"), gc.get("ghost_read")]): return
    if not is_ghost_active_for(chat_id=num_chat_id, user_id=sender_id): return

    # Ghost Read
    if gc.get("ghost_read") and event.is_private:
        sender = await event.get_sender()
        if getattr(sender, "bot", False) is False:
            try:
                dest = gc.get("vault_dest", "me")
                await event.client.forward_messages(dest, event.message)
            except: pass

    # Anti-Seen
    if gc.get("anti_seen") and event.is_private:
        try:
            await asyncio.sleep(1)
            peer = await event.client.get_input_entity(num_chat_id)
            await event.client(MarkDialogUnreadRequest(peer=InputDialogPeer(peer=peer), unread=True))
        except: pass

    # Delayed Seen
    if gc.get("delayed_seen") and not gc.get("anti_seen"):
        delay_secs = random.randint(gc.get("delay_min", 5) * 60, gc.get("delay_max", 30) * 60)
        if num_chat_id in _delayed_seen_tasks:
            old = _delayed_seen_tasks[num_chat_id]
            if not old.done(): old.cancel()

        async def _delayed_read(c_id, msg_id, secs):
            await asyncio.sleep(secs)
            if not ghost_config.get("delayed_seen"): return
            try:
                entity = await CipherElite.get_entity(c_id)
                if hasattr(entity, "broadcast"): await CipherElite(ChannelReadHistoryRequest(channel=entity, max_id=msg_id))
                else: await CipherElite(ReadHistoryRequest(peer=entity, max_id=msg_id))
            except: pass

        _delayed_seen_tasks[num_chat_id] = asyncio.create_task(_delayed_read(num_chat_id, event.id, delay_secs))


@CipherElite.on(events.MessageDeleted())
async def catch_deletions(event):
    gc = ghost_config
    chat_id = str(get_peer_id(event.chat_id)) if event.chat_id else None
    
    for msg_id in event.deleted_ids:
        true_chat_id = chat_id
        cached_msg = None
        if chat_id: cached_msg = get_cached_message(chat_id, msg_id)
        else: true_chat_id, cached_msg = get_cached_message(None, msg_id)
            
        if not cached_msg: continue
            
        should_log = False
        if gc.get("ghost_vault") or (true_chat_id and true_chat_id in gc.get("vault_monitored_chats", [])):
            should_log = True
        elif gc.get("private_ghost_vault", True) and getattr(cached_msg, 'is_private', False):
            should_log = True
            try:
                chat_entity = await event.client.get_entity(int(true_chat_id))
                if getattr(chat_entity, 'bot', False): should_log = False
            except: pass

        if not should_log: continue
            
        try:
            chat_title = "Private Chat"
            try: chat_title = get_display_name(await event.client.get_entity(int(true_chat_id)))
            except: pass
            
            sender_entity = await cached_msg.get_sender()
            sender_name = get_display_name(sender_entity) if sender_entity else "Unknown User"
            
            log_text = f"🗑 **DELETED MESSAGE EXPOSED**\n\n👤 **User:** {sender_name}\n💬 **Chat:** {chat_title}\n━━━━━━━━━━━━━━━━━━━━\n{cached_msg.text or '[Media/No Text]'}"
            log_peer = await get_vault_log_peer(event.client)
            await event.client.send_message(log_peer, message=log_text, file=cached_msg.media)
        except Exception as e: print(f"Vault Deletion Error: {e}")

@CipherElite.on(events.MessageEdited())
async def catch_edits(event):
    gc = ghost_config
    chat_id = str(get_peer_id(event.chat_id)) if event.chat_id else None
    
    should_log = False
    if gc.get("ghost_vault") or (chat_id and chat_id in gc.get("vault_monitored_chats", [])):
        should_log = True
    elif gc.get("private_ghost_vault", True) and event.is_private:
        should_log = True
        try:
            if getattr(await event.client.get_entity(event.chat_id), 'bot', False): should_log = False
        except: pass

    if not should_log: return
        
    cached_msg = get_cached_message(chat_id, event.id)
    if isinstance(cached_msg, tuple): cached_msg = cached_msg[1]
        
    if cached_msg and cached_msg.text != event.text:
        try:
            chat_title = get_display_name(await event.client.get_entity(int(chat_id)))
            sender_entity = await event.get_sender()
            sender_name = get_display_name(sender_entity) if sender_entity else "Unknown User"
            
            log_text = f"✏️ **EDITED MESSAGE EXPOSED**\n\n👤 **User:** {sender_name}\n💬 **Chat:** {chat_title}\n━━━━━━━━━━━━━━━━━━━━\n🛑 **ORIGINAL:**\n{cached_msg.text or '[Media]'}\n\n✅ **NEW:**\n{event.text}"
            log_peer = await get_vault_log_peer(event.client)
            await event.client.send_message(log_peer, log_text)
            
            cache_message(chat_id, event.id, event.message)
        except Exception as e: print(f"Vault Edit Error: {e}")

# ── GhostRead Reply Interceptor ────────────────────────────────────────────────
@CipherElite.on(events.NewMessage())
async def vaultdest_reply_relay(event):
    if not event.is_reply:
        return
        
    gc = ghost_config
    if not gc.get("ghost_read"):
        return
        
    dest = gc.get("vault_dest", "me")
    
    # Check if this message is in the vault destination
    try:
        if dest == "me":
            # If "me", the chat_id should be the userbot's own ID
            me = await event.client.get_me()
            if event.chat_id != me.id:
                return
        else:
            if event.chat_id != int(dest):
                return
    except Exception:
        return

    # Ignore commands
    if event.text and event.text.startswith("."):
        return

    # Get the replied-to message
    reply_msg = await event.get_reply_message()
    if not reply_msg or not reply_msg.forward:
        return
        
    # Get the original sender from the forward
    original_sender_id = None
    if reply_msg.forward.sender_id:
        original_sender_id = reply_msg.forward.sender_id
    else:
        # Sometimes Telethon sets from_id instead of sender_id
        try:
            original_sender_id = reply_msg.forward.from_id.user_id
        except Exception:
            pass
            
    if not original_sender_id:
        return
        
    try:
        await event.client.send_message(
            entity=original_sender_id,
            message=event.text,
            file=event.media,
            link_preview=False
        )
        await event.reply("✅ _Message cleanly relayed._")
    except Exception as e:
        await event.reply(f"❌ _Failed to relay:_ `{e}`")
