# =============================================================================
#  CipherElite Userbot Plugin — Twitter Monitor (via twscrape)
#  No developer API needed — uses a regular Twitter/X account.
#  Setup: .twaccount add <username> <password> <email> <email_password>
# =============================================================================

import os, re, json, asyncio, tempfile
import aiohttp, aiofiles
from pathlib import Path
from datetime import datetime, timezone

from telethon import events
from telethon.errors import FloodWaitError
from utils.utils import CipherElite
from utils.decorators import rishabh
from plugins.bot import add_handler

try:
    from twscrape import API as TwAPI
    from twscrape.logger import set_log_level
    set_log_level("ERROR")
    TWSCRAPE_OK = True
except ImportError:
    TWSCRAPE_OK = False

# ─── CONFIG ───────────────────────────────────────────────────────────────────
POLL_INTERVAL = 120

DB_DIR = Path("DB")
DB_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH      = DB_DIR / "twitter_monitor.json"
ACCOUNTS_DB  = str(DB_DIR / "twscrape.db")

_tw_api = None

async def _api() -> "TwAPI | None":
    global _tw_api
    if not TWSCRAPE_OK:
        return None
    if _tw_api is None:
        _tw_api = TwAPI(ACCOUNTS_DB)
    return _tw_api

async def _has_active_accounts() -> bool:
    a = await _api()
    if not a:
        return False
    accs = await a.pool.get_all()
    return any(acc.active for acc in accs)

# ─── DB ───────────────────────────────────────────────────────────────────────
def _load_db():
    if DB_PATH.exists():
        try:
            return json.loads(DB_PATH.read_text("utf-8"))
        except Exception:
            pass
    return {"monitors": {}}

def _save_db(db):
    DB_PATH.write_text(json.dumps(db, indent=2, ensure_ascii=False), "utf-8")

# ─── TWITTER HELPERS ──────────────────────────────────────────────────────────
def _best_video(variants) -> str | None:
    mp4 = [v for v in (variants or []) if getattr(v, "contentType", "") == "video/mp4"]
    return max(mp4, key=lambda v: getattr(v, "bitrate", 0)).url if mp4 else None

def _tweet_to_dict(t) -> dict:
    media = []
    if t.media:
        for p in (t.media.photos or []):
            url = getattr(p, "fullUrl", None) or getattr(p, "url", None)
            if url: media.append({"type": "photo", "url": url})
        for v in list(t.media.videos or []) + list(t.media.animated or []):
            url = _best_video(getattr(v, "variants", None))
            if url: media.append({"type": "video", "url": url})
    time_str = t.date.strftime("%d %b %Y • %H:%M UTC") if t.date else ""
    return {"id": str(t.id), "text": t.rawContent or "", "url": t.url or "", "time_str": time_str, "_media": media}

async def _resolve_user(username: str):
    a = await _api()
    if not a: return None, None
    try:
        u = await a.user_by_login(username.lstrip("@"))
        if u: return str(u.id), u.displayname
    except Exception as e:
        print(f"[twitter] resolve error: {e}")
    return None, None

async def _fetch_tweets(user_id: str, since_id: str | None = None, limit: int = 10) -> list[dict]:
    a = await _api()
    if not a: return []
    results = []
    try:
        async for t in a.user_tweets(int(user_id), limit=limit):
            if t.retweetedTweet or t.inReplyToTweetId:
                continue
            if since_id and str(t.id) <= since_id:
                continue
            results.append(_tweet_to_dict(t))
            if len(results) >= limit:
                break
    except Exception as e:
        print(f"[twitter] fetch error: {e}")
    results.reverse()  # oldest first
    return results

# ─── MEDIA DOWNLOAD ───────────────────────────────────────────────────────────
async def _dl(url: str, suffix: str) -> str | None:
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(url, timeout=aiohttp.ClientTimeout(total=60), headers={"User-Agent": "Mozilla/5.0"}) as r:
                if r.status != 200: return None
                tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
                path = tmp.name; tmp.close()
                async with aiofiles.open(path, "wb") as f:
                    async for chunk in r.content.iter_chunked(65536):
                        await f.write(chunk)
        return path
    except Exception:
        return None

async def _get_files(media: list) -> list[str]:
    paths = []
    for m in media:
        p = await _dl(m["url"], ".mp4" if m["type"] == "video" else ".jpg")
        if p: paths.append(p)
    return paths

# ─── TELEGRAM POSTING ─────────────────────────────────────────────────────────
def _caption(tweet: dict, username: str, display_name: str) -> str:
    return (
        f"🐦 <b>New Tweet from <a href=\"https://twitter.com/{username}\">{display_name} (@{username})</a></b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n{tweet['text']}\n━━━━━━━━━━━━━━━━━━━━\n"
        f"🕐 <i>{tweet['time_str']}</i>\n🔗 <a href=\"{tweet['url']}\">View on X/Twitter</a>\n\n"
        f"<i>Powered by PARADOX</i>"
    )

async def _post(client, target_id: int, tweet: dict, username: str, display_name: str):
    cap = _caption(tweet, username, display_name)
    files = await _get_files(tweet.get("_media", []))
    try:
        if not files:
            await client.send_message(target_id, cap, parse_mode="html", link_preview=False)
        elif len(files) == 1:
            await client.send_file(target_id, files[0], caption=cap, parse_mode="html")
        else:
            await client.send_file(target_id, files, caption=[cap] + [""] * (len(files) - 1), parse_mode="html")
    finally:
        for fp in files:
            try: os.unlink(fp)
            except Exception: pass

# ─── POLLING ENGINE ───────────────────────────────────────────────────────────
_tasks: dict[str, asyncio.Task] = {}
_pending_accounts: dict[str, tuple] = {}  # username_lower -> (password, email)

async def _poll(client, key: str):
    while True:
        try:
            db = _load_db()
            mon = db["monitors"].get(key)
            if not mon: break
            targets = mon.get("targets", [])
            if targets:
                tweets = await _fetch_tweets(mon["user_id"], mon.get("last_tweet_id"), 10)
                if tweets:
                    db["monitors"][key]["last_tweet_id"] = tweets[-1]["id"]
                    _save_db(db)
                    for t in tweets:
                        for tgt in targets:
                            try:
                                await _post(client, int(tgt), t, mon["username"], mon.get("display_name", mon["username"]))
                                await asyncio.sleep(1.5)
                            except FloodWaitError as e:
                                await asyncio.sleep(e.seconds + 5)
                            except Exception as e:
                                print(f"[twitter] post error: {e}")
        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"[twitter] poll error {key}: {e}")
        await asyncio.sleep(POLL_INTERVAL)

def _start(client, key):
    old = _tasks.get(key)
    if old and not old.done(): old.cancel()
    _tasks[key] = asyncio.ensure_future(_poll(client, key))

def _stop(key):
    t = _tasks.pop(key, None)
    if t and not t.done(): t.cancel()

async def _resume(client):
    for key in list(_load_db()["monitors"].keys()):
        _start(client, key)

# ─── INIT ─────────────────────────────────────────────────────────────────────
def init(client_instance):
    add_handler("twitter", [
        ".twaccount add <user> <pass> <email> <email_pass>  — Add Twitter login account",
        ".twaccount list                                      — List configured accounts",
        ".twmonitor add <@user> <chat_id>                    — Start monitoring",
        ".twmonitor del <@user> [chat_id]                    — Stop monitoring",
        ".twmonitor list                                      — Show monitors",
        ".twmonitor test <@user>                             — Post latest tweet now",
        ".twdl <tweet_url>                                   — Download tweet media",
    ], "🐦 <b>Twitter Monitor</b> — No API key needed. Add a regular Twitter account with .twaccount add.")
    asyncio.ensure_future(_resume(client_instance))

# ─── .twaccount ───────────────────────────────────────────────────────────────
def _no_twscrape_msg():
    return "❌ <b>twscrape not installed!</b>\nRun: <code>pip install twscrape</code>"

def _no_account_msg():
    return (
        "❌ <b>No active Twitter account configured.</b>\n\n"
        "Add one with:\n<code>.twaccount add username password email email_password</code>\n\n"
        "<i>Use a spare Twitter/X account, not your main one.</i>"
    )

@CipherElite.on(events.NewMessage(pattern=r"^\.twaccount(?:\s|$)(.*)"))
@rishabh()
async def twaccount_cmd(event):
    await event.delete()
    if not TWSCRAPE_OK:
        return await event.respond(_no_twscrape_msg(), parse_mode="html")

    args = (event.pattern_match.group(1) or "").strip().split()
    if not args:
        return await event.respond(
            "🐦 <b>Twitter Account Manager</b>\n\n"
            "• <code>.twaccount add &lt;username&gt; &lt;password&gt; &lt;email&gt; &lt;email_password&gt;</code>\n"
            "• <code>.twaccount list</code>\n"
            "• <code>.twaccount del &lt;username&gt;</code>",
            parse_mode="html",
        )

    subcmd = args[0].lower()
    a = await _api()

    if subcmd == "add":
        if len(args) < 4:
            return await event.respond(
                "❌ Usage: <code>.twaccount add &lt;username&gt; &lt;password&gt; &lt;email&gt; [email_password]</code>\n\n"
                "<i>email_password is optional — only needed if Twitter sends a verification code to your email during login.</i>",
                parse_mode="html",
            )
        user, pw, email = args[1], args[2], args[3]
        epw = args[4] if len(args) >= 5 else ""
        st = await event.respond(f"⏳ <b>Logging in @{user}...</b>", parse_mode="html")
        try:
            await a.pool.add_account(user, pw, email, epw)
            await a.pool.login_all()
            accs = await a.pool.get_all()
            acc = next((ac for ac in accs if ac.username.lower() == user.lower()), None)
            if acc and acc.active:
                _pending_accounts.pop(user.lower(), None)
                total_active = sum(1 for ac in accs if ac.active)
                await st.edit(
                    f"✅ <b>@{user} logged in!</b>\nActive accounts: {total_active}\n\nYou can now use <code>.twmonitor add</code>.",
                    parse_mode="html",
                )
            else:
                # Login incomplete — Twitter likely needs a verification code
                _pending_accounts[user.lower()] = (pw, email)
                await st.edit(
                    f"⚠️ <b>Twitter is asking for a verification code.</b>\n\n"
                    f"Check your email <code>{email}</code> for a code from Twitter,\n"
                    f"then send:\n<code>.twverify {user} YOUR_CODE</code>",
                    parse_mode="html",
                )
        except Exception as e:
            await st.edit(f"❌ <b>Login error:</b> <code>{e}</code>", parse_mode="html")

    elif subcmd == "list":
        accs = await a.pool.get_all()
        if not accs:
            return await event.respond("📭 No Twitter accounts configured.", parse_mode="html")
        text = "🐦 <b>Twitter Accounts:</b>\n\n"
        for ac in accs:
            text += f"{'🟢' if ac.active else '🔴'} <code>{ac.username}</code>\n"
        await event.respond(text, parse_mode="html")

    elif subcmd == "del":
        if len(args) < 2:
            return await event.respond("❌ Usage: <code>.twaccount del &lt;username&gt;</code>", parse_mode="html")
        try:
            await a.pool.delete_accounts([args[1]])
            await event.respond(f"🗑️ Account <code>{args[1]}</code> removed.", parse_mode="html")
        except Exception as e:
            await event.respond(f"❌ <code>{e}</code>", parse_mode="html")
    else:
        await event.respond("❌ Unknown subcommand. Use <code>add</code>, <code>list</code>, or <code>del</code>.", parse_mode="html")


# ─── .twverify ────────────────────────────────────────────────────────────────
@CipherElite.on(events.NewMessage(pattern=r"^\.twverify(?:\s|$)(.*)"))
@rishabh()
async def twverify_cmd(event):
    await event.delete()
    if not TWSCRAPE_OK:
        return await event.respond(_no_twscrape_msg(), parse_mode="html")

    args = (event.pattern_match.group(1) or "").strip().split()
    if len(args) < 2:
        return await event.respond(
            "❌ <b>Usage:</b> <code>.twverify &lt;username&gt; &lt;code&gt;</code>\n"
            "<i>Run this after Twitter asks for a verification code during .twaccount add</i>",
            parse_mode="html",
        )

    username, code = args[0], args[1]
    key = username.lower()

    if key not in _pending_accounts:
        return await event.respond(
            f"⚠️ No pending login for <code>{username}</code>.\n"
            "Use <code>.twaccount add</code> first.",
            parse_mode="html",
        )

    pw, email = _pending_accounts[key]
    st = await event.respond(f"⏳ <b>Submitting verification code for @{username}...</b>", parse_mode="html")

    try:
        a = await _api()
        # Remove the failed account and re-add supplying the code as email_password
        # twscrape will use it to complete email verification
        await a.pool.delete_accounts([username])
        await a.pool.add_account(username, pw, email, code)
        await a.pool.login_all()

        accs = await a.pool.get_all()
        acc = next((ac for ac in accs if ac.username.lower() == key), None)

        if acc and acc.active:
            del _pending_accounts[key]
            await st.edit(
                f"✅ <b>@{username} verified and logged in!</b>\n\n"
                "You can now use <code>.twmonitor add</code>.",
                parse_mode="html",
            )
        else:
            await st.edit(
                "❌ <b>Verification failed.</b>\n"
                "The code may be wrong or expired. Try <code>.twaccount add</code> again.",
                parse_mode="html",
            )
    except Exception as e:
        await st.edit(f"❌ <b>Error:</b> <code>{e}</code>", parse_mode="html")

# ─── .twmonitor ───────────────────────────────────────────────────────────────
@CipherElite.on(events.NewMessage(pattern=r"^\.twmonitor(?:\s|$)(.*)"))
@rishabh()
async def twmonitor_cmd(event):
    await event.delete()
    if not TWSCRAPE_OK:
        return await event.respond(_no_twscrape_msg(), parse_mode="html")

    args = (event.pattern_match.group(1) or "").strip().split()
    if not args:
        return await event.respond(_monitor_help(), parse_mode="html")

    subcmd = args[0].lower()

    # ADD
    if subcmd == "add":
        if len(args) < 3:
            return await event.respond("❌ Usage: <code>.twmonitor add &lt;@user&gt; &lt;chat_id&gt;</code>", parse_mode="html")
        if not await _has_active_accounts():
            return await event.respond(_no_account_msg(), parse_mode="html")

        tw_user = args[1].lstrip("@")
        try:
            tg_id = int(args[2])
        except ValueError:
            return await event.respond("❌ Chat ID must be a number.", parse_mode="html")

        st = await event.respond(f"🔍 <b>Looking up @{tw_user}...</b>", parse_mode="html")
        user_id, display_name = await _resolve_user(tw_user)
        if not user_id:
            return await st.edit(f"❌ <b>Could not find @{tw_user}.</b>\nCheck username or try again.", parse_mode="html")

        db = _load_db()
        key = tw_user.lower()
        if key not in db["monitors"]:
            tweets = await _fetch_tweets(user_id, limit=1)
            db["monitors"][key] = {"username": tw_user, "display_name": display_name, "user_id": user_id, "targets": [], "last_tweet_id": tweets[0]["id"] if tweets else None}

        tgt = str(tg_id)
        if tgt not in db["monitors"][key]["targets"]:
            db["monitors"][key]["targets"].append(tgt)
        _save_db(db)
        _start(event.client, key)
        await st.edit(
            f"✅ <b>Monitor started!</b>\n🐦 <a href=\"https://twitter.com/{tw_user}\">@{tw_user}</a> ({display_name})\n📩 Target: <code>{tg_id}</code>\n⏱ Every {POLL_INTERVAL}s",
            parse_mode="html",
        )

    # DEL
    elif subcmd == "del":
        if len(args) < 2:
            return await event.respond("❌ Usage: <code>.twmonitor del &lt;@user&gt; [chat_id]</code>", parse_mode="html")
        key = args[1].lstrip("@").lower()
        db = _load_db()
        if key not in db["monitors"]:
            return await event.respond(f"⚠️ @{args[1].lstrip('@')} is not monitored.", parse_mode="html")
        if len(args) >= 3:
            tgt = str(args[2])
            db["monitors"][key]["targets"] = [t for t in db["monitors"][key]["targets"] if t != tgt]
            msg = f"🗑️ Removed target <code>{tgt}</code>."
            if not db["monitors"][key]["targets"]:
                del db["monitors"][key]; _stop(key)
                msg += "\n<i>No targets left — monitor stopped.</i>"
        else:
            del db["monitors"][key]; _stop(key)
            msg = f"🗑️ Monitor for <b>@{args[1].lstrip('@')}</b> stopped."
        _save_db(db)
        await event.respond(msg, parse_mode="html")

    # LIST
    elif subcmd == "list":
        db = _load_db()
        monitors = db.get("monitors", {})
        if not monitors:
            return await event.respond("📭 No active monitors.", parse_mode="html")
        text = "🐦 <b>Active Monitors:</b>\n━━━━━━━━━━━━━━━━━━━━\n\n"
        for key, m in monitors.items():
            icon = "🟢" if (key in _tasks and not _tasks[key].done()) else "🔴"
            text += f"{icon} <b><a href=\"https://twitter.com/{m['username']}\">@{m['username']}</a></b> ({m.get('display_name','?')})\n"
            for t in m.get("targets", []):
                text += f"   └ 📩 <code>{t}</code>\n"
        text += "\n<i>Powered by PARADOX</i>"
        await event.respond(text, parse_mode="html")

    # TEST
    elif subcmd == "test":
        if len(args) < 2:
            return await event.respond("❌ Usage: <code>.twmonitor test &lt;@user&gt;</code>", parse_mode="html")
        key = args[1].lstrip("@").lower()
        db = _load_db()
        if key not in db["monitors"]:
            return await event.respond(f"⚠️ @{args[1].lstrip('@')} is not monitored.", parse_mode="html")
        st = await event.respond(f"⏳ <b>Fetching latest tweet...</b>", parse_mode="html")
        mon = db["monitors"][key]
        tweets = await _fetch_tweets(mon["user_id"], limit=1)
        if not tweets:
            return await st.edit("❌ Could not fetch tweets.", parse_mode="html")
        targets = mon.get("targets", [])
        if not targets:
            return await st.edit("⚠️ No Telegram targets set.", parse_mode="html")
        await st.edit("📤 <b>Posting...</b>", parse_mode="html")
        for tgt in targets:
            try:
                await _post(event.client, int(tgt), tweets[0], mon["username"], mon.get("display_name", mon["username"]))
            except Exception as e:
                await event.respond(f"⚠️ Failed: <code>{e}</code>", parse_mode="html")
        await st.edit("✅ <b>Test post complete!</b>", parse_mode="html")

    else:
        await event.respond(_monitor_help(), parse_mode="html")

# ─── .twdl ────────────────────────────────────────────────────────────────────
@CipherElite.on(events.NewMessage(pattern=r"^\.twdl(?:\s|$)(.*)"))
@rishabh()
async def twdl_cmd(event):
    await event.delete()
    if not TWSCRAPE_OK:
        return await event.respond(_no_twscrape_msg(), parse_mode="html")

    url_arg = (event.pattern_match.group(1) or "").strip()
    if not url_arg:
        return await event.respond("❌ Usage: <code>.twdl &lt;tweet_url&gt;</code>", parse_mode="html")

    m = re.search(r"(?:twitter\.com|x\.com)/\w+/status/(\d+)", url_arg)
    if not m:
        return await event.respond("❌ Invalid tweet URL.", parse_mode="html")

    if not await _has_active_accounts():
        return await event.respond(_no_account_msg(), parse_mode="html")

    tweet_id = int(m.group(1))
    st = await event.respond("⬇️ <b>Fetching tweet...</b>", parse_mode="html")
    a = await _api()
    try:
        t = await a.tweet_details(tweet_id)
    except Exception as e:
        return await st.edit(f"❌ <b>Error:</b> <code>{e}</code>", parse_mode="html")

    if not t:
        return await st.edit("❌ Tweet not found.", parse_mode="html")

    tweet = _tweet_to_dict(t)
    username = t.user.username if t.user else "unknown"
    display_name = t.user.displayname if t.user else "Unknown"

    if not tweet["_media"]:
        return await st.edit(f"ℹ️ <b>No media found.</b>\n\n{tweet['text']}", parse_mode="html")

    await st.edit("📥 <b>Downloading...</b>", parse_mode="html")
    files = await _get_files(tweet["_media"])
    if not files:
        return await st.edit("❌ Failed to download media.", parse_mode="html")

    cap = _caption(tweet, username, display_name)
    try:
        await st.edit("📤 <b>Uploading...</b>", parse_mode="html")
        if len(files) == 1:
            await event.client.send_file(event.chat_id, files[0], caption=cap, parse_mode="html")
        else:
            await event.client.send_file(event.chat_id, files, caption=[cap] + [""] * (len(files) - 1), parse_mode="html")
        await st.delete()
    except Exception as e:
        await st.edit(f"❌ <b>Upload error:</b> <code>{e}</code>", parse_mode="html")
    finally:
        for fp in files:
            try: os.unlink(fp)
            except Exception: pass

# ─── HELP ─────────────────────────────────────────────────────────────────────
def _monitor_help() -> str:
    return (
        "🐦 <b>Twitter Monitor — Help</b>\n━━━━━━━━━━━━━━━━━━━━\n\n"
        "• <code>.twmonitor add @user &lt;chat_id&gt;</code> — Start monitoring\n"
        "• <code>.twmonitor del @user [chat_id]</code> — Stop monitoring\n"
        "• <code>.twmonitor list</code> — Show monitors\n"
        "• <code>.twmonitor test @user</code> — Post latest tweet now\n"
        "• <code>.twdl &lt;tweet_url&gt;</code> — Download tweet media\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "⚙️ First time? Add an account:\n"
        "<code>.twaccount add username password email email_password</code>\n\n"
        "<i>Powered by PARADOX</i>"
    )
