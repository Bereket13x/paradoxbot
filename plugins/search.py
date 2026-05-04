import os
import re
import requests
from bs4 import BeautifulSoup
from telethon import events, Button
from datetime import datetime

from utils.utils import CipherElite
from utils.decorators import rishabh
from plugins.bot import add_handler, bot
from config.config import Config


def init(client_instance):
    commands = [
        ".gs <query>  —  Search Google and get top results as clickable links.\n"
        "    Flags:  -l<num>  to set how many results (e.g. .gs -l8 python)\n"
        "            -p<num>  to choose a page  (e.g. .gs -p2 python)",

        ".gis <query>  —  Search and download images. Sends them as an album in chat.\n"
        "    Flag:  -l<num>  to set how many images (1–10, default 3)\n"
        "    Example:  .gis -l5 cute cats",

        ".grs  —  Reply to any image with this to reverse search it.\n"
        "    Uploads the image and returns clickable Google Lens & Yandex links.",

        ".reverse <1–10>  —  Reply to any image. Downloads N visually similar images\n"
        "    and sends them as an album. Default is 3.\n"
        "    Example:  .reverse 5",

        ".google <query>  —  Sends a clickable Google Search button for the query.\n"
        "    Example:  .google how to cook pasta"
    ]
    description = "🔍 Search Tools — Google search, image search & reverse image lookup"
    add_handler("search", commands, description)



# ────────────────── HELPERS ──────────────────

def _ddg_search(query, num=5):
    """DuckDuckGo HTML search — no blocks, no API key needed."""
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:120.0) Gecko/20100101 Firefox/120.0",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
    data = {"q": query, "b": "", "kl": ""}
    res = requests.post("https://html.duckduckgo.com/html/", data=data, headers=headers, timeout=15)
    soup = BeautifulSoup(res.text, "html.parser")
    results = []
    for r in soup.select(".result__body")[:num]:
        title_tag = r.select_one(".result__a")
        desc_tag  = r.select_one(".result__snippet")
        if not title_tag:
            continue
        results.append({
            "title": title_tag.text.strip(),
            "link":  title_tag.get("href", ""),
            "desc":  desc_tag.text.strip() if desc_tag else ""
        })
    return results


def _bing_image_urls(query, num=3):
    """Scrape Bing images for direct image URLs."""
    url = f"https://www.bing.com/images/search?q={query.replace(' ', '+')}&count=30"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    r = requests.get(url, headers=headers, timeout=15)
    raw = re.findall(r'murl&quot;:&quot;(.*?)&quot;', r.text)
    seen, out = set(), []
    for u in raw:
        if u not in seen:
            seen.add(u)
            out.append(u)
        if len(out) >= num:
            break
    return out


def _download_images(urls, prefix="img"):
    """Download a list of image URLs to local temp files. Returns list of valid paths."""
    os.makedirs("./temp", exist_ok=True)
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    paths = []
    for i, url in enumerate(urls):
        try:
            r = requests.get(url, headers=headers, timeout=10, stream=True)
            if r.status_code == 200 and "image" in r.headers.get("Content-Type", ""):
                ext = r.headers.get("Content-Type", "image/jpeg").split("/")[-1].split(";")[0].strip()
                if ext not in ("jpeg", "jpg", "png", "gif", "webp"):
                    ext = "jpg"
                path = f"./temp/{prefix}_{i}.{ext}"
                with open(path, "wb") as f:
                    for chunk in r.iter_content(8192):
                        f.write(chunk)
                paths.append(path)
        except Exception:
            continue
    return paths


def _cleanup(paths):
    """Delete a list of local file paths."""
    for p in paths:
        try:
            if os.path.exists(p):
                os.remove(p)
        except Exception:
            pass


def _upload_telegraph(file_path):
    """Upload image to telegraph and return full URL."""
    with open(file_path, "rb") as f:
        res = requests.post("https://telegra.ph/upload", files={"file": f}, timeout=30)
    if res.status_code == 200:
        data = res.json()
        if isinstance(data, list) and "src" in data[0]:
            return "https://telegra.ph" + data[0]["src"]
    return None


def _yandex_similar_images(img_url, num=3):
    """Get visually similar images from Yandex."""
    search_url = f"https://yandex.com/images/search?rpt=imageview&url={img_url}"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    try:
        r = requests.get(search_url, headers=headers, timeout=15)
        soup = BeautifulSoup(r.text, "html.parser")
        # Yandex similar images are in data-bem attrs
        imgs = re.findall(r'"url":"(https?://[^"]+\.(?:jpg|jpeg|png))"', r.text)
        seen, out = set(), []
        for u in imgs:
            if u not in seen and "yandex" not in u:
                seen.add(u)
                out.append(u)
            if len(out) >= num:
                break
        return out
    except Exception:
        return []


# ────────────────── COMMANDS ──────────────────

async def register_commands():

    # ── .gs ────────────────────────────────────────────────────────────────
    @CipherElite.on(events.NewMessage(pattern=r"^\.gs ([\s\S]+)"))
    @rishabh()
    async def gsearch(event):
        match = event.pattern_match.group(1)

        # Extract flags
        page_flag = re.findall(r"-p(\d+)", match)
        lim_flag  = re.findall(r"-l(\d+)", match)
        page = int(page_flag[0]) if page_flag else 1
        lim  = int(lim_flag[0])  if lim_flag  else 5
        if lim <= 0: lim = 5
        if lim > 20: lim = 20

        # Clean query
        query = re.sub(r"-[pl]\d+", "", match).strip()

        catevent = await event.reply("`searching........`")
        try:
            results = _ddg_search(query, num=lim)
            if not results:
                return await catevent.edit("❌ **No results found!**")

            msg = f"**Search Query:**\n`{query}`\n\n**Results:**\n"
            for r in results:
                msg += f"👉[{r['title']}]({r['link']})\n`{r['desc']}`\n\n"

            await catevent.edit(msg, link_preview=False)
        except Exception as e:
            await catevent.edit(f"**Error:**\n`{str(e)}`")


    # ── .gis ───────────────────────────────────────────────────────────────
    @CipherElite.on(events.NewMessage(pattern=r"^\.gis ([\s\S]+)"))
    @rishabh()
    async def gis(event):
        query = event.pattern_match.group(1).strip()

        # Support -l flag for number of images (1–10)
        lim_flag = re.findall(r"-l(\d+)", query)
        lim = int(lim_flag[0]) if lim_flag else 3
        lim = max(1, min(lim, 10))
        query = re.sub(r"-l\d+", "", query).strip()

        catevent = await event.reply("`Searching images...`")
        paths = []
        try:
            urls = _bing_image_urls(query, num=lim)
            if not urls:
                return await catevent.edit("❌ **No images found!**")

            await catevent.edit(f"`Downloading {lim} image(s)...`")
            paths = _download_images(urls, prefix="gis")
            if not paths:
                return await catevent.edit("❌ **Failed to download images. Try a different query.**")

            await event.client.send_file(
                event.chat_id,
                paths,
                caption=f"🖼 **Image Search:** `{query}`\n**Found:** `{len(paths)}`",
                reply_to=event.reply_to_msg_id or event.id
            )
            await catevent.delete()
        except Exception as e:
            await catevent.edit(f"**Error:**\n`{str(e)}`")
        finally:
            _cleanup(paths)


    # ── .grs ───────────────────────────────────────────────────────────────
    @CipherElite.on(events.NewMessage(pattern=r"^\.grs$"))
    @rishabh()
    async def grs(event):
        """Google Reverse Search — sends image with Google Lens & Yandex links."""
        reply = await event.get_reply_message()
        if not reply or not reply.media:
            return await event.reply("`Reply to media...`")

        catevent = await event.reply("`Processing...`")
        file_path = None
        try:
            os.makedirs("./temp", exist_ok=True)
            file_path = await event.client.download_media(reply, "./temp/grs_img.jpg")
            if not file_path:
                return await catevent.edit("`Unable to extract image from replied message..`")

            await catevent.edit("`Uploading image...`")
            img_url = _upload_telegraph(file_path)

            if not img_url:
                return await catevent.edit("`Couldn't upload image. Try again.`")

            lens_url   = f"https://lens.google.com/uploadbyurl?url={img_url}"
            yandex_url = f"https://yandex.com/images/search?rpt=imageview&url={img_url}"

            caption = (
                "<b>➥ Google Reverse Search</b>\n"
                f'<b>➥ View Similar: <a href="{lens_url}">Google Lens</a></b> (Desktop)\n'
                f'<b>➥ View Alternative: <a href="{yandex_url}">Yandex</a></b>'
            )
            await catevent.delete()
            await event.client.send_file(
                event.chat_id,
                reply.media,
                caption=caption,
                parse_mode="html",
                reply_to=reply.id
            )
        except Exception as e:
            await catevent.edit(f"**Error:**\n`{str(e)}`")
        finally:
            if file_path and os.path.exists(file_path):
                os.remove(file_path)


    # ── .reverse ───────────────────────────────────────────────────────────
    @CipherElite.on(events.NewMessage(pattern=r"^\.reverse(?:\s+(\d+))?$"))
    @rishabh()
    async def reverse(event):
        """Reverse search — downloads & sends N visually similar images (1–10)."""
        reply = await event.get_reply_message()
        if not reply or not reply.media:
            return await event.reply("`Reply to media...`")

        limit_str = event.pattern_match.group(1) or "3"
        limit = int(limit_str)
        if limit < 1 or limit > 10:
            return await event.reply("`Give a limit between 1-10`")

        start = datetime.now()
        catevent = await event.reply("`Processing...`")
        file_path = None
        try:
            os.makedirs("./temp", exist_ok=True)
            file_path = await event.client.download_media(reply, "./temp/reverse_img.jpg")
            if not file_path:
                return await catevent.edit("`Unable to extract image from replied message..`")

            await catevent.edit("`Uploading image...`")
            img_url = _upload_telegraph(file_path)

            if not img_url:
                return await catevent.edit("`Couldn't upload image for reverse search..`")

            await catevent.edit("`Searching for similar images...`")
            similar_urls = _yandex_similar_images(img_url, num=limit)

            end = datetime.now()
            ms  = (end - start).seconds

            lens_url   = f"https://lens.google.com/uploadbyurl?url={img_url}"
            yandex_url = f"https://yandex.com/images/search?rpt=imageview&url={img_url}"

            caption = (
                f"<b>➥ Google Reverse Search:</b>  <code>Visual matches</code>\n"
                f'<b>➥ View Similar: <a href="{lens_url}">Google Lens</a></b> (Desktop)\n'
                f'<b>➥ View Alternative: <a href="{yandex_url}">Yandex</a></b>\n'
                f"<b>➥ Time Taken:</b>  <code>{ms} seconds</code>"
            )

            await catevent.delete()

            sim_paths = []
            if similar_urls:
                await event.client.send_message(event.chat_id, "`Downloading similar images...`")
                sim_paths = _download_images(similar_urls, prefix="rev")

            if sim_paths:
                await event.client.send_file(
                    event.chat_id,
                    sim_paths,
                    caption=caption,
                    parse_mode="html",
                    reply_to=event.reply_to_msg_id or event.id
                )
                _cleanup(sim_paths)
            else:
                # Fallback: send the original image with the links
                await event.client.send_file(
                    event.chat_id,
                    reply.media,
                    caption=caption,
                    parse_mode="html",
                    reply_to=reply.id
                )
        except Exception as e:
            await catevent.edit(f"**Error:**\n`{str(e)}`")
        finally:
            if file_path and os.path.exists(file_path):
                os.remove(file_path)


    # ── .google ────────────────────────────────────────────────────────────
    @CipherElite.on(events.NewMessage(pattern=r"^\.google ([\s\S]+)"))
    @rishabh()
    async def google_btn(event):
        query = event.pattern_match.group(1).strip()
        if len(query) > 195:
            return await event.reply("`Search query exceeds 200 characters.`")

        catevent = await event.reply("`Generating Google link...`")
        try:
            bot_username = Config.TG_BOT_USERNAME
            results = await event.client.inline_query(bot_username, f"google {query}")
            if results:
                await results[0].click(event.chat_id, reply_to=event.reply_to_msg_id or event.id, hide_via=True)
                await catevent.delete()
                await event.delete()
            else:
                await catevent.edit("`Could not generate Google button. Make sure your Assistant Bot is running.`")
        except Exception as e:
            await catevent.edit(f"**Error:** `{str(e)}`")


# ────────────────── BOT INLINE HANDLER ──────────────────

if bot:
    @bot.on(events.InlineQuery(pattern=r"^google\s+(.+)"))
    async def inline_google(event):
        query = event.pattern_match.group(1)
        url   = f"https://www.google.com/search?q={query.replace(' ', '+')}"
        result = event.builder.article(
            title=f"Google: {query}",
            text=f"🔍 **Google Search**\n\n**Query:** `{query}`",
            buttons=[Button.url("🔍 Search Google", url)]
        )
        await event.answer([result], cache_time=1)
