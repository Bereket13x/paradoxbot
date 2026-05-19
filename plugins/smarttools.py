# =============================================================================
#  PARADOX Userbot Plugin
#
#  Plugin Name:    Smart Tools
#  Description:    WebShot, Wikipedia, Movie Info, Shazam — all powered
#                  directly by free APIs. ZERO API keys needed.
#  License:        MIT
# =============================================================================

import os
import tempfile
import urllib.parse

import requests
from telethon import events

from utils.utils import CipherElite
from utils.decorators import rishabh
from plugins.bot import add_handler

TEMP_DIR = tempfile.gettempdir()


def init(client_instance):
    commands = [
        ".ss <url> - Screenshot any website instantly",
        ".wiki <query> - Wikipedia lookup with image",
        ".movie <title> - Movie/Series info with poster",
        ".shazam - Recognize a song (reply to audio/voice)",
    ]
    desc = "🧠 **PARADOX Smart Tools** — WebShot, Wiki, Movies, Shazam"
    add_handler("smarttools", commands, desc)


# ═══════════════════════════════════════════════════════════════════════════════
#  📸 WEBSHOT — Screenshot any website
# ═══════════════════════════════════════════════════════════════════════════════

@CipherElite.on(events.NewMessage(pattern=r"^\.ss(?:\s+(.+))?$", outgoing=True))
@rishabh()
async def webshot(event):
    url = (event.pattern_match.group(1) or "").strip()
    if not url:
        return await event.edit("❌ **Usage:** `.ss example.com`")

    if not url.startswith("http"):
        url = "https://" + url

    await event.edit("📸 **Capturing screenshot...**")

    try:
        encoded = urllib.parse.quote(url, safe=":/")
        shot_url = f"https://image.thum.io/get/width/1280/crop/720/noanimate/{encoded}"

        r = requests.get(shot_url, timeout=45, headers={"User-Agent": "Mozilla/5.0"})
        if r.status_code == 200 and len(r.content) > 1000:
            path = os.path.join(TEMP_DIR, "paradox_ss.png")
            with open(path, "wb") as f:
                f.write(r.content)

            await event.client.send_file(
                event.chat_id,
                path,
                caption=(
                    f"📸 **Website Screenshot**\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n"
                    f"🔗 `{url}`\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n"
                    f"⟨ PARADOX ⟩"
                ),
                reply_to=event.reply_to_msg_id,
            )
            await event.delete()
            os.remove(path)
        else:
            await event.edit("❌ **Failed to capture screenshot.**")
    except Exception as e:
        await event.edit(f"❌ **Error:** `{e}`")


# ═══════════════════════════════════════════════════════════════════════════════
#  📖 WIKIPEDIA — Instant knowledge lookup
# ═══════════════════════════════════════════════════════════════════════════════

@CipherElite.on(events.NewMessage(pattern=r"^\.wiki(?:\s+(.+))?$", outgoing=True))
@rishabh()
async def wiki_lookup(event):
    query = (event.pattern_match.group(1) or "").strip()
    if not query:
        return await event.edit("❌ **Usage:** `.wiki Albert Einstein`")

    await event.edit("📖 **Searching...**")

    try:
        encoded = urllib.parse.quote(query)
        api_url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{encoded}"
        r = requests.get(api_url, timeout=15, headers={"User-Agent": "PARADOX/2.0"})

        if r.status_code != 200:
            # Fallback: search API
            search_url = (
                f"https://en.wikipedia.org/w/api.php?"
                f"action=opensearch&search={encoded}&limit=1&format=json"
            )
            sr = requests.get(search_url, timeout=10, headers={"User-Agent": "PARADOX/2.0"})
            if sr.status_code == 200:
                sdata = sr.json()
                if sdata[1]:
                    suggested = urllib.parse.quote(sdata[1][0])
                    r = requests.get(
                        f"https://en.wikipedia.org/api/rest_v1/page/summary/{suggested}",
                        timeout=15,
                        headers={"User-Agent": "PARADOX/2.0"},
                    )
            if r.status_code != 200:
                return await event.edit("❌ **No results found.**")

        data = r.json()
        title = data.get("title", query)
        extract = data.get("extract", "No summary available.")
        desc = data.get("description", "")
        thumb = data.get("thumbnail", {}).get("source", "")

        if len(extract) > 900:
            extract = extract[:900] + "..."

        text = f"📖 **{title}**\n"
        if desc:
            text += f"_{desc}_\n"
        text += (
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"{extract}\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"⟨ PARADOX ⟩"
        )

        if thumb:
            path = os.path.join(TEMP_DIR, "paradox_wiki.jpg")
            tr = requests.get(thumb, timeout=10)
            with open(path, "wb") as f:
                f.write(tr.content)
            await event.client.send_file(
                event.chat_id, path, caption=text, reply_to=event.reply_to_msg_id
            )
            await event.delete()
            os.remove(path)
        else:
            await event.edit(text)
    except Exception as e:
        await event.edit(f"❌ **Error:** `{e}`")


# ═══════════════════════════════════════════════════════════════════════════════
#  🎬 MOVIE INFO — Film & series database (FREE — no API key)
# ═══════════════════════════════════════════════════════════════════════════════

@CipherElite.on(events.NewMessage(pattern=r"^\.movie(?:\s+(.+))?$", outgoing=True))
@rishabh()
async def movie_info(event):
    title = (event.pattern_match.group(1) or "").strip()
    if not title:
        return await event.edit("❌ **Usage:** `.movie Inception`")

    await event.edit("🎬 **Searching database...**")

    try:
        # Use iTunes Search API — 100% free, no key needed
        encoded = urllib.parse.quote(title)
        url = f"https://itunes.apple.com/search?term={encoded}&entity=movie&limit=1"
        r = requests.get(url, timeout=15)
        data = r.json()

        results = data.get("results", [])
        if not results:
            # Fallback: try TV shows
            url2 = f"https://itunes.apple.com/search?term={encoded}&entity=tvSeason&limit=1"
            r2 = requests.get(url2, timeout=15)
            data2 = r2.json()
            results = data2.get("results", [])

        if not results:
            return await event.edit(f"❌ **Not found:** `{title}`")

        m = results[0]
        name = m.get("trackName") or m.get("collectionName", "N/A")
        artist = m.get("artistName", "N/A")
        genre = m.get("primaryGenreName", "N/A")
        release = m.get("releaseDate", "")[:10]  # YYYY-MM-DD
        description = m.get("longDescription") or m.get("shortDescription", "No description.")
        price = m.get("trackPrice") or m.get("collectionPrice", "N/A")
        currency = m.get("currency", "USD")
        rating = m.get("contentAdvisoryRating", "N/A")
        runtime_ms = m.get("trackTimeMillis", 0)
        runtime_min = f"{runtime_ms // 60000}m" if runtime_ms else "N/A"
        kind = m.get("kind", "movie").replace("-", " ").title()

        # Truncate description
        if len(description) > 600:
            description = description[:600] + "..."

        # Get high-res artwork
        artwork = m.get("artworkUrl100", "")
        if artwork:
            artwork = artwork.replace("100x100bb", "600x600bb")

        text = (
            f"🎬 **{name}**\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"🎭 **Genre:** `{genre}`\n"
            f"📅 **Released:** `{release}`\n"
            f"⏱ **Runtime:** `{runtime_min}`\n"
            f"🔞 **Rating:** `{rating}`\n"
            f"🎬 **Director:** `{artist}`\n"
            f"📦 **Type:** `{kind}`\n"
            f"💰 **Price:** `{price} {currency}`\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📝 {description}\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"⟨ PARADOX ⟩"
        )

        if artwork:
            path = os.path.join(TEMP_DIR, "paradox_movie.jpg")
            ar = requests.get(artwork, timeout=10)
            with open(path, "wb") as f:
                f.write(ar.content)
            await event.client.send_file(
                event.chat_id, path, caption=text, reply_to=event.reply_to_msg_id
            )
            await event.delete()
            os.remove(path)
        else:
            await event.edit(text)
    except Exception as e:
        await event.edit(f"❌ **Error:** `{e}`")


# ═══════════════════════════════════════════════════════════════════════════════
#  🎵 SHAZAM — Recognize any song from audio
# ═══════════════════════════════════════════════════════════════════════════════

@CipherElite.on(events.NewMessage(pattern=r"^\.shazam$", outgoing=True))
@rishabh()
async def shazam_recognize(event):
    if not event.is_reply:
        return await event.edit("❌ **Reply to an audio or voice message!**")

    reply = await event.get_reply_message()
    if not reply.media:
        return await event.edit("❌ **Reply to an audio or voice message!**")

    await event.edit("🎵 **Analyzing audio...**")

    audio_path = None
    try:
        from shazamio import Shazam

        audio_path = await reply.download_media(TEMP_DIR)
        if not audio_path:
            return await event.edit("❌ **Failed to download audio.**")

        shazam = Shazam()
        result = await shazam.recognize(audio_path)

        track = result.get("track")
        if not track:
            return await event.edit("❌ **Could not recognize the song.** Try a clearer clip.")

        song_title = track.get("title", "Unknown")
        artist = track.get("subtitle", "Unknown Artist")
        genre = track.get("genres", {}).get("primary", "Unknown")

        # Extract album & year from metadata sections
        album = ""
        year = ""
        for section in track.get("sections", []):
            for meta in section.get("metadata", []):
                if meta.get("title") == "Album":
                    album = meta.get("text", "")
                if meta.get("title") == "Released":
                    year = meta.get("text", "")

        cover_url = None
        images = track.get("images", {})
        if images:
            cover_url = images.get("coverarthq") or images.get("coverart")

        text = (
            f"🎵 **Song Recognized!**\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"🎶 **Title:** `{song_title}`\n"
            f"🎤 **Artist:** `{artist}`\n"
            f"🎸 **Genre:** `{genre}`\n"
        )
        if album:
            text += f"💿 **Album:** `{album}`\n"
        if year:
            text += f"📅 **Released:** `{year}`\n"
        text += (
            f"\n━━━━━━━━━━━━━━━━━━━━\n"
            f"⟨ PARADOX ⟩"
        )

        if cover_url:
            path = os.path.join(TEMP_DIR, "paradox_shazam.jpg")
            cr = requests.get(cover_url, timeout=10)
            with open(path, "wb") as f:
                f.write(cr.content)
            await event.client.send_file(
                event.chat_id, path, caption=text, reply_to=event.reply_to_msg_id
            )
            await event.delete()
            os.remove(path)
        else:
            await event.edit(text)

    except ImportError:
        await event.edit(
            "❌ **shazamio not installed!**\n"
            "Add `shazamio` to your `requirements.txt` and redeploy."
        )
    except Exception as e:
        await event.edit(f"❌ **Error:** `{e}`")
    finally:
        if audio_path and os.path.exists(audio_path):
            try:
                os.remove(audio_path)
            except Exception:
                pass
