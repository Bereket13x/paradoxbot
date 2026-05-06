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
#    (with full media support: photos, videos, multi-media albums) to
#    any Telegram chat.
#
#  SETUP:
#    Use the in-bot command once:
#      .twsetup <your_bearer_token>
#
#    Token is saved to DB/ and persists across bot updates.
#    Get a free Bearer Token at: https://developer.twitter.com/
# =============================================================================

import os
import json
import asyncio
import tempfile
import aiohttp
import aiofiles
from pathlib import Path
from datetime import datetime, timezone

from telethon import events
from telethon.errors import FloodWaitError

from utils.utils import CipherElite
from utils.decorators import rishabh
from plugins.bot import add_handler

# ─────────────────────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────────────────────

POLL_INTERVAL = 120  # seconds between checks per account

# Token is loaded dynamically from DB (set via .twsetup) or env var fallback.
# Always call _get_token() instead of using a global directly.
def _get_token() -> str:
    db = _load_db()
    return db.get("bearer_token") or os.getenv("TWITTER_BEARER_TOKEN", "")

# ─────────────────────────────────────────────────────────────────────────────
# DATABASE  (DB/twitter_monitor.json)
# Stores bearer token + all monitor configs in one persistent file.
# This file lives in DB/ which is NOT overwritten on bot updates.
# ─────────────────────────────────────────────────────────────────────────────

DB_DIR = Path("DB")
DB_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DB_DIR / "twitter_monitor.json"

# Schema:
# {
#   "bearer_token": "AAAA...",            ← saved by .twsetup (persists updates)
#   "monitors": {
#     "<twitter_username_lower>": {
#       "username": "realUsername",
#       "display_name": "Real Name",
#       "user_id": "1234567890",
#       "targets": ["-100xxx", "-100yyy"],
#       "last_tweet_id": "1234567890123456789"
#     }
#   }
# }

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
# TWITTER API v2 HELPERS
# ─────────────────────────────────────────────────────────────────────────────

TWITTER_API_BASE = "https://api.twitter.com/2"

def _headers() -> dict:
    return {"Authorization": f"Bearer {_get_token()}"}


async def _api_get(session: aiohttp.ClientSession, path: str, params: dict) -> dict | None:
    """Perform a GET request against the Twitter v2 API."""
    try:
        async with session.get(
            f"{TWITTER_API_BASE}{path}",
            headers=_headers(),
            params=params,
            timeout=aiohttp.ClientTimeout(total=20),
        ) as resp:
            if resp.status == 200:
                return await resp.json()
            return None
    except Exception:
        return None


async def resolve_twitter_user(username: str) -> tuple[str | None, str | None]:
    """
    Resolve a Twitter username to (user_id, display_name).
    Returns (None, None) on failure.
    """
    async with aiohttp.ClientSession() as session:
        data = await _api_get(
            session,
            f"/users/by/username/{username.lstrip('@')}",
            {"user.fields": "name,username"},
        )
    if data and "data" in data:
        return data["data"]["id"], data["data"]["name"]
    return None, None


async def fetch_latest_tweets(
    user_id: str,
    since_id: str | None = None,
    max_results: int = 5,
) -> list[dict]:
    """
    Fetch the most recent tweets from a user, optionally newer than since_id.
    Returns a list of tweet dicts (newest last so we process in chronological order).
    """
    params = {
        "max_results": max_results,
        "tweet.fields": "created_at,text,attachments,entities",
        "expansions": "attachments.media_keys,author_id",
        "media.fields": "type,url,preview_image_url,variants",
        "exclude": "retweets,replies",
    }
    if since_id:
        params["since_id"] = since_id

    async with aiohttp.ClientSession() as session:
        data = await _api_get(session, f"/users/{user_id}/tweets", params)

    if not data or "data" not in data:
        return []

    tweets = data["data"]

    # Build a media_key → media_info lookup
    media_map: dict[str, dict] = {}
    if "includes" in data and "media" in data["includes"]:
        for m in data["includes"]["media"]:
            media_map[m["media_key"]] = m

    # Attach media info directly into each tweet dict
    for tweet in tweets:
        tweet["_media"] = []
        keys = (tweet.get("attachments") or {}).get("media_keys", [])
        for key in keys:
            if key in media_map:
                tweet["_media"].append(media_map[key])

    # Oldest first so messages appear in correct order in Telegram
    tweets.reverse()
    return tweets


# ─────────────────────────────────────────────────────────────────────────────
# MEDIA DOWNLOAD HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _best_video_url(media: dict) -> str | None:
    """Pick the highest-bitrate mp4 from a video media object."""
    variants = media.get("variants") or []
    mp4s = [v for v in variants if v.get("content_type") == "video/mp4"]
    if not mp4s:
        return None
    return max(mp4s, key=lambda v: v.get("bit_rate", 0))["url"]


async def _download_file(url: str, suffix: str) -> str | None:
    """Download a URL to a temp file. Returns path or None."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=60)) as resp:
                if resp.status != 200:
                    return None
                tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
                tmp_path = tmp.name
                tmp.close()
                async with aiofiles.open(tmp_path, "wb") as f:
                    async for chunk in resp.content.iter_chunked(1024 * 64):
                        await f.write(chunk)
        return tmp_path
    except Exception:
        return None


async def _get_media_files(media_list: list[dict]) -> list[str]:
    """
    Download all media items to temp files.
    Returns list of local file paths.
    """
    paths = []
    for media in media_list:
        mtype = media.get("type", "")
        if mtype == "photo":
            url = media.get("url")
            if url:
                path = await _download_file(url, ".jpg")
                if path:
                    paths.append(path)
        elif mtype in ("video", "animated_gif"):
            url = _best_video_url(media)
            if url:
                path = await _download_file(url, ".mp4")
                if path:
                    paths.append(path)
    return paths


# ─────────────────────────────────────────────────────────────────────────────
# TELEGRAM POSTING
# ─────────────────────────────────────────────────────────────────────────────

def _format_caption(tweet: dict, username: str, display_name: str) -> str:
    """Build the Telegram caption for a tweet."""
    text = tweet.get("text", "")
    tweet_id = tweet.get("id", "")
    created = tweet.get("created_at", "")

    # Parse timestamp
    try:
        dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
        time_str = dt.strftime("%d %b %Y • %H:%M UTC")
    except Exception:
        time_str = created

    tweet_url = f"https://twitter.com/{username}/status/{tweet_id}"

    caption = (
        f"🐦 <b>New Tweet from <a href=\"https://twitter.com/{username}\">"
        f"{display_name} (@{username})</a></b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"{text}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🕐 <i>{time_str}</i>\n"
        f"🔗 <a href=\"{tweet_url}\">View on X/Twitter</a>\n\n"
        f"<i>Powered by PARADOX</i>"
    )
    return caption


async def _post_tweet_to_telegram(client, target_id: int, tweet: dict, username: str, display_name: str):
    """Send a single tweet (with media) to a Telegram chat."""
    caption = _format_caption(tweet, username, display_name)
    media_list = tweet.get("_media", [])

    if not media_list:
        # Text-only tweet
        await client.send_message(target_id, caption, parse_mode="html", link_preview=False)
        return

    # Download media
    files = await _get_media_files(media_list)

    if not files:
        # Media failed to download — post text only
        await client.send_message(target_id, caption, parse_mode="html", link_preview=False)
        return

    try:
        if len(files) == 1:
            await client.send_file(
                target_id,
                files[0],
                caption=caption,
                parse_mode="html",
            )
        else:
            # Multiple files — send as album; caption only on first file
            captions = [caption] + [""] * (len(files) - 1)
            await client.send_file(
                target_id,
                files,
                caption=captions,
                parse_mode="html",
            )
    finally:
        # Clean up temp files
        for fp in files:
            try:
                os.unlink(fp)
            except Exception:
                pass


# ─────────────────────────────────────────────────────────────────────────────
# POLLING ENGINE
# ─────────────────────────────────────────────────────────────────────────────

_poll_tasks: dict[str, asyncio.Task] = {}  # username_lower → asyncio.Task


async def _poll_account(client, username_lower: str):
    """Background task that continuously polls one Twitter account."""
    while True:
        try:
            db = _load_db()
            monitor = db["monitors"].get(username_lower)

            if not monitor:
                # Monitor was removed — exit task
                break

            user_id = monitor["user_id"]
            display_name = monitor.get("display_name", monitor["username"])
            targets = monitor.get("targets", [])
            last_id = monitor.get("last_tweet_id")

            if not targets:
                await asyncio.sleep(POLL_INTERVAL)
                continue

            tweets = await fetch_latest_tweets(user_id, since_id=last_id, max_results=10)

            if tweets:
                # Update last tweet ID to the newest one (last in chronological list)
                db["monitors"][username_lower]["last_tweet_id"] = tweets[-1]["id"]
                _save_db(db)

                for tweet in tweets:
                    for target_str in targets:
                        try:
                            await _post_tweet_to_telegram(
                                client,
                                int(target_str),
                                tweet,
                                monitor["username"],
                                display_name,
                            )
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
    """Start (or restart) the polling task for a username."""
    # Cancel old task if running
    old = _poll_tasks.get(username_lower)
    if old and not old.done():
        old.cancel()
    task = asyncio.ensure_future(_poll_account(client, username_lower))
    _poll_tasks[username_lower] = task


def _stop_monitor_task(username_lower: str):
    """Cancel the polling task for a username."""
    task = _poll_tasks.pop(username_lower, None)
    if task and not task.done():
        task.cancel()


async def _resume_all_monitors(client):
    """Re-start polling tasks for all monitors saved in DB (called at startup)."""
    db = _load_db()
    for username_lower in list(db["monitors"].keys()):
        _start_monitor_task(client, username_lower)


# ─────────────────────────────────────────────────────────────────────────────
# HELP MENU  +  STARTUP
# ─────────────────────────────────────────────────────────────────────────────

def init(client_instance):
    commands = [
        ".twsetup <bearer_token>                          — Save your Twitter Bearer Token (once only)",
        ".twmonitor add <@twitter_user> <telegram_chat>  — Start auto-posting tweets",
        ".twmonitor del <@twitter_user> [telegram_chat]  — Stop monitoring (all or specific chat)",
        ".twmonitor list                                  — Show all active monitors",
        ".twmonitor test <@twitter_user>                 — Post the latest tweet right now",
        ".twdl <tweet_url>                               — Download & send tweet media",
    ]
    description = (
        "🐦 <b>Twitter Monitor</b> — Auto-post tweets to Telegram\n"
        "Supports photos, videos, multi-media albums & text.\n"
        "Run <code>.twsetup &lt;token&gt;</code> once to configure."
    )
    add_handler("twitter", commands, description)

    # Schedule resume after event loop starts
    asyncio.ensure_future(_resume_all_monitors(client_instance))



# ─────────────────────────────────────────────────────────────────────────────
# COMMAND: .twsetup  — save bearer token to DB (persists across bot updates)
# ─────────────────────────────────────────────────────────────────────────────

@CipherElite.on(events.NewMessage(pattern=r"^\.twsetup(?:\s|$)(.*)"))
@rishabh()
async def twsetup_command(event):
    await event.delete()

    token = (event.pattern_match.group(1) or "").strip()

    if not token:
        db = _load_db()
        current = db.get("bearer_token", "")
        masked = f"{current[:10]}...{current[-5:]}" if len(current) > 15 else ("✅ Set" if current else "❌ Not set")
        return await event.respond(
            "🔑 <b>Twitter Bearer Token Setup</b>\n\n"
            f"Current token: <code>{masked}</code>\n\n"
            "To set/update your token:\n"
            "<code>.twsetup YOUR_BEARER_TOKEN_HERE</code>\n\n"
            "Get a free token at <a href=\"https://developer.twitter.com/\">developer.twitter.com</a>\n"
            "<i>Your token is saved to the DB folder and persists across bot updates.</i>",
            parse_mode="html",
        )

    # Basic format check (Bearer tokens start with AAAA and are long)
    if len(token) < 50 or not token.startswith("AAAA"):
        return await event.respond(
            "❌ <b>That doesn't look like a valid Bearer Token.</b>\n\n"
            "Bearer tokens start with <code>AAAA</code> and are very long.\n"
            "Get yours at <a href=\"https://developer.twitter.com/\">developer.twitter.com</a>",
            parse_mode="html",
        )

    # Save to DB
    db = _load_db()
    db["bearer_token"] = token
    if "monitors" not in db:
        db["monitors"] = {}
    _save_db(db)

    await event.respond(
        "✅ <b>Twitter Bearer Token saved!</b>\n\n"
        "Your token is stored in <code>DB/twitter_monitor.json</code> and will persist across bot updates.\n\n"
        "You can now use:\n"
        "<code>.twmonitor add @username -100xxxxxxxxx</code>",
        parse_mode="html",
    )


# ─────────────────────────────────────────────────────────────────────────────
# COMMAND: .twmonitor
# ─────────────────────────────────────────────────────────────────────────────

@CipherElite.on(events.NewMessage(pattern=r"^\.twmonitor(?:\s|$)(.*)"))
@rishabh()
async def twmonitor_command(event):
    await event.delete()

    if not _get_token():
        return await event.respond(
            "❌ <b>Twitter Bearer Token not configured!</b>\n\n"
            "Run this command first:\n"
            "<code>.twsetup YOUR_BEARER_TOKEN_HERE</code>\n\n"
            "Get a free token at <a href=\"https://developer.twitter.com/\">developer.twitter.com</a>",
            parse_mode="html",
        )

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
        tg_target = parts[2]

        # Validate Telegram target
        try:
            tg_id = int(tg_target)
        except ValueError:
            return await event.respond("❌ Telegram chat ID must be a number (e.g. <code>-1001234567890</code>).", parse_mode="html")

        status = await event.respond(f"🔍 <b>Resolving @{tw_user} on Twitter/X...</b>", parse_mode="html")

        user_id, display_name = await resolve_twitter_user(tw_user)
        if not user_id:
            return await status.edit(
                f"❌ <b>Could not find Twitter user @{tw_user}.</b>\n"
                "Make sure the username is correct and your Bearer Token is valid.",
                parse_mode="html",
            )

        db = _load_db()
        key = tw_user.lower()

        if key not in db["monitors"]:
            # Fetch the most recent tweet ID so we don't re-post old tweets
            tweets = await fetch_latest_tweets(user_id, max_results=1)
            last_id = tweets[0]["id"] if tweets else None

            db["monitors"][key] = {
                "username": tw_user,
                "display_name": display_name,
                "user_id": user_id,
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
            f"<i>New tweets will be posted automatically with full media support.</i>",
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
            # Remove only a specific target
            target_str = str(parts[2])
            if target_str in db["monitors"][key]["targets"]:
                db["monitors"][key]["targets"].remove(target_str)
                msg = f"🗑️ Removed target <code>{target_str}</code> from <b>@{tw_user}</b> monitor."
            else:
                msg = f"⚠️ Target <code>{target_str}</code> was not in the monitor list."

            # If no targets left, remove the whole monitor
            if not db["monitors"][key]["targets"]:
                del db["monitors"][key]
                _stop_monitor_task(key)
                msg += "\n<i>No targets left — monitor fully stopped.</i>"
        else:
            # Remove the whole monitor
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
            status_icon = "🟢" if running else "🔴"
            text += (
                f"{status_icon} <b><a href=\"https://twitter.com/{m['username']}\">@{m['username']}</a></b>"
                f" ({m.get('display_name', '?')})\n"
            )
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
                f"⚠️ <b>@{tw_user}</b> is not in your monitor list.\n"
                "Add it first with <code>.twmonitor add</code>.",
                parse_mode="html",
            )

        status = await event.respond(f"⏳ <b>Fetching latest tweet from @{tw_user}...</b>", parse_mode="html")

        m = db["monitors"][key]
        tweets = await fetch_latest_tweets(m["user_id"], max_results=1)

        if not tweets:
            return await status.edit("❌ Could not fetch any tweets. Is the account active?", parse_mode="html")

        tweet = tweets[0]
        targets = m.get("targets", [])
        if not targets:
            return await status.edit("⚠️ No Telegram targets configured for this monitor.", parse_mode="html")

        await status.edit("📤 <b>Posting latest tweet to all targets...</b>", parse_mode="html")

        for target_str in targets:
            try:
                await _post_tweet_to_telegram(
                    event.client,
                    int(target_str),
                    tweet,
                    m["username"],
                    m.get("display_name", m["username"]),
                )
            except Exception as e:
                await event.respond(f"⚠️ Failed to post to <code>{target_str}</code>: <code>{e}</code>", parse_mode="html")

        await status.edit("✅ <b>Test post complete!</b>", parse_mode="html")

    else:
        await event.respond(_help_text(), parse_mode="html")


# ─────────────────────────────────────────────────────────────────────────────
# COMMAND: .twdl  (download any tweet media by URL)
# ─────────────────────────────────────────────────────────────────────────────

@CipherElite.on(events.NewMessage(pattern=r"^\.twdl(?:\s|$)(.*)"))
@rishabh()
async def twdl_command(event):
    await event.delete()

    url_arg = (event.pattern_match.group(1) or "").strip()
    if not url_arg:
        return await event.respond("❌ <b>Usage:</b> <code>.twdl &lt;tweet_url&gt;</code>", parse_mode="html")

    # Extract tweet ID from URL
    import re
    m = re.search(r"(?:twitter\.com|x\.com)/\w+/status/(\d+)", url_arg)
    if not m:
        return await event.respond("❌ <b>Invalid tweet URL.</b>", parse_mode="html")

    tweet_id = m.group(1)
    status = await event.respond("⬇️ <b>Fetching tweet media...</b>", parse_mode="html")

    async with aiohttp.ClientSession() as session:
        data = await _api_get(
            session,
            f"/tweets/{tweet_id}",
            {
                "tweet.fields": "created_at,text,attachments",
                "expansions": "attachments.media_keys,author_id",
                "media.fields": "type,url,preview_image_url,variants",
                "user.fields": "username,name",
            },
        )

    if not data or "data" not in data:
        return await status.edit("❌ Could not fetch tweet. Check the URL or your Bearer Token.", parse_mode="html")

    tweet = data["data"]

    # Build media map
    media_map = {}
    if "includes" in data and "media" in data["includes"]:
        for med in data["includes"]["media"]:
            media_map[med["media_key"]] = med

    tweet["_media"] = []
    for key in (tweet.get("attachments") or {}).get("media_keys", []):
        if key in media_map:
            tweet["_media"].append(media_map[key])

    # Resolve author
    username = "unknown"
    display_name = "Unknown"
    if "includes" in data and "users" in data["includes"]:
        u = data["includes"]["users"][0]
        username = u.get("username", username)
        display_name = u.get("name", display_name)

    if not tweet["_media"]:
        # No media — just send text
        await status.edit(
            f"ℹ️ <b>No media found in this tweet.</b>\n\n{tweet.get('text', '')}",
            parse_mode="html",
        )
        return

    await status.edit("📥 <b>Downloading media files...</b>", parse_mode="html")
    files = await _get_media_files(tweet["_media"])

    if not files:
        return await status.edit("❌ Failed to download media from this tweet.", parse_mode="html")

    caption = _format_caption(tweet, username, display_name)

    try:
        await status.edit("📤 <b>Uploading to Telegram...</b>", parse_mode="html")
        if len(files) == 1:
            await event.client.send_file(event.chat_id, files[0], caption=caption, parse_mode="html")
        else:
            captions = [caption] + [""] * (len(files) - 1)
            await event.client.send_file(event.chat_id, files, caption=captions, parse_mode="html")
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
        "⚙️ <b>Setup:</b> Add <code>TWITTER_BEARER_TOKEN=xxx</code> to your <code>.env</code>\n"
        "Get a free token at <a href=\"https://developer.twitter.com/\">developer.twitter.com</a>\n\n"
        "<i>Powered by PARADOX</i>"
    )
