# =============================================================================
#  CipherElite Userbot Plugin
#
#  Plugin Name:    Channel Mirror / Auto-Forward
#  Author:         CipherElite Plugins (PARADOX)
#  Description:    Automatically forward new posts from one channel to another
#                  in real-time. Supports multiple mirror pairs. Persists
#                  across restarts via a local JSON file.
# =============================================================================

import json
import os
import re

from telethon import events, utils as telethon_utils
from telethon.tl.types import Channel, MessageService

from plugins.bot import add_handler
from utils.utils import CipherElite
from utils.decorators import rishabh

# ── Persistence ────────────────────────────────────────────────────────────────
_MIRROR_FILE = os.path.join("cipher_assets", "mirrors.json")
os.makedirs("cipher_assets", exist_ok=True)

def _load_mirrors() -> dict:
    """Load mirror pairs from disk. Returns {source_id: [dest_id, ...]}"""
    try:
        if os.path.exists(_MIRROR_FILE):
            with open(_MIRROR_FILE, "r") as f:
                raw = json.load(f)
            # JSON keys are strings — convert back to int
            return {int(k): [int(x) for x in v] for k, v in raw.items()}
    except Exception:
        pass
    return {}

def _save_mirrors():
    """Persist current MIRRORS state to disk."""
    try:
        with open(_MIRROR_FILE, "w") as f:
            json.dump({str(k): v for k, v in MIRRORS.items()}, f, indent=2)
    except Exception as e:
        print(f"⚠️ Mirror save failed: {e}")

# source_id (int) → list of dest_id (int)
MIRRORS: dict[int, list[int]] = _load_mirrors()

# Friendly labels: channel_id → "@username or title"
_LABELS: dict[int, str] = {}


# ── Plugin Registration ────────────────────────────────────────────────────────

def init(client):
    commands = [
        ".mirror <source> <dest>     — Forward all new posts from source → dest",
        ".unmirror <source> <dest>   — Stop a specific mirror",
        ".unmirror all               — Stop ALL active mirrors",
        ".mirrors                    — List all active mirror pairs",
    ]
    desc = (
        "📡 Channel Mirror — Silently forward every new post from one channel "
        "to another in real-time. Survives bot restarts."
    )
    add_handler("mirror", commands, desc)


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _resolve_channel(client, raw: str) -> tuple[int, str]:
    """
    Resolve a channel username, link, or ID to (channel_id, label).
    Raises ValueError with a human-readable message on failure.
    """
    raw = str(raw).strip().lstrip("@")
    # Handle t.me/username links
    if "t.me/" in raw:
        raw = raw.split("t.me/")[-1].split("/")[0]
        
    try:
        if raw.lstrip("-").isdigit():
            raw = int(raw)
        entity = await client.get_entity(raw)
    except Exception as e:
        raise ValueError(f"Cannot find channel `{raw}`: {e}")

    if not isinstance(entity, Channel):
        raise ValueError(f"`{raw}` is not a channel.")

    label = f"@{entity.username}" if getattr(entity, "username", None) else getattr(entity, "title", str(telethon_utils.get_peer_id(entity)))
    return telethon_utils.get_peer_id(entity), label


# ── Live Mirror Handlers ───────────────────────────────────────────────────────

class SimpleMsgCache:
    def __init__(self):
        self.d = {}
    def put(self, k, v):
        self.d[k] = v
        if len(self.d) > 2000:
            for _ in range(500):
                self.d.pop(next(iter(self.d)))
    def get(self, k):
        return self.d.get(k)

msg_cache = SimpleMsgCache()

@CipherElite.on(events.NewMessage())
async def _mirror_handler(event):
    """Forward new single posts from monitored source channels."""
    if not getattr(event, 'is_channel', False):
        return
    if isinstance(event.message, MessageService):
        return
    if getattr(event.message, 'grouped_id', None):
        return  # Albums are handled below by events.Album
    if event.message.reply_markup:
        return  # Skip promotional posts with buttons

    chat_id = event.chat_id
    if chat_id not in MIRRORS:
        return

    me = await event.client.get_me()
    fallback_uname = getattr(me, 'username', None)
    
    reply_to = getattr(event.message, 'reply_to_msg_id', None)

    for dest_id in MIRRORS[chat_id]:
        try:
            dest_ent = await event.client.get_entity(dest_id)
            dest_uname = getattr(dest_ent, 'username', None) or fallback_uname

            msg_text = event.message.message or ""
            if dest_uname and msg_text:
                msg_text = re.sub(r'@[A-Za-z0-9_]+', f'@{dest_uname}', msg_text)
                msg_text = re.sub(r'(?:https?://)?(?:www\.)?t\.me/[A-Za-z0-9_]+', f'https://t.me/{dest_uname}', msg_text)

            dest_reply_to = msg_cache.get(f"{chat_id}_{reply_to}_{dest_id}") if reply_to else None

            sent = await event.client.send_message(
                dest_id,
                msg_text,
                file=event.message.media,
                reply_to=dest_reply_to
            )
            if sent:
                msg_cache.put(f"{chat_id}_{event.message.id}_{dest_id}", sent.id)
        except Exception as e:
            print(f"⚠️ Mirror send error ({chat_id} → {dest_id}): {e}")

@CipherElite.on(events.Album())
async def _mirror_album_handler(event):
    """Forward albums (2+ photos/videos) grouped together instantly."""
    if getattr(event, 'is_channel', None) is False:
        return
        
    if any(m.reply_markup for m in event.messages):
        return  # Skip promotional albums
        
    chat_id = event.chat_id
    if chat_id not in MIRRORS:
        return

    me = await event.client.get_me()
    fallback_uname = getattr(me, 'username', None)

    # find first caption and its reply attributes
    caption_msg = next((m for m in event.messages if m.message), event.messages[0])
    msg_text = caption_msg.message or ""
    reply_to = getattr(caption_msg, 'reply_to_msg_id', None)
    
    media = [m.media for m in event.messages if m.media]

    for dest_id in MIRRORS[chat_id]:
        try:
            dest_ent = await event.client.get_entity(dest_id)
            dest_uname = getattr(dest_ent, 'username', None) or fallback_uname

            album_text = msg_text
            if dest_uname and album_text:
                album_text = re.sub(r'@[A-Za-z0-9_]+', f'@{dest_uname}', album_text)
                album_text = re.sub(r'(?:https?://)?(?:www\.)?t\.me/[A-Za-z0-9_]+', f'https://t.me/{dest_uname}', album_text)

            dest_reply_to = msg_cache.get(f"{chat_id}_{reply_to}_{dest_id}") if reply_to else None

            sent_msgs = await event.client.send_file(
                dest_id,
                file=media,
                caption=album_text,
                reply_to=dest_reply_to
            )
            if sent_msgs and isinstance(sent_msgs, list):
                # Map the primary album message ID to the destination's primary ID to sustain future replies
                msg_cache.put(f"{chat_id}_{caption_msg.id}_{dest_id}", sent_msgs[0].id)
        except Exception as e:
            print(f"⚠️ Mirror album error ({chat_id} → {dest_id}): {e}")


# ── Commands ──────────────────────────────────────────────────────────────────

@CipherElite.on(events.NewMessage(pattern=r"\.mirror(?:\s+(.+))?$"))
@rishabh()
async def mirror_cmd(event):
    """
    .mirror <source_channel> <dest_channel>
    Start forwarding all new posts from source → dest automatically.
    """
    raw = (event.pattern_match.group(1) or "").strip()
    parts = raw.split()

    if len(parts) < 2:
        return await event.reply(
            "📡 **Channel Mirror**\n\n"
            "**Usage:** `.mirror <source> <dest>`\n"
            "**Example:** `.mirror @newsource @mydestchannel`\n\n"
            "_Every new post in the source channel will be forwarded to the "
            "destination channel automatically._\n\n"
            "Use `.mirrors` to see active pairs.\n"
            "Use `.unmirror <source> <dest>` to stop."
        )

    client = event.client
    msg = await event.reply("🔍 **Resolving channels...**")

    # Resolve source
    try:
        src_id, src_label = await _resolve_channel(client, parts[0])
    except ValueError as e:
        return await msg.edit(f"❌ **Source error:** {e}\n\n_Exiting._")

    # Resolve destination
    try:
        dst_id, dst_label = await _resolve_channel(client, parts[1])
    except ValueError as e:
        return await msg.edit(f"❌ **Destination error:** {e}\n\n_Exiting._")

    if src_id == dst_id:
        return await msg.edit("❌ **Source and destination cannot be the same channel.**")

    # Register mirror
    if src_id not in MIRRORS:
        MIRRORS[src_id] = []
    if dst_id in MIRRORS[src_id]:
        return await msg.edit(
            f"⚠️ **Already mirroring:**\n"
            f"`{src_label}` → `{dst_label}`"
        )

    MIRRORS[src_id].append(dst_id)

    # Cache labels for .mirrors display
    _LABELS[src_id] = src_label
    _LABELS[dst_id] = dst_label

    _save_mirrors()

    await msg.edit(
        f"✅ **Mirror Active!**\n\n"
        f"📥 **Source:** `{src_label}`\n"
        f"📤 **Destination:** `{dst_label}`\n\n"
        f"_Every new post from {src_label} will be forwarded to "
        f"{dst_label} automatically._\n\n"
        f"Use `.unmirror {parts[0]} {parts[1]}` to stop."
    )


@CipherElite.on(events.NewMessage(pattern=r"\.unmirror(?:\s+(.+))?$"))
@rishabh()
async def unmirror_cmd(event):
    """
    .unmirror <source> <dest>   — Remove one mirror pair
    .unmirror all               — Remove ALL mirrors
    """
    raw = (event.pattern_match.group(1) or "").strip()

    if not raw:
        return await event.reply(
            "📡 **Stop Mirror**\n\n"
            "**Usage:**\n"
            "`.unmirror <source> <dest>` — stop one mirror\n"
            "`.unmirror all` — stop all mirrors"
        )

    client = event.client
    msg = await event.reply("⏳ **Processing...**")

    # Stop all
    if raw.lower() == "all":
        count = sum(len(v) for v in MIRRORS.values())
        MIRRORS.clear()
        _save_mirrors()
        return await msg.edit(
            f"🛑 **All mirrors stopped.**\n"
            f"_{count} mirror pair(s) removed._"
        )

    parts = raw.split()
    if len(parts) < 2:
        return await msg.edit(
            "❌ Please provide both source and destination.\n"
            "**Usage:** `.unmirror <source> <dest>`"
        )

    # Resolve both channels
    try:
        src_id, src_label = await _resolve_channel(client, parts[0])
    except ValueError as e:
        return await msg.edit(f"❌ **Source error:** {e}")

    try:
        dst_id, dst_label = await _resolve_channel(client, parts[1])
    except ValueError as e:
        return await msg.edit(f"❌ **Destination error:** {e}")

    if src_id not in MIRRORS or dst_id not in MIRRORS[src_id]:
        return await msg.edit(
            f"⚠️ **No active mirror found for:**\n"
            f"`{src_label}` → `{dst_label}`\n\n"
            f"Use `.mirrors` to see active pairs."
        )

    MIRRORS[src_id].remove(dst_id)
    if not MIRRORS[src_id]:
        del MIRRORS[src_id]
    _save_mirrors()

    await msg.edit(
        f"🛑 **Mirror Stopped**\n\n"
        f"📥 `{src_label}` → 📤 `{dst_label}`\n"
        f"_No longer forwarding posts._"
    )


@CipherElite.on(events.NewMessage(pattern=r"\.mirrors$"))
@rishabh()
async def mirrors_list_cmd(event):
    """List all currently active mirror pairs."""
    if not MIRRORS:
        return await event.reply(
            "📡 **No active mirrors.**\n\n"
            "Use `.mirror <source> <dest>` to create one."
        )

    client = event.client
    lines = ["📡 **Active Channel Mirrors**\n"]

    for src_id, dest_ids in MIRRORS.items():
        # Try to get a label — use cached first, fall back to ID
        src_label = _LABELS.get(src_id)
        if not src_label:
            try:
                ent = await client.get_entity(src_id)
                src_label = f"@{ent.username}" if getattr(ent, "username", None) else ent.title
                _LABELS[src_id] = src_label
            except Exception:
                src_label = f"`ID:{src_id}`"

        for dst_id in dest_ids:
            dst_label = _LABELS.get(dst_id)
            if not dst_label:
                try:
                    ent = await client.get_entity(dst_id)
                    dst_label = f"@{ent.username}" if getattr(ent, "username", None) else ent.title
                    _LABELS[dst_id] = dst_label
                except Exception:
                    dst_label = f"`ID:{dst_id}`"

            lines.append(f"  📥 `{src_label}` ➜ 📤 `{dst_label}`")

    total = sum(len(v) for v in MIRRORS.values())
    lines.append(f"\n_{total} pair(s) active_")
    lines.append("Use `.unmirror <source> <dest>` to stop one.")
    lines.append("Use `.unmirror all` to stop all.")

    await event.reply("\n".join(lines))
