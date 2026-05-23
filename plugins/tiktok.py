# =============================================================================
#  PARADOX Userbot Plugin
#
#  Plugin Name:    tiktok
#  Description:    Fetch TikTok videos by username and index using yt-dlp
#  Commands:
#    .tiktok <username> [index] [-link] → Fetch a specific video (default: 1st/latest)
#    .tiktokfirst <username> [-link]    → Fetch the very first (oldest) video posted
#    .tiktokoldest <username> [-link]   → Alias for .tiktokfirst
#    .tiktokdl <url>                    → Download any TikTok video by direct link
#    .tiktokpin <username>              → Download pinned video(s) from profile
#
#  Examples:
#    .tiktok charlidamelio       → fetches the latest video
#    .tiktok charlidamelio 5     → fetches the 5th latest video
#    .tiktok charlidamelio 5 -link → only fetches the link/info
#    .tiktok charlidamelio oldest→ fetches the oldest video
#    .tiktokfirst charlidamelio  → fetches the oldest video
#    .tiktokdl https://tiktok.com/...  → downloads by link
#    .tiktokpin charlidamelio    → fetches pinned video(s)
# =============================================================================

import os
import asyncio
import tempfile
from datetime import datetime

import yt_dlp
from telethon import events

from utils.utils import CipherElite
from utils.decorators import rishabh
from plugins.bot import add_handler


# ── Plugin registration ────────────────────────────────────────────────────── #

def init(client_instance):
    commands = [
        ".tiktok <username> [index] [-link] - Fetch a TikTok video by position (default: 1st/latest)",
        ".tiktok <username> oldest - Fetch the oldest accessible video",
        ".tiktokfirst <username> - Alias for oldest",
        ".tiktokdl <url> - Download any TikTok video by direct link",
        ".tiktokpin <username> - Download pinned video(s) from a profile",
    ]
    description = "🎵 TikTok Fetcher — Download TikTok videos by username, index, link, or pinned"
    add_handler("tiktok", commands, description)


# ── yt-dlp helper (runs in a thread so it won't block the event loop) ────── #

def _base_opts(out_path: str) -> dict:
    """Shared yt-dlp options."""
    return {
        "quiet": True,
        "no_warnings": True,
        "outtmpl": out_path,
        "format": "mp4/bestvideo+bestaudio/best",
        "merge_output_format": "mp4",
        "http_headers": {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Referer": "https://www.tiktok.com/",
        },
    }


def _parse_entry(entry, fallback_user: str = "unknown") -> dict:
    """Extract metadata from a yt-dlp info entry."""
    title      = entry.get("title", "No title")
    like_count = entry.get("like_count") or 0
    view_count = entry.get("view_count") or 0
    uploader   = entry.get("uploader") or entry.get("creator") or fallback_user
    webpage_url = entry.get("webpage_url") or f"https://www.tiktok.com/@{fallback_user}"
    playlist_index = entry.get("playlist_index")

    # Extract date
    date_str = "Unknown Date"
    timestamp = entry.get("timestamp")
    upload_date = entry.get("upload_date")
    if timestamp:
        date_str = datetime.fromtimestamp(timestamp).strftime("%b %d, %Y")
    elif upload_date:
        try:
            date_str = datetime.strptime(upload_date, "%Y%m%d").strftime("%b %d, %Y")
        except Exception:
            pass

    return {
        "title": title,
        "like_count": like_count,
        "view_count": view_count,
        "uploader": uploader,
        "webpage_url": webpage_url,
        "playlist_index": playlist_index,
        "date_str": date_str,
    }


def _extract_and_download(username: str, index: int, out_path: str, download_video: bool = True) -> dict:
    """
    Runs yt-dlp synchronously (must be called via asyncio.to_thread).
    Single-pass: extracts metadata AND downloads in one go.
    """
    url = f"https://www.tiktok.com/@{username}"
    opts = _base_opts(out_path)
    opts["playlist_items"] = str(index)

    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=download_video)

    if "entries" in info:
        entries = list(info["entries"])
        if not entries:
            raise ValueError(f"No video found at index {index} for @{username}.")
        entry = entries[0]
    else:
        entry = info

    if not entry:
        raise ValueError(f"No video found at index {index} for @{username}.")

    return _parse_entry(entry, username)


def _download_by_url(video_url: str, out_path: str, download_video: bool = True) -> dict:
    """
    Download a single TikTok video by its direct URL.
    """
    opts = _base_opts(out_path)

    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(video_url, download=download_video)

    if "entries" in info:
        entries = list(info["entries"])
        if not entries:
            raise ValueError("Could not extract video from that URL.")
        entry = entries[0]
    else:
        entry = info

    if not entry:
        raise ValueError("Could not extract video from that URL.")

    return _parse_entry(entry)


def _extract_pinned(username: str, out_path: str, max_pinned: int = 3) -> list:
    """
    Fetch the first few videos from a profile (pinned videos appear first).
    Returns a list of metadata dicts.
    """
    url = f"https://www.tiktok.com/@{username}"
    opts = _base_opts(out_path)
    opts["playlist_items"] = f"1-{max_pinned}"

    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=True)

    results = []
    if "entries" in info:
        for entry in info["entries"]:
            if entry:
                results.append(_parse_entry(entry, username))
    elif info:
        results.append(_parse_entry(info, username))

    return results


def _fmt_count(n: int) -> str:
    """Format large numbers as e.g. 1.2M, 345K."""
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)


# ── Command handlers ───────────────────────────────────────────────────────── #

async def register_commands():

    @CipherElite.on(events.NewMessage(outgoing=True, pattern=r"\.tiktok(first|oldest)?(?:\s+(.+))?$"))
    @rishabh()
    async def tiktok_fetch(event):
        """Fetch a TikTok video by username and optional index."""

        # ── Parse arguments ────────────────────────────────────────────── #
        cmd_type = event.pattern_match.group(1) # 'first', 'oldest', or None
        raw = (event.pattern_match.group(2) or "").strip()

        only_link = False
        if "-link" in raw.lower():
            only_link = True
            # Case insensitive replace
            import re
            raw = re.sub(r'(?i)-link', '', raw).strip()

        if not raw:
            return await event.reply(
                "❌ **Usage:**\n"
                "• `.tiktok <username> [index] [-link]` (e.g. `.tiktok charlidamelio 5 -link`)\n"
                "• `.tiktok <username> oldest`\n"
                "• `.tiktokfirst <username>` / `.tiktokoldest <username>`"
            )

        parts = raw.split()
        username = parts[0].lstrip("@")

        index = 1
        if cmd_type in ["first", "oldest"]:
            index = -1
        elif len(parts) > 1:
            val = parts[1].lower()
            if val in ["oldest", "first", "-1"]:
                index = -1
            else:
                try:
                    index = int(parts[1])
                    if index < 1:
                        raise ValueError
                except ValueError:
                    return await event.reply("❌ **Index must be a positive integer (e.g. 1, 2, 3…) or 'oldest'**")

        # ── Status message ─────────────────────────────────────────────── #
        idx_text = "oldest accessible" if index == -1 else f"#{index}"
        slow_warn = "\n⚠️ _Oldest mode scans the entire profile — may be slow for big accounts!_" if index == -1 else ""
        action_text = "Fetching link for" if only_link else "Fetching"
        
        status = await event.reply(
            f"🎵 **{action_text} the {idx_text} TikTok video from @{username}…**\n"
            f"⏳ _This may take a moment, hang tight!_{slow_warn}"
        )

        # ── Temp file setup ────────────────────────────────────────────── #
        tmp_dir  = tempfile.mkdtemp()
        out_path = os.path.join(tmp_dir, "tiktok_%(id)s.%(ext)s")

        try:
            # ── Run yt-dlp in a thread (non-blocking) ─────────────────── #
            meta = await asyncio.to_thread(
                _extract_and_download, username, index, out_path, not only_link
            )

            # ── Build caption ──────────────────────────────────────────── #
            title      = meta["title"][:200] if meta["title"] else "—"
            likes      = _fmt_count(meta["like_count"])
            views      = _fmt_count(meta["view_count"])
            uploader   = meta["uploader"]
            page_url   = meta["webpage_url"]
            actual_idx = meta.get("playlist_index")
            date_str   = meta.get("date_str")

            if index == -1:
                index_label = f"#{actual_idx} (Oldest Accessible)" if actual_idx else "Oldest Accessible"
                caption = (
                    f"🎵 **TikTok** — @{uploader}\n"
                    f"📅 **Date:** {date_str}\n\n"
                    f"📝 {title}\n\n"
                    f"♥ **{likes}** likes  •  👁 **{views}** views\n"
                    f"🔗 [Open on TikTok]({page_url})\n\n"
                    f"📌 **Video {index_label}**\n"
                    f"ℹ️ _Note: TikTok limits how far back we can fetch (usually ~2.5k videos)._"
                )
            else:
                index_label = f"#{index}"
                caption = (
                    f"🎵 **TikTok** — @{uploader}\n"
                    f"📅 **Date:** {date_str}\n\n"
                    f"📝 {title}\n\n"
                    f"♥ **{likes}** likes  •  👁 **{views}** views\n"
                    f"🔗 [Open on TikTok]({page_url})\n\n"
                    f"📌 **Video {index_label}**"
                )

            if only_link:
                return await status.edit(f"✅ **TikTok Video Link Fetched!**\n\n{caption}")

            # Find the downloaded file (yt-dlp fills in %(id)s / %(ext)s)
            files = [
                os.path.join(tmp_dir, f)
                for f in os.listdir(tmp_dir)
                if os.path.isfile(os.path.join(tmp_dir, f))
            ]
            if not files:
                return await status.edit(
                    f"❌ **Download completed but no file was found.**\n"
                    f"The video may be private or geo-restricted."
                )

            video_file = files[0]
            file_size  = os.path.getsize(video_file)

            # Telegram limit: 2 GB
            if file_size > 2 * 1024 ** 3:
                os.remove(video_file)
                return await status.edit(
                    f"❌ **Video is too large for Telegram (>{file_size // 1024 ** 2} MB).**\n"
                    f"🔗 [Watch on TikTok]({meta['webpage_url']})"
                )

            await status.edit(f"📤 **Uploading video {index_label} from @{username}…**")

            # ── Send video ─────────────────────────────────────────────── #
            await event.client.send_file(
                event.chat_id,
                video_file,
                caption=caption,
                supports_streaming=True,
            )

            await status.edit(f"✅ **TikTok video {index_label} from @{username} delivered!** 🎵")

        except yt_dlp.utils.DownloadError as e:
            err = str(e)
            if "Private" in err or "private" in err:
                msg = "❌ **This TikTok account is private.**"
            elif "does not exist" in err or "Could not find" in err:
                msg = f"❌ **User @{username} not found on TikTok.**"
            elif "No video" in err or "unavailable" in err.lower():
                msg = f"❌ **No video found for @{username} at index: {idx_text}.**"
            else:
                msg = f"❌ **yt-dlp error:** `{err[:300]}`"
            await status.edit(msg)

        except ValueError as e:
            await status.edit(f"❌ {e}")

        except Exception as e:
            await status.edit(f"❌ **Unexpected error:** `{str(e)[:300]}`")

        finally:
            # ── Cleanup temp files ─────────────────────────────────────── #
            try:
                for f in os.listdir(tmp_dir):
                    fp = os.path.join(tmp_dir, f)
                    if os.path.isfile(fp):
                        os.remove(fp)
                os.rmdir(tmp_dir)
            except Exception:
                pass

    # ================================================================== #
    # .tiktokdl <url>  — Download any TikTok video by direct link
    # ================================================================== #

    @CipherElite.on(events.NewMessage(outgoing=True, pattern=r"\.tiktokdl(?:\s+(.+))?$"))
    @rishabh()
    async def tiktok_dl(event):
        """Download a TikTok video by its direct URL."""
        import re as _re

        raw = (event.pattern_match.group(1) or "").strip()
        if not raw or not _re.match(r"https?://", raw):
            return await event.reply(
                "❌ **Usage:** `.tiktokdl <tiktok url>`\n\n"
                "**Example:**\n"
                "• `.tiktokdl https://www.tiktok.com/@user/video/123456`\n"
                "• `.tiktokdl https://vm.tiktok.com/XXXXX`"
            )

        video_url = raw.split()[0]

        status = await event.reply(
            f"🎵 **Downloading TikTok video from link…**\n"
            "⏳ _Hang tight!_"
        )

        tmp_dir  = tempfile.mkdtemp()
        out_path = os.path.join(tmp_dir, "tiktok_%(id)s.%(ext)s")

        try:
            meta = await asyncio.to_thread(
                _download_by_url, video_url, out_path, True
            )

            files = [
                os.path.join(tmp_dir, f)
                for f in os.listdir(tmp_dir)
                if os.path.isfile(os.path.join(tmp_dir, f))
            ]
            if not files:
                return await status.edit("❌ **Download completed but no file was found.**")

            video_file = files[0]
            file_size  = os.path.getsize(video_file)

            if file_size > 2 * 1024 ** 3:
                os.remove(video_file)
                return await status.edit(
                    f"❌ **Video too large for Telegram (>{file_size // 1024 ** 2} MB).**\n"
                    f"🔗 [Watch on TikTok]({meta['webpage_url']})"
                )

            title    = meta["title"][:200] if meta["title"] else "—"
            likes    = _fmt_count(meta["like_count"])
            views    = _fmt_count(meta["view_count"])
            uploader = meta["uploader"]
            page_url = meta["webpage_url"]
            date_str = meta.get("date_str")

            caption = (
                f"🎵 **TikTok** — @{uploader}\n"
                f"📅 **Date:** {date_str}\n\n"
                f"📝 {title}\n\n"
                f"♥ **{likes}** likes  •  👁 **{views}** views\n"
                f"🔗 [Open on TikTok]({page_url})"
            )

            await status.edit(f"📤 **Uploading…**")

            await event.client.send_file(
                event.chat_id,
                video_file,
                caption=caption,
                supports_streaming=True,
            )

            await status.edit("✅ **TikTok video downloaded!** 🎵")

        except Exception as e:
            await status.edit(f"❌ **Error:** `{str(e)[:300]}`")

        finally:
            try:
                for f in os.listdir(tmp_dir):
                    fp = os.path.join(tmp_dir, f)
                    if os.path.isfile(fp):
                        os.remove(fp)
                os.rmdir(tmp_dir)
            except Exception:
                pass

    # ================================================================== #
    # .tiktokpin <username>  — Download pinned video(s) from profile
    # ================================================================== #

    @CipherElite.on(events.NewMessage(outgoing=True, pattern=r"\.tiktokpin(?:\s+(.+))?$"))
    @rishabh()
    async def tiktok_pinned(event):
        """Fetch pinned (top) video(s) from a TikTok profile."""

        raw = (event.pattern_match.group(1) or "").strip()
        if not raw:
            return await event.reply("❌ **Usage:** `.tiktokpin <username>`")

        username = raw.split()[0].lstrip("@")

        status = await event.reply(
            f"📌 **Fetching pinned video(s) from @{username}…**\n"
            "⏳ _Pinned videos are always at the top of the profile._"
        )

        tmp_dir  = tempfile.mkdtemp()
        out_path = os.path.join(tmp_dir, "tiktok_%(id)s.%(ext)s")

        try:
            results = await asyncio.to_thread(
                _extract_pinned, username, out_path, 3
            )

            if not results:
                return await status.edit(f"❌ **No videos found for @{username}.**")

            # Collect all downloaded files
            files = sorted([
                os.path.join(tmp_dir, f)
                for f in os.listdir(tmp_dir)
                if os.path.isfile(os.path.join(tmp_dir, f))
            ])

            if not files:
                return await status.edit("❌ **Download completed but no files found.**")

            total = min(len(files), len(results))
            await status.edit(f"📤 **Uploading {total} pinned video(s) from @{username}…**")

            for i in range(total):
                meta     = results[i]
                title    = meta["title"][:200] if meta["title"] else "—"
                likes    = _fmt_count(meta["like_count"])
                views    = _fmt_count(meta["view_count"])
                uploader = meta["uploader"]
                page_url = meta["webpage_url"]
                date_str = meta.get("date_str")

                caption = (
                    f"📌 **Pinned Video ({i+1}/{total})** — @{uploader}\n"
                    f"📅 **Date:** {date_str}\n\n"
                    f"📝 {title}\n\n"
                    f"♥ **{likes}** likes  •  👁 **{views}** views\n"
                    f"🔗 [Open on TikTok]({page_url})"
                )

                await event.client.send_file(
                    event.chat_id,
                    files[i],
                    caption=caption,
                    supports_streaming=True,
                )
                await asyncio.sleep(0.5)  # Avoid flood

            await status.edit(f"✅ **{total} pinned video(s) from @{username} delivered!** 📌")

        except yt_dlp.utils.DownloadError as e:
            err = str(e)
            if "Private" in err or "private" in err:
                msg = "❌ **This TikTok account is private.**"
            elif "does not exist" in err or "Could not find" in err:
                msg = f"❌ **User @{username} not found on TikTok.**"
            else:
                msg = f"❌ **yt-dlp error:** `{err[:300]}`"
            await status.edit(msg)

        except Exception as e:
            await status.edit(f"❌ **Error:** `{str(e)[:300]}`")

        finally:
            try:
                for f in os.listdir(tmp_dir):
                    fp = os.path.join(tmp_dir, f)
                    if os.path.isfile(fp):
                        os.remove(fp)
                os.rmdir(tmp_dir)
            except Exception:
                pass
