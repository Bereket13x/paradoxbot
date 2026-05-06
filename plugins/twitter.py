# =============================================================================
#  CipherElite Userbot Plugin
#
#  Plugin Name:    twitter
#  Author:         CipherElite Dev (@rishabhops)
#  Repository:     https://github.com/rishabhops/CipherElite
#
#  License:        MIT
#
#  DESCRIPTION:
#    Automatically monitors Twitter/X accounts and posts new tweets
#    (with full media support) to any Telegram chat.
#    Uses Nitter RSS — completely FREE, no API key required.
#
#  SETUP:
#    No setup needed! Just run:
#      .twmonitor add @username -100xxxxxxxxx
# =============================================================================

import os
import re
import json
import asyncio
import tempfile
import aiohttp
import aiofiles
from pathlib import Path
from datetime import datetime, timezone
from urllib.parse import unquote
import xml.etree.ElementTree as ET

from telethon import events
from telethon.errors import FloodWaitError

from utils.utils import CipherElite
from utils.decorators import rishabh
from plugins.bot import add_handler

# ─────────────────────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────────────────────

POLL_INTERVAL = 120  # seconds between checks per account

# Public Nitter instances — tried in order, first success wins
NITTER_INSTANCES = [
    "https://nitter.privacydev.net",
    "https://nitter.poast.org",
    "https://nitter.1d4.us",
    "https://nitter.net",
    "https://nitter.unixfox.eu",
    "https://nitter.kaitabababa.com",
]

# ─────────────────────────────────────────────────────────────────────────────
# DATABASE  (DB/twitter_monitor.json)
# ─────────────────────────────────────────────────────────────────────────────

DB_DIR = Path("DB")
DB_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DB_DIR / "twitter_monitor.json"


def _load_db() -> dict:
    if DB_PATH.exists():
        try:
            with open(DB_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"monitors": {}}


def _save_db(db: dict):
    with open(DB_PATH, "w", encoding="utf-8") as f:
        json.dump(db, f, indent=2, ensure_ascii=False)


# ─────────────────────────────────────────────────────────────────────────────
# NITTER RSS HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _extract_tweet_id(url: str) -> str | None:
    m = re.search(r"/status/(\d+)", url)
    return m.group(1) if m else None


def _nitter_pic_to_direct(url: str, instance: str) -> str:
    """Convert Nitter image proxy URL to direct pbs.twimg.com URL."""
    path = url.replace(instance, "").replace("https://nitter.net", "")
    if path.startswith("/pic/"):
        path = unquote(path[5:])  # strip /pic/ and URL-decode
        if path.startswith("orig/"):
            path = path[5:]
        return f"https://pbs.twimg.com/{path}"
    return url


def _extract_media(description_html: str, instance: str) -> list[dict]:
    """Extract photo/video URLs from a Nitter RSS item description."""
    media = []
    for url in re.findall(r'<img[^>]+src=["\']([^"\']+)["\']', description_html):
        if "/pic/" in url or "twimg.com" in url:
            media.append({"type": "photo", "url": _nitter_pic_to_direct(url, instance)})
    for url in re.findall(r'<source[^>]+src=["\']([^"\']+)["\']', description_html):
        media.append({"type": "video", "url": url})
    return media


def _parse_rss(xml_text: str, instance: str) -> tuple[list[dict], str | None]:
    """Parse Nitter RSS XML. Returns (tweets, display_name)."""
    tweets = []
    display_name = None
    try:
        root = ET.fromstring(xml_text)
        channel = root.find("channel")
        if channel is None:
            return [], None

        title = channel.findtext("title", "")
        if " / " in title:
            display_name = title.split(" / ", 1)[1]
        else:
            display_name = title

        for item in channel.findall("item"):
            title_text = item.findtext("title", "")
            link = item.findtext("link", "")
            pub_date = item.findtext("pubDate", "")
            description = item.findtext("description", "")

            # Skip retweets and replies
            if title_text.startswith("RT by ") or title_text.startswith("R to "):
                continue

            tweet_id = _extract_tweet_id(link)
            if not tweet_id:
                continue

            # Normalise link to twitter.com
            twitter_link = re.sub(r"https?://[^/]+", "https://twitter.com", link)

            try:
                dt = datetime.strptime(pub_date, "%a, %d %b %Y %H:%M:%S %Z")
                time_str = dt.replace(tzinfo=timezone.utc).strftime("%d %b %Y • %H:%M UTC")
            except Exception:
                time_str = pub_date

            tweets.append({
                "id": tweet_id,
                "text": title_text,
                "url": twitter_link,
                "time_str": time_str,
                "_media": _extract_media(description, instance),
            })
    except Exception as e:
        print(f"[twitter] RSS parse error: {e}")

    return tweets, display_name


async def _fetch_nitter_rss(username: str) -> tuple[list[dict], str | None]:
    """Fetch RSS from Nitter, trying multiple instances. Returns (tweets, display_name)."""
    username = username.lstrip("@")
    for instance in NITTER_INSTANCES:
        try:
            url = f"{instance}/{username}/rss"
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url,
                    timeout=aiohttp.ClientTimeout(total=15),
                    headers={"User-Agent": "Mozilla/5.0"},
                ) as resp:
                    if resp.status == 200:
                        text = await resp.text()
                        tweets, display_name = _parse_rss(text, instance)
                        return tweets, display_name
        except Exception as e:
            print(f"[twitter] Nitter {instance} failed: {e}")
    return [], None


async def resolve_twitter_user(username: str) -> tuple[str | None, str | None]:
    """Check a Twitter username exists via Nitter. Returns (username, display_name) or (None, None)."""
    _, display_name = await _fetch_nitter_rss(username)
    if display_name is not None:
        return username.lstrip("@"), display_name or username
    return None, None


# ─────────────────────────────────────────────────────────────────────────────
# MEDIA DOWNLOAD HELPERS
# ─────────────────────────────────────────────────────────────────────────────

async def _download_file(url: str, suffix: str) -> str | None:
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                url,
                timeout=aiohttp.ClientTimeout(total=60),
                headers={"User-Agent": "Mozilla/5.0"},
            ) as resp:
                if resp.status != 200:
                    return None
                tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
                tmp_path = tmp.name
                tmp.close()
                async with aiofiles.open(tmp_path, "wb") as f:
                    async for chunk in resp.content.iter_chunked(65536):
                        await f.write(chunk)
        return tmp_path
    except Exception:
        return None


async def _get_media_files(media_list: list[dict]) -> list[str]:
    paths = []
    for media in media_list:
        url = media.get("url", "")
        if not url:
            continue
        suffix = ".mp4" if media.get("type") == "video" else ".jpg"
        path = await _download_file(url, suffix)
        if path:
            paths.append(path)
    return paths


# ─────────────────────────────────────────────────────────────────────────────
# TELEGRAM POSTING
# ─────────────────────────────────────────────────────────────────────────────

def _format_caption(tweet: dict, username: str, display_name: str) -> str:
    caption = (
        f"🐦 <b>New Tweet from <a href=\"https://twitter.com/{username}\">"
        f"{display_name} (@{username})</a></b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"{tweet.get('text', '')}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🕐 <i>{tweet.get('time_str', '')}</i>\n"
        f"🔗 <a href=\"{tweet.get('url', '')}\">View on X/Twitter</a>\n\n"
        f"<i>Powered by PARADOX</i>"
    )
    return caption


async def _post_tweet_to_telegram(client, target_id: int, tweet: dict, username: str, display_name: str):
    caption = _format_caption(tweet, username, display_name)
    files = await _get_media_files(tweet.get("_media", []))

    try:
        if not files:
            await client.send_message(target_id, caption, parse_mode="html", link_preview=False)
        elif len(files) == 1:
            await client.send_file(target_id, files[0], caption=caption, parse_mode="html")
        else:
            await client.send_file(target_id, files, caption=[caption] + [""] * (len(files) - 1), parse_mode="html")
    finally:
        for fp in files:
            try:
                os.unlink(fp)
            except Exception:
                pass


# ─────────────────────────────────────────────────────────────────────────────
# POLLING ENGINE
# ─────────────────────────────────────────────────────────────────────────────

_poll_tasks: dict[str, asyncio.Task] = {}


async def _poll_account(client, username_lower: str):
    while True:
        try:
            db = _load_db()
            monitor = db["monitors"].get(username_lower)
            if not monitor:
                break

            username = monitor["username"]
            display_name = monitor.get("display_name", username)
            targets = monitor.get("targets", [])
            last_id = monitor.get("last_tweet_id")

            if targets:
                tweets, _ = await _fetch_nitter_rss(username)
                new_tweets = sorted(
                    [t for t in tweets if not last_id or t["id"] > last_id],
                    key=lambda t: t["id"],
                )

                if new_tweets:
                    db["monitors"][username_lower]["last_tweet_id"] = new_tweets[-1]["id"]
                    _save_db(db)

                    for tweet in new_tweets:
                        for target_str in targets:
                            try:
                                await _post_tweet_to_telegram(client, int(target_str), tweet, username, display_name)
                                await asyncio.sleep(1.5)
                            except FloodWaitError as e:
                                await asyncio.sleep(e.seconds + 5)
                            except Exception as e:
                                print(f"[twitter] post error for {username_lower}: {e}")

        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"[twitter] poll error for {username_lower}: {e}")

        await asyncio.sleep(POLL_INTERVAL)


def _start_monitor_task(client, username_lower: str):
    old = _poll_tasks.get(username_lower)
    if old and not old.done():
        old.cancel()
    _poll_tasks[username_lower] = asyncio.ensure_future(_poll_account(client, username_lower))


def _stop_monitor_task(username_lower: str):
    task = _poll_tasks.pop(username_lower, None)
    if task and not task.done():
        task.cancel()


async def _resume_all_monitors(client):
    db = _load_db()
    for username_lower in list(db["monitors"].keys()):
        _start_monitor_task(client, username_lower)


# ─────────────────────────────────────────────────────────────────────────────
# HELP MENU + STARTUP
# ─────────────────────────────────────────────────────────────────────────────

def init(client_instance):
    commands = [
        ".twmonitor add <@twitter_user> <telegram_chat>  — Start auto-posting tweets",
        ".twmonitor del <@twitter_user> [telegram_chat]  — Stop monitoring",
        ".twmonitor list                                  — Show all active monitors",
        ".twmonitor test <@twitter_user>                 — Post the latest tweet now",
        ".twdl <tweet_url>                               — Download & send tweet media",
    ]
    description = (
        "🐦 <b>Twitter Monitor</b> — Auto-post tweets to Telegram\n"
        "Supports photos, videos & text. No API key required.\n"
        "Uses public Nitter RSS — completely free."
    )
    add_handler("twitter", commands, description)
    asyncio.ensure_future(_resume_all_monitors(client_instance))


# ─────────────────────────────────────────────────────────────────────────────
# COMMAND: .twmonitor
# ─────────────────────────────────────────────────────────────────────────────

@CipherElite.on(events.NewMessage(pattern=r"^\.twmonitor(?:\s|$)(.*)"))
@rishabh()
async def twmonitor_command(event):
    await event.delete()
    args_raw = (event.pattern_match.group(1) or "").strip()
    parts = args_raw.split()

    if not parts:
        return await event.respond(_help_text(), parse_mode="html")

    subcmd = parts[0].lower()

    # ── ADD ──────────────────────────────────────────────────────────────────
    if subcmd == "add":
        if len(parts) < 3:
            return await event.respond(
                "❌ <b>Usage:</b> <code>.twmonitor add &lt;@twitter_user&gt; &lt;telegram_chat_id&gt;</code>",
                parse_mode="html",
            )
        tw_user = parts[1].lstrip("@")
        try:
            tg_id = int(parts[2])
        except ValueError:
            return await event.respond("❌ Telegram chat ID must be a number.", parse_mode="html")

        status = await event.respond(f"🔍 <b>Looking up @{tw_user} via Nitter...</b>", parse_mode="html")

        user_id, display_name = await resolve_twitter_user(tw_user)
        if not user_id:
            return await status.edit(
                f"❌ <b>Could not find Twitter user @{tw_user}.</b>\n"
                "Make sure the username is correct (Nitter may be temporarily down — try again).",
                parse_mode="html",
            )

        db = _load_db()
        key = tw_user.lower()

        if key not in db["monitors"]:
            tweets, _ = await _fetch_nitter_rss(tw_user)
            last_id = tweets[0]["id"] if tweets else None
            db["monitors"][key] = {
                "username": tw_user,
                "display_name": display_name,
                "user_id": key,
                "targets": [],
                "last_tweet_id": last_id,
            }

        target_str = str(tg_id)
        if target_str not in db["monitors"][key]["targets"]:
            db["monitors"][key]["targets"].append(target_str)

        _save_db(db)
        _start_monitor_task(event.client, key)

        await status.edit(
            f"✅ <b>Monitor Started!</b>\n\n"
            f"🐦 <b>Twitter:</b> <a href=\"https://twitter.com/{tw_user}\">@{tw_user}</a> ({display_name})\n"
            f"📩 <b>Telegram target:</b> <code>{tg_id}</code>\n"
            f"⏱ <b>Check interval:</b> every {POLL_INTERVAL}s\n\n"
            f"<i>New tweets will be posted automatically.</i>",
            parse_mode="html",
        )

    # ── DEL ──────────────────────────────────────────────────────────────────
    elif subcmd == "del":
        if len(parts) < 2:
            return await event.respond(
                "❌ <b>Usage:</b> <code>.twmonitor del &lt;@twitter_user&gt; [telegram_chat_id]</code>",
                parse_mode="html",
            )
        tw_user = parts[1].lstrip("@")
        key = tw_user.lower()
        db = _load_db()

        if key not in db["monitors"]:
            return await event.respond(f"⚠️ <b>@{tw_user}</b> is not being monitored.", parse_mode="html")

        if len(parts) >= 3:
            target_str = str(parts[2])
            if target_str in db["monitors"][key]["targets"]:
                db["monitors"][key]["targets"].remove(target_str)
                msg = f"🗑️ Removed target <code>{target_str}</code> from <b>@{tw_user}</b> monitor."
            else:
                msg = f"⚠️ Target <code>{target_str}</code> was not in the monitor list."
            if not db["monitors"][key]["targets"]:
                del db["monitors"][key]
                _stop_monitor_task(key)
                msg += "\n<i>No targets left — monitor fully stopped.</i>"
        else:
            del db["monitors"][key]
            _stop_monitor_task(key)
            msg = f"🗑️ Monitor for <b>@{tw_user}</b> fully stopped and removed."

        _save_db(db)
        await event.respond(msg, parse_mode="html")

    # ── LIST ─────────────────────────────────────────────────────────────────
    elif subcmd == "list":
        db = _load_db()
        monitors = db.get("monitors", {})
        if not monitors:
            return await event.respond("📭 <b>No active Twitter monitors.</b>", parse_mode="html")

        text = "🐦 <b>Active Twitter Monitors:</b>\n━━━━━━━━━━━━━━━━━━━━\n\n"
        for key, m in monitors.items():
            running = key in _poll_tasks and not _poll_tasks[key].done()
            text += f"{'🟢' if running else '🔴'} <b><a href=\"https://twitter.com/{m['username']}\">@{m['username']}</a></b> ({m.get('display_name', '?')})\n"
            for t in m.get("targets", []):
                text += f"   └ 📩 <code>{t}</code>\n"
            text += f"   └ 🆔 Last tweet: <code>{m.get('last_tweet_id', 'none')}</code>\n\n"
        text += "<i>Powered by PARADOX</i>"
        await event.respond(text, parse_mode="html")

    # ── TEST ─────────────────────────────────────────────────────────────────
    elif subcmd == "test":
        if len(parts) < 2:
            return await event.respond(
                "❌ <b>Usage:</b> <code>.twmonitor test &lt;@twitter_user&gt;</code>",
                parse_mode="html",
            )
        tw_user = parts[1].lstrip("@")
        key = tw_user.lower()
        db = _load_db()

        if key not in db["monitors"]:
            return await event.respond(
                f"⚠️ <b>@{tw_user}</b> is not in your monitor list.\nAdd it first with <code>.twmonitor add</code>.",
                parse_mode="html",
            )

        status = await event.respond(f"⏳ <b>Fetching latest tweet from @{tw_user}...</b>", parse_mode="html")
        m = db["monitors"][key]
        tweets, _ = await _fetch_nitter_rss(tw_user)

        if not tweets:
            return await status.edit("❌ Could not fetch any tweets. Nitter may be down — try again.", parse_mode="html")

        targets = m.get("targets", [])
        if not targets:
            return await status.edit("⚠️ No Telegram targets configured for this monitor.", parse_mode="html")

        await status.edit("📤 <b>Posting latest tweet to all targets...</b>", parse_mode="html")
        for target_str in targets:
            try:
                await _post_tweet_to_telegram(event.client, int(target_str), tweets[0], m["username"], m.get("display_name", m["username"]))
            except Exception as e:
                await event.respond(f"⚠️ Failed to post to <code>{target_str}</code>: <code>{e}</code>", parse_mode="html")

        await status.edit("✅ <b>Test post complete!</b>", parse_mode="html")

    else:
        await event.respond(_help_text(), parse_mode="html")


# ─────────────────────────────────────────────────────────────────────────────
# COMMAND: .twdl
# ─────────────────────────────────────────────────────────────────────────────

@CipherElite.on(events.NewMessage(pattern=r"^\.twdl(?:\s|$)(.*)"))
@rishabh()
async def twdl_command(event):
    await event.delete()
    url_arg = (event.pattern_match.group(1) or "").strip()
    if not url_arg:
        return await event.respond("❌ <b>Usage:</b> <code>.twdl &lt;tweet_url&gt;</code>", parse_mode="html")

    m = re.search(r"(?:twitter\.com|x\.com)/(\w+)/status/(\d+)", url_arg)
    if not m:
        return await event.respond("❌ <b>Invalid tweet URL.</b>", parse_mode="html")

    username, tweet_id = m.group(1), m.group(2)
    status = await event.respond("⬇️ <b>Fetching tweet via Nitter...</b>", parse_mode="html")

    tweets, display_name = await _fetch_nitter_rss(username)
    tweet = next((t for t in tweets if t["id"] == tweet_id), None)

    if not tweet:
        return await status.edit("❌ Could not find this tweet via Nitter. Try a different URL.", parse_mode="html")

    if not tweet["_media"]:
        await status.edit(
            f"ℹ️ <b>No media found in this tweet.</b>\n\n{tweet.get('text', '')}",
            parse_mode="html",
        )
        return

    await status.edit("📥 <b>Downloading media...</b>", parse_mode="html")
    files = await _get_media_files(tweet["_media"])

    if not files:
        return await status.edit("❌ Failed to download media from this tweet.", parse_mode="html")

    caption = _format_caption(tweet, username, display_name or username)
    try:
        await status.edit("📤 <b>Uploading to Telegram...</b>", parse_mode="html")
        if len(files) == 1:
            await event.client.send_file(event.chat_id, files[0], caption=caption, parse_mode="html")
        else:
            await event.client.send_file(event.chat_id, files, caption=[caption] + [""] * (len(files) - 1), parse_mode="html")
        await status.delete()
    except Exception as e:
        await status.edit(f"❌ <b>Upload error:</b> <code>{e}</code>", parse_mode="html")
    finally:
        for fp in files:
            try:
                os.unlink(fp)
            except Exception:
                pass


# ─────────────────────────────────────────────────────────────────────────────
# HELP TEXT
# ─────────────────────────────────────────────────────────────────────────────

def _help_text() -> str:
    return (
        "🐦 <b>Twitter Monitor — Help</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "<b>Commands:</b>\n"
        "• <code>.twmonitor add @user &lt;chat_id&gt;</code>\n"
        "  Start auto-posting from a Twitter account to a Telegram chat.\n\n"
        "• <code>.twmonitor del @user [chat_id]</code>\n"
        "  Stop monitoring. Omit chat_id to remove all targets.\n\n"
        "• <code>.twmonitor list</code>\n"
        "  Show all active monitors.\n\n"
        "• <code>.twmonitor test @user</code>\n"
        "  Instantly post the latest tweet from a monitored account.\n\n"
        "• <code>.twdl &lt;tweet_url&gt;</code>\n"
        "  Download and send tweet photos/videos to this chat.\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "✅ <b>No API key required</b> — uses public Nitter RSS feeds.\n\n"
        "<i>Powered by PARADOX</i>"
    )
