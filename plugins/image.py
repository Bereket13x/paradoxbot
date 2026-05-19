# =============================================================================
#  CipherElite Userbot Plugin
#
#  Plugin Name:    image
#  Author:         CipherElite Dev (@rishabhops)
#  Repository:     https://github.com/rishabhops/CipherElite
#
#  License:        MIT
# =============================================================================
#
#  Commands:
#    .img <query>           — Search Google images, send 3 results (default)
#    .img <1-10> <query>    — Search and send N images (max 10)
#    .img <1-10>            — Reply to a message, uses its text as query
#
# =============================================================================

import os
import re
import asyncio
import requests
from telethon import events
from telethon.errors.rpcerrorlist import MediaEmptyError

from utils.utils import CipherElite
from utils.decorators import rishabh
from plugins.bot import add_handler


# ─── Plugin Registration ──────────────────────────────────────────────────────

def init(client_instance):
    commands = [
        ".img <query>  —  Search Google images, sends 3 results by default.\n"
        "    Optional: prefix with a number (1–10) to control how many.\n"
        "    Examples:\n"
        "      .img cats\n"
        "      .img 7 sunset wallpapers\n"
        "      .img 5   (reply to a message to use its text as query)",
    ]
    description = "🖼️ Image Search — Download & send images from Google/Bing"
    add_handler("image", commands, description)


# ─── Internal Helpers ─────────────────────────────────────────────────────────

def _bing_image_urls(query: str, num: int = 3) -> list[str]:
    """
    Scrape Bing Images for direct image URLs.
    Falls back gracefully — returns whatever it finds up to `num`.
    """
    url = f"https://www.bing.com/images/search?q={query.replace(' ', '+')}&count=50&first=1"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "en-US,en;q=0.9",
    }
    try:
        r = requests.get(url, headers=headers, timeout=20)
        # Bing embeds direct URLs in murl fields
        raw = re.findall(r'murl&quot;:&quot;(.*?)&quot;', r.text)
        seen, out = set(), []
        for u in raw:
            if u not in seen and u.startswith("http"):
                seen.add(u)
                out.append(u)
            if len(out) >= num:
                break
        return out
    except Exception:
        return []


def _ddg_image_urls(query: str, num: int = 3) -> list[str]:
    """
    DuckDuckGo image search fallback — extracts thumbnail/image URLs.
    """
    try:
        token_url = f"https://duckduckgo.com/?q={query.replace(' ', '+')}&iax=images&ia=images"
        headers = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:120.0) Gecko/20100101 Firefox/120.0"}
        r = requests.get(token_url, headers=headers, timeout=15)
        vqd = re.search(r'vqd=([\d-]+)', r.text)
        if not vqd:
            return []
        vqd_token = vqd.group(1)

        api_url = (
            f"https://duckduckgo.com/i.js"
            f"?l=us-en&o=json&q={query.replace(' ', '+')}"
            f"&vqd={vqd_token}&f=,,,&p=1"
        )
        r2 = requests.get(api_url, headers=headers, timeout=15)
        data = r2.json()
        results = data.get("results", [])
        return [item["image"] for item in results[:num] if "image" in item]
    except Exception:
        return []


def _download_images(urls: list[str], prefix: str = "img") -> list[str]:
    """
    Download a list of image URLs into ./temp/.
    Returns only the paths that were successfully downloaded.
    """
    os.makedirs("./temp", exist_ok=True)
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Referer": "https://www.google.com/",
    }
    paths = []
    for i, url in enumerate(urls):
        try:
            r = requests.get(url, headers=headers, timeout=12, stream=True)
            ctype = r.headers.get("Content-Type", "")
            if r.status_code == 200 and "image" in ctype:
                ext = ctype.split("/")[-1].split(";")[0].strip()
                if ext not in ("jpeg", "jpg", "png", "gif", "webp"):
                    ext = "jpg"
                path = f"./temp/{prefix}_{i}.{ext}"
                with open(path, "wb") as f:
                    for chunk in r.iter_content(8192):
                        f.write(chunk)
                # Reject tiny files (likely placeholder/error images)
                if os.path.getsize(path) > 2048:
                    paths.append(path)
                else:
                    os.remove(path)
        except Exception:
            continue
    return paths


def _cleanup(paths: list[str]):
    """Delete a list of local file paths silently."""
    for p in paths:
        try:
            if os.path.exists(p):
                os.remove(p)
        except Exception:
            pass


# ─── Command Registration ─────────────────────────────────────────────────────

async def register_commands():

    @CipherElite.on(events.NewMessage(pattern=r"^\.img(?:\s+(\d+))?(?:\s+([\s\S]+))?$"))
    @rishabh()
    async def img_search(event):
        """
        .img [1-10] [query]
        If replied to a message, its text is used as the query (if no query given).
        """
        group1 = event.pattern_match.group(1)   # optional limit
        group2 = event.pattern_match.group(2)   # optional query

        # ── Determine query ────────────────────────────────────────────────
        query = (group2 or "").strip()

        if not query and event.is_reply:
            # Use replied-message text as the search query
            replied = await event.get_reply_message()
            if replied and replied.message:
                query = replied.message.strip()

        if not query:
            return await event.reply(
                "❌ **Usage:**\n"
                "`.img <query>` — search images\n"
                "`.img 5 <query>` — search and send 5 images\n"
                "`.img 5` — reply to a message to use its text"
            )

        # ── Determine limit ────────────────────────────────────────────────
        lim = int(group1) if group1 else 3
        lim = max(1, min(lim, 10))  # clamp 1–10

        # ── Start processing ───────────────────────────────────────────────
        catevent = await event.reply(f"`🔍 Searching {lim} image(s) for:` **{query}**")
        paths = []

        try:
            # Primary source: Bing
            urls = _bing_image_urls(query, num=lim)

            # Fallback: DuckDuckGo
            if not urls:
                await catevent.edit("`⚠️ Bing unavailable, trying DuckDuckGo...`")
                urls = _ddg_image_urls(query, num=lim)

            if not urls:
                return await catevent.edit(
                    f"❌ **No images found for:** `{query}`\n"
                    "_Try a different or simpler query._"
                )

            await catevent.edit(f"`📥 Downloading {len(urls)} image(s)...`")

            # Download in a thread so we don't block the event loop
            paths = await asyncio.get_event_loop().run_in_executor(
                None, _download_images, urls, "img"
            )

            if not paths:
                return await catevent.edit(
                    "❌ **Failed to download any images.**\n"
                    "_The sources may have blocked the request. Try again or use a different query._"
                )

            # ── Send results ───────────────────────────────────────────────
            caption = (
                f"🖼 **Image Search:** `{query}`\n"
                f"📦 **Sent:** `{len(paths)}`/`{lim}` image(s)"
            )

            try:
                await event.client.send_file(
                    event.chat_id,
                    paths,
                    caption=caption,
                    reply_to=event.reply_to_msg_id or event.id,
                )
            except MediaEmptyError:
                # Some files rejected — try sending one by one
                sent = 0
                for path in paths:
                    try:
                        await event.client.send_file(
                            event.chat_id,
                            path,
                            caption=caption if sent == 0 else "",
                            reply_to=event.reply_to_msg_id or event.id,
                        )
                        sent += 1
                    except MediaEmptyError:
                        continue

                if sent == 0:
                    return await catevent.edit(
                        "❌ **All downloaded files were rejected by Telegram.**\n"
                        "_This can happen with certain image formats or corrupt files._"
                    )

            await catevent.delete()
            await event.delete()

        except Exception as e:
            await catevent.edit(f"❌ **Error:**\n`{e}`")
        finally:
            _cleanup(paths)
