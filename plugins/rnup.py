# =============================================================================
#  CipherElite Userbot Plugin
#
#  Plugin Name:    Rename & Upload (rnup)
#  Author:         CipherElite Plugins (Ported from CatUB)
#  Description:    Download, rename, and re-upload any Telegram media file
#                  with live progress updates.
# =============================================================================

import asyncio
import os
import time
from datetime import datetime
from pathlib import Path

from telethon import events

from plugins.bot import add_handler
from utils.utils import CipherElite
from utils.decorators import rishabh

# Temp download directory — uses a local ./temp folder, created if missing
TEMP_DIR = Path("./temp")
TEMP_DIR.mkdir(exist_ok=True)

# Optional thumbnail path — if you have set a custom thumb via .setthumb
THUMB_PATH = TEMP_DIR / "thumb_image.jpg"


def init(client):
    commands = [
        ".rnup <new name>",
        ".rnup -f <new name>",
    ]
    desc = "Rename a replied file and re-upload it with live progress. Use -f to force document mode."
    add_handler("rnup", commands, desc)


# ─── Progress Callback ────────────────────────────────────────────────────────

async def progress_callback(current, total, event, start_time, action, filename):
    """Edit the event message with upload/download progress."""
    now = time.time()
    elapsed = now - start_time
    if elapsed == 0:
        return
    speed = current / elapsed
    percent = (current / total) * 100 if total else 0
    eta = (total - current) / speed if speed else 0

    def human(size):
        for unit in ["B", "KB", "MB", "GB"]:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} TB"

    try:
        await event.edit(
            f"**{action}** `{filename}`\n\n"
            f"📦 `{human(current)}` / `{human(total)}`\n"
            f"⚡ Speed: `{human(speed)}/s`\n"
            f"📊 Progress: `{percent:.1f}%`\n"
            f"⏳ ETA: `{int(eta)}s`"
        )
    except Exception:
        pass  # Avoid flood waits from too-frequent edits


# ─── Command Handler ──────────────────────────────────────────────────────────

@CipherElite.on(events.NewMessage(pattern=r"\.rnup ?(-f)? ?([\s\S]+)"))
@rishabh()
async def rnup(event):
    """Rename and re-upload a replied Telegram media file."""
    if not event.reply_to_msg_id:
        return await event.edit(
            "**Usage:** Reply to any media with `.rnup <new filename>`\n"
            "**Force doc:** `.rnup -f <new filename>`"
        )

    reply = await event.get_reply_message()
    if not reply or not reply.media:
        return await event.edit("`Reply to a supported media file.`")

    flag = event.pattern_match.group(1)        # -f or None
    new_name = event.pattern_match.group(2).strip()

    if not new_name:
        return await event.edit("`Please provide a new filename.`")

    force_doc = bool(flag)
    streamable = not force_doc

    status_msg = await event.edit(
        f"`⬇️ Downloading` `{new_name}` `— please wait...`"
    )

    # ── Download ──────────────────────────────────────────────────────────────
    dl_path = TEMP_DIR / new_name
    start_dl = time.time()

    try:
        downloaded = await event.client.download_media(
            reply,
            str(dl_path),
            progress_callback=lambda d, t: asyncio.get_event_loop().create_task(
                progress_callback(d, t, status_msg, start_dl, "⬇️ Downloading", new_name)
            ),
        )
    except Exception as e:
        return await status_msg.edit(f"**Download failed:**\n`{e}`")

    dl_elapsed = round((datetime.now() - datetime.fromtimestamp(start_dl)).total_seconds(), 1)

    if not downloaded or not os.path.exists(downloaded):
        return await status_msg.edit(f"`File not found after download: {new_name}`")

    # Size guard — warn for very large files (>2 GB Telegram bot limit)
    size = os.path.getsize(downloaded)
    if size > 2_000_000_000:
        os.remove(downloaded)
        return await status_msg.edit("`File exceeds Telegram's 2 GB upload limit.`")

    # ── Thumbnail ─────────────────────────────────────────────────────────────
    thumb = None
    if THUMB_PATH.exists():
        thumb = str(THUMB_PATH)
    else:
        try:
            thumb = await reply.download_media(thumb=-1)
        except Exception:
            thumb = None

    # ── Upload ────────────────────────────────────────────────────────────────
    await status_msg.edit(f"`⬆️ Uploading` `{new_name}` `...`")
    start_ul = time.time()

    try:
        await event.client.send_file(
            event.chat_id,
            downloaded,
            force_document=force_doc,
            supports_streaming=streamable,
            allow_cache=False,
            reply_to=event.reply_to_msg_id,
            thumb=thumb,
            progress_callback=lambda d, t: asyncio.get_event_loop().create_task(
                progress_callback(d, t, status_msg, start_ul, "⬆️ Uploading", new_name)
            ),
        )
    except Exception as e:
        os.remove(downloaded)
        return await status_msg.edit(f"**Upload failed:**\n`{e}`")

    ul_elapsed = round((datetime.now() - datetime.fromtimestamp(start_ul)).total_seconds(), 1)

    # ── Cleanup ───────────────────────────────────────────────────────────────
    try:
        os.remove(downloaded)
    except Exception:
        pass

    await status_msg.edit(
        f"✅ **Done!**\n\n"
        f"📁 **File:** `{new_name}`\n"
        f"⬇️ **Downloaded in:** `{dl_elapsed}s`\n"
        f"⬆️ **Uploaded in:** `{ul_elapsed}s`\n"
        f"📄 **Mode:** `{'Document' if force_doc else 'Streamable'}`"
    )
