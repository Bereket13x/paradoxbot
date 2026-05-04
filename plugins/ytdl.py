# =============================================================================
#  CipherElite Userbot Plugin
#
#  Plugin Name:    ytdl
#  Author:         CipherElite Dev (@rishabhops)
#  Repository:     https://github.com/rishabhops/CipherElite
#
#  License:        MIT
# =============================================================================
#
#  Commands:
#    .ytv <url> [quality]  — Download YouTube video  (default: best ≤720p)
#    .yta <url>            — Download YouTube audio as MP3
#    .yti <url>            — Show video info (title, views, duration, …)
#
#  quality options:  360 | 480 | 720 | 1080 | best
#
#  No API key required — powered by yt-dlp.
#
# =============================================================================

import os
import asyncio
import time
from datetime import timedelta
from functools import partial

import yt_dlp

from telethon import events

from utils.utils import CipherElite
from utils.decorators import rishabh
from plugins.bot import add_handler


# ─── Constants ────────────────────────────────────────────────────────────────

TEMP_DIR      = "./temp"
MAX_SIZE_MB   = 1900          # Telegram bot upload cap (< 2 GB)
MAX_SIZE_B    = MAX_SIZE_MB * 1024 * 1024
UPDATE_EVERY  = 3             # seconds between progress edits

os.makedirs(TEMP_DIR, exist_ok=True)


# ─── Plugin Registration ──────────────────────────────────────────────────────

def init(client_instance):
    commands = [
        ".ytv <url> [quality]  —  Download a YouTube video and send it.\n"
        "    quality options: 360 | 480 | 720 | 1080 | best  (default: 720)\n"
        "    Examples:\n"
        "      .ytv https://youtu.be/dQw4w9WgXcQ\n"
        "      .ytv https://youtu.be/dQw4w9WgXcQ 1080",

        ".yta <url>  —  Download a YouTube video as an MP3 audio file.\n"
        "    Example:  .yta https://youtu.be/dQw4w9WgXcQ",

        ".yti <url>  —  Show metadata for a YouTube video without downloading.\n"
        "    (Title, uploader, duration, views, likes, description snippet)\n"
        "    Example:  .yti https://youtu.be/dQw4w9WgXcQ",
    ]
    description = "🎬 YouTube Downloader — Video, audio & info. No API key needed."
    add_handler("ytdl", commands, description)


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _human_size(b: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if b < 1024:
            return f"{b:.1f} {unit}"
        b /= 1024
    return f"{b:.1f} TB"


def _human_duration(seconds: int) -> str:
    return str(timedelta(seconds=seconds))


def _bar(pct: float, width: int = 14) -> str:
    filled = int(width * pct / 100)
    return "█" * filled + "░" * (width - filled)


def _quality_format(quality: str) -> str:
    """Return a yt-dlp format string for the requested quality."""
    q = quality.strip().lower()
    if q == "best":
        return "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best"
    if q in ("360", "480", "720", "1080"):
        return (
            f"bestvideo[height<={q}][ext=mp4]+bestaudio[ext=m4a]"
            f"/best[height<={q}][ext=mp4]/best[height<={q}]"
        )
    # fallback
    return "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720][ext=mp4]/best[height<=720]"


class _ProgressTracker:
    """Shared state between the yt-dlp progress hook and the async updater."""

    def __init__(self):
        self.pct       = 0.0
        self.speed     = ""
        self.eta       = ""
        self.size      = ""
        self.status    = "starting"
        self.filename  = None

    def hook(self, d: dict):
        if d["status"] == "downloading":
            self.status   = "downloading"
            total   = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            done    = d.get("downloaded_bytes", 0)
            self.pct      = (done / total * 100) if total else 0
            self.speed    = d.get("_speed_str", "?").strip()
            self.eta      = d.get("_eta_str", "?").strip()
            self.size     = _human_size(total) if total else "?"
            self.filename = d.get("filename")
        elif d["status"] == "finished":
            self.status   = "finished"
            self.pct      = 100.0
            self.filename = d.get("filename")
        elif d["status"] == "error":
            self.status   = "error"


async def _live_progress(catevent, tracker: _ProgressTracker, label: str):
    """Periodically edit the Telegram message with download progress."""
    last_edit = 0.0
    while tracker.status == "downloading":
        now = time.time()
        if now - last_edit >= UPDATE_EVERY:
            try:
                await catevent.edit(
                    f"**{label}**\n"
                    f"`{_bar(tracker.pct)}` **{tracker.pct:.1f}%**\n"
                    f"📦 Size: `{tracker.size}`\n"
                    f"⚡ Speed: `{tracker.speed}`\n"
                    f"⏳ ETA: `{tracker.eta}`"
                )
                last_edit = now
            except Exception:
                pass
        await asyncio.sleep(1)


def _run_ytdlp(ydl_opts: dict, url: str):
    """Blocking yt-dlp call — meant to run in a thread executor."""
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
    return info


def _fetch_info(url: str) -> dict:
    """Fetch video metadata without downloading."""
    opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "noplaylist": True,
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        return ydl.extract_info(url, download=False)


def _find_downloaded_file(info: dict, outtmpl: str) -> str | None:
    """Try to locate the actual output file yt-dlp wrote."""
    # yt-dlp may merge into .mp4 even if outtmpl said .%(ext)s
    base = outtmpl.replace(".%(ext)s", "")
    for ext in ("mp4", "mkv", "webm", "mp3", "m4a", "ogg"):
        candidate = f"{base}.{ext}"
        if os.path.exists(candidate):
            return candidate
    # fallback: scan temp dir by modification time
    try:
        files = [
            os.path.join(TEMP_DIR, f)
            for f in os.listdir(TEMP_DIR)
            if not f.endswith(".part")
        ]
        if files:
            return max(files, key=os.path.getmtime)
    except Exception:
        pass
    return None


# ─── Command Registration ─────────────────────────────────────────────────────

async def register_commands():

    # ── .ytv — Video Download ─────────────────────────────────────────────────
    @CipherElite.on(events.NewMessage(pattern=r"^\.ytv\s+(https?://\S+)(?:\s+(\S+))?"))
    @rishabh()
    async def ytv(event):
        url     = event.pattern_match.group(1).strip()
        quality = event.pattern_match.group(2) or "720"

        catevent = await event.reply(f"`⏳ Fetching video info...`")
        file_path = None

        try:
            # Quick metadata check first (no download yet)
            loop = asyncio.get_event_loop()
            info = await loop.run_in_executor(None, _fetch_info, url)

            title    = info.get("title", "Unknown")
            duration = _human_duration(info.get("duration", 0))

            await catevent.edit(
                f"**🎬 {title}**\n"
                f"⏱ Duration: `{duration}`\n"
                f"📥 Starting download at `{quality}p`…"
            )

            # Set up tracker + yt-dlp options
            tracker  = _ProgressTracker()
            uid      = int(time.time())
            outtmpl  = f"{TEMP_DIR}/ytv_{uid}.%(ext)s"

            ydl_opts = {
                "format":          _quality_format(quality),
                "outtmpl":         outtmpl,
                "merge_output_format": "mp4",
                "quiet":           True,
                "no_warnings":     True,
                "noplaylist":      True,
                "progress_hooks":  [tracker.hook],
                # Handle throttled/bot-detection flows
                "http_headers": {
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/124.0.0.0 Safari/537.36"
                    )
                },
                "retries":         5,
                "fragment_retries": 5,
                "file_access_retries": 5,
                "extractor_retries": 5,
            }

            # Download + live progress concurrently
            dl_task   = loop.run_in_executor(None, partial(_run_ytdlp, ydl_opts, url))
            prog_task = asyncio.ensure_future(
                _live_progress(catevent, tracker, f"📥 Downloading: **{title}**")
            )

            await dl_task
            prog_task.cancel()

            file_path = _find_downloaded_file(info, outtmpl.replace(".%(ext)s", ""))

            if not file_path or not os.path.exists(file_path):
                return await catevent.edit("❌ Download finished but file not found.")

            size = os.path.getsize(file_path)
            if size > MAX_SIZE_B:
                return await catevent.edit(
                    f"❌ File too large for Telegram: `{_human_size(size)}`\n"
                    f"Try a lower quality (e.g. `.ytv {url} 480`)"
                )

            await catevent.edit("`📤 Uploading to Telegram…`")
            await event.client.send_file(
                event.chat_id,
                file_path,
                caption=(
                    f"🎬 **{title}**\n"
                    f"⏱ `{duration}` | 📦 `{_human_size(size)}`"
                ),
                supports_streaming=True,
                reply_to=event.reply_to_msg_id or event.id,
            )
            await catevent.delete()
            await event.delete()

        except yt_dlp.utils.DownloadError as e:
            await catevent.edit(f"**❌ Download Error:**\n`{e}`")
        except Exception as e:
            await catevent.edit(f"**❌ Error:**\n`{e}`")
        finally:
            if file_path and os.path.exists(file_path):
                os.remove(file_path)
            # Clean up leftover .part files
            for f in os.listdir(TEMP_DIR):
                if f.startswith("ytv_") and f.endswith(".part"):
                    try:
                        os.remove(os.path.join(TEMP_DIR, f))
                    except Exception:
                        pass


    # ── .yta — Audio Download ─────────────────────────────────────────────────
    @CipherElite.on(events.NewMessage(pattern=r"^\.yta\s+(https?://\S+)"))
    @rishabh()
    async def yta(event):
        url = event.pattern_match.group(1).strip()

        catevent = await event.reply("`⏳ Fetching audio info...`")
        file_path = None

        try:
            loop = asyncio.get_event_loop()
            info = await loop.run_in_executor(None, _fetch_info, url)

            title    = info.get("title", "Unknown")
            duration = _human_duration(info.get("duration", 0))
            uploader = info.get("uploader", "Unknown")

            await catevent.edit(
                f"**🎵 {title}**\n"
                f"👤 `{uploader}` | ⏱ `{duration}`\n"
                f"📥 Starting audio download…"
            )

            tracker = _ProgressTracker()
            uid     = int(time.time())
            outtmpl = f"{TEMP_DIR}/yta_{uid}.%(ext)s"

            ydl_opts = {
                "format":          "bestaudio/best",
                "outtmpl":         outtmpl,
                "quiet":           True,
                "no_warnings":     True,
                "noplaylist":      True,
                "progress_hooks":  [tracker.hook],
                "postprocessors":  [{
                    "key":            "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "192",
                }],
                "http_headers": {
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/124.0.0.0 Safari/537.36"
                    )
                },
                "retries": 5,
            }

            dl_task   = loop.run_in_executor(None, partial(_run_ytdlp, ydl_opts, url))
            prog_task = asyncio.ensure_future(
                _live_progress(catevent, tracker, f"🎵 Downloading: **{title}**")
            )

            await dl_task
            prog_task.cancel()

            # After ffmpeg conversion the ext is .mp3
            base      = outtmpl.replace(".%(ext)s", "")
            file_path = f"{base}.mp3"
            if not os.path.exists(file_path):
                file_path = _find_downloaded_file(info, base)

            if not file_path or not os.path.exists(file_path):
                return await catevent.edit("❌ Audio extraction finished but file not found.")

            size = os.path.getsize(file_path)
            if size > MAX_SIZE_B:
                return await catevent.edit(
                    f"❌ File too large for Telegram: `{_human_size(size)}`"
                )

            await catevent.edit("`📤 Uploading audio to Telegram…`")
            await event.client.send_file(
                event.chat_id,
                file_path,
                caption=(
                    f"🎵 **{title}**\n"
                    f"👤 `{uploader}` | ⏱ `{duration}` | 📦 `{_human_size(size)}`"
                ),
                attributes=[],
                reply_to=event.reply_to_msg_id or event.id,
                voice_note=False,
            )
            await catevent.delete()
            await event.delete()

        except yt_dlp.utils.DownloadError as e:
            await catevent.edit(f"**❌ Download Error:**\n`{e}`")
        except Exception as e:
            await catevent.edit(f"**❌ Error:**\n`{e}`")
        finally:
            if file_path and os.path.exists(file_path):
                os.remove(file_path)
            for f in os.listdir(TEMP_DIR):
                if f.startswith("yta_") and f.endswith((".part", ".webm", ".m4a")):
                    try:
                        os.remove(os.path.join(TEMP_DIR, f))
                    except Exception:
                        pass


    # ── .yti — Video Info ─────────────────────────────────────────────────────
    @CipherElite.on(events.NewMessage(pattern=r"^\.yti\s+(https?://\S+)"))
    @rishabh()
    async def yti(event):
        url = event.pattern_match.group(1).strip()

        catevent = await event.reply("`🔍 Fetching video info...`")

        try:
            loop = asyncio.get_event_loop()
            info = await loop.run_in_executor(None, _fetch_info, url)

            title       = info.get("title", "N/A")
            uploader    = info.get("uploader", "N/A")
            duration    = _human_duration(info.get("duration", 0))
            views       = f"{info.get('view_count', 0):,}"
            likes       = f"{info.get('like_count', 0):,}" if info.get("like_count") else "N/A"
            upload_date = info.get("upload_date", "")
            if upload_date and len(upload_date) == 8:
                upload_date = f"{upload_date[:4]}-{upload_date[4:6]}-{upload_date[6:]}"
            description = (info.get("description") or "")[:300]
            if len(info.get("description") or "") > 300:
                description += "…"
            webpage_url = info.get("webpage_url", url)

            # Available formats summary
            formats = info.get("formats", [])
            heights = sorted({
                f.get("height") for f in formats
                if f.get("height") and f.get("vcodec") != "none"
            }, reverse=True)
            quality_str = " | ".join(f"`{h}p`" for h in heights[:6]) or "N/A"

            msg = (
                f"**🎬 {title}**\n"
                f"━━━━━━━━━━━━━━━━━\n"
                f"👤 **Uploader:** `{uploader}`\n"
                f"⏱ **Duration:** `{duration}`\n"
                f"📅 **Uploaded:** `{upload_date}`\n"
                f"👁 **Views:** `{views}`\n"
                f"👍 **Likes:** `{likes}`\n"
                f"📐 **Qualities:** {quality_str}\n"
                f"━━━━━━━━━━━━━━━━━\n"
                f"📝 **Description:**\n`{description}`\n"
                f"━━━━━━━━━━━━━━━━━\n"
                f"🔗 [Watch on YouTube]({webpage_url})"
            )

            await catevent.edit(msg, link_preview=False)

        except yt_dlp.utils.DownloadError as e:
            await catevent.edit(f"**❌ Error fetching info:**\n`{e}`")
        except Exception as e:
            await catevent.edit(f"**❌ Error:**\n`{e}`")
