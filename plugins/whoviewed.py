# =============================================================================
#  PARADOX Userbot Plugin
#
#  Plugin Name:    Who Viewed Your Profile
#  Description:    Statistical detector that tracks who comes online shortly
#                  after you change your profile picture. Builds a ranked
#                  "suspects" list over time with reaction times and hit counts.
#  License:        MIT
# =============================================================================

import asyncio
import json
import time
from pathlib import Path

from telethon import events
from telethon.tl.functions.photos import GetUserPhotosRequest
from telethon.tl.types import UserStatusOnline

from utils.utils import CipherElite
from utils.decorators import rishabh
from plugins.bot import add_handler

# ── Persistent Database ────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).parent.parent
DB_DIR = PROJECT_ROOT / "DB"
DB_DIR.mkdir(exist_ok=True)
WHOVIEWED_DB = DB_DIR / "whoviewed_db.json"

# Runtime state
_monitor_running = False
_monitor_task = None
_last_pfp_id = None
_pfp_change_time = None       # timestamp of last PFP change
_pre_change_statuses = {}     # snapshot BEFORE/at PFP change

DETECTION_WINDOW = 300   # 5 minutes after PFP change to watch
CHECK_INTERVAL = 25      # poll statuses every 25 seconds


def load_db():
    if WHOVIEWED_DB.exists():
        try:
            return json.loads(WHOVIEWED_DB.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"suspects": {}, "total_events": 0}


def save_db(db):
    try:
        WHOVIEWED_DB.write_text(
            json.dumps(db, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except Exception:
        pass


# ── Plugin Registration ────────────────────────────────────────────────────────
def init(client_instance):
    commands = [
        ".whoviewed start - Start monitoring who views your profile",
        ".whoviewed stop - Stop monitoring",
        ".whoviewed snap - Manually trigger a detection window NOW",
        ".whoviewed list - Show ranked suspects",
        ".whoviewed reset - Clear all collected data",
    ]
    desc = (
        "👁️ **Who Viewed Your Profile**\n"
        "Detects who comes online shortly after you change your PFP.\n"
        "Builds a ranked suspect list over time."
    )
    add_handler("whoviewed", commands, desc)


# ── Core Logic ─────────────────────────────────────────────────────────────────

async def _get_contact_statuses(client):
    """Snapshot online/offline status of top 80 private chat contacts."""
    statuses = {}
    try:
        me = await client.get_me()
        my_id = me.id
        dialogs = await client.get_dialogs(limit=80)
        for d in dialogs:
            try:
                ent = d.entity
                if not d.is_user:
                    continue
                if getattr(ent, "bot", False) or ent.id == my_id:
                    continue
                is_online = isinstance(getattr(ent, "status", None), UserStatusOnline)
                first = ent.first_name or ""
                last = ent.last_name or ""
                statuses[ent.id] = {
                    "name": f"{first} {last}".strip() or "Unknown",
                    "username": f"@{ent.username}" if ent.username else None,
                    "online": is_online,
                }
            except Exception:
                continue
    except Exception as e:
        print(f"WhoViewed: status fetch error: {e}")
    return statuses


async def _get_my_pfp_id(client):
    """Returns the ID of the current profile photo, or None."""
    try:
        me = await client.get_me()
        result = await client(
            GetUserPhotosRequest(user_id=me.id, offset=0, max_id=0, limit=1)
        )
        if result.photos:
            return result.photos[0].id
    except Exception:
        pass
    return None


async def _record_suspects(current_statuses, change_time):
    """Compare pre-change vs current: anyone who went offline→online is a suspect."""
    global _pre_change_statuses
    db = load_db()
    new_hits = 0

    for uid, curr in current_statuses.items():
        prev = _pre_change_statuses.get(uid)
        if prev and not prev["online"] and curr["online"]:
            # This person was OFFLINE before PFP change and is now ONLINE
            reaction_secs = round(time.time() - change_time)
            uid_str = str(uid)

            if uid_str not in db["suspects"]:
                db["suspects"][uid_str] = {
                    "name": curr["name"],
                    "username": curr.get("username"),
                    "hits": 0,
                    "avg_reaction_secs": 0,
                    "reactions": [],
                }

            entry = db["suspects"][uid_str]
            entry["hits"] += 1
            entry["name"] = curr["name"]
            entry["username"] = curr.get("username")
            entry["reactions"].append(reaction_secs)
            entry["reactions"] = entry["reactions"][-30]  # keep last 30
            entry["avg_reaction_secs"] = round(
                sum(entry["reactions"]) / len(entry["reactions"])
            )
            new_hits += 1

    save_db(db)
    return new_hits


async def _monitor_loop(client):
    """Background loop: detects PFP changes and monitors who reacts."""
    global _monitor_running, _last_pfp_id, _pfp_change_time, _pre_change_statuses

    # Initial snapshot
    _last_pfp_id = await _get_my_pfp_id(client)
    _pre_change_statuses = await _get_contact_statuses(client)
    _pfp_change_time = None

    try:
        await client.send_message(
            "me",
            "👁️ **WhoViewed Monitor Started!**\n"
            "I'm now watching for PFP changes and tracking who reacts.\n\n"
            "• Change your PFP or use `.forgepfp` to generate events.\n"
            "• Or use `.whoviewed snap` to manually trigger detection.\n"
            "• Use `.whoviewed list` to see results."
        )
    except Exception:
        pass

    while _monitor_running:
        try:
            await asyncio.sleep(CHECK_INTERVAL)
            if not _monitor_running:
                break

            # ── Check for automatic PFP change ──────────────────────────────
            if _pfp_change_time is None:
                current_pfp = await _get_my_pfp_id(client)
                if current_pfp and current_pfp != _last_pfp_id:
                    _last_pfp_id = current_pfp
                    _pfp_change_time = time.time()
                    _pre_change_statuses = await _get_contact_statuses(client)

                    try:
                        await client.send_message(
                            "me",
                            "👁️ **PFP Change Detected!**\n"
                            "Monitoring who comes online in the next 5 minutes..."
                        )
                    except Exception:
                        pass
                    continue
                else:
                    # No event active — keep the baseline fresh
                    _pre_change_statuses = await _get_contact_statuses(client)
                    continue

            # ── Active detection window ─────────────────────────────────────
            elapsed = time.time() - _pfp_change_time
            if elapsed <= DETECTION_WINDOW:
                current = await _get_contact_statuses(client)
                new_hits = await _record_suspects(current, _pfp_change_time)
                if new_hits:
                    print(f"WhoViewed: {new_hits} new suspects detected")
            else:
                # Window expired — finalize this event
                db = load_db()
                db["total_events"] = db.get("total_events", 0) + 1
                save_db(db)
                _pfp_change_time = None

                try:
                    total_suspects = len(db["suspects"])
                    await client.send_message(
                        "me",
                        f"👁️ **Detection Window Closed.**\n"
                        f"Total tracked suspects so far: **{total_suspects}**\n"
                        f"Use `.whoviewed list` to see rankings."
                    )
                except Exception:
                    pass

        except Exception as e:
            print(f"WhoViewed monitor error: {e}")
            await asyncio.sleep(60)

    print("WhoViewed: Monitor loop stopped.")


# ── Commands ───────────────────────────────────────────────────────────────────

@CipherElite.on(events.NewMessage(pattern=r"^\.whoviewed(?:\s+(.+))?$"))
@rishabh()
async def whoviewed_cmd(event):
    global _monitor_running, _monitor_task, _pfp_change_time, _pre_change_statuses

    arg = (event.pattern_match.group(1) or "").strip().lower()

    # ── START ──────────────────────────────────────────────────────────────
    if arg == "start":
        if _monitor_running:
            return await event.reply("⚠️ **Already running!** Use `.whoviewed stop` first.")
        _monitor_running = True
        _monitor_task = asyncio.create_task(_monitor_loop(event.client))
        await event.reply(
            "👁️ **WhoViewed Monitor Started!**\n\n"
            "I'll automatically detect when your PFP changes and track "
            "who comes online within 5 minutes.\n\n"
            "💡 **Tips:**\n"
            "• Use `.forgepfp` for automatic PFP changes\n"
            "• Use `.whoviewed snap` for manual triggers\n"
            "• Use `.whoviewed list` to see results"
        )

    # ── STOP ───────────────────────────────────────────────────────────────
    elif arg == "stop":
        if not _monitor_running:
            return await event.reply("⚠️ **Not running.**")
        _monitor_running = False
        if _monitor_task and not _monitor_task.done():
            _monitor_task.cancel()
        _monitor_task = None
        await event.reply("🛑 **WhoViewed Monitor Stopped.**")

    # ── SNAP (manual trigger) ──────────────────────────────────────────────
    elif arg == "snap":
        if not _monitor_running:
            return await event.reply("⚠️ **Start the monitor first!** `.whoviewed start`")
        _pre_change_statuses = await _get_contact_statuses(event.client)
        _pfp_change_time = time.time()
        await event.reply(
            "📸 **Detection Window Activated!**\n\n"
            "Monitoring who comes online in the next 5 minutes.\n"
            "Use this right after you change your PFP manually!"
        )

    # ── LIST ───────────────────────────────────────────────────────────────
    elif arg == "list":
        db = load_db()
        suspects = db.get("suspects", {})
        total_events = db.get("total_events", 0)

        if not suspects:
            return await event.reply(
                "👁️ **No Data Yet.**\n\n"
                "Start the monitor and change your PFP a few times.\n"
                "The more events, the more accurate the results!"
            )

        # Sort by hits (descending), then by avg reaction time (ascending)
        ranked = sorted(
            suspects.items(),
            key=lambda x: (-x[1]["hits"], x[1]["avg_reaction_secs"])
        )

        medals = ["🥇", "🥈", "🥉"]
        lines = []
        for i, (uid, data) in enumerate(ranked[:15]):  # Top 15
            medal = medals[i] if i < 3 else f"**{i+1}.**"
            name = data["name"]
            uname = data.get("username") or f"ID:{uid}"
            hits = data["hits"]
            avg = data["avg_reaction_secs"]

            # Format reaction time nicely
            if avg < 60:
                time_str = f"{avg}s"
            else:
                time_str = f"{avg // 60}m {avg % 60}s"

            # Confidence indicator
            if hits >= 5:
                conf = "🔴 High"
            elif hits >= 3:
                conf = "🟡 Medium"
            else:
                conf = "⚪ Low"

            lines.append(
                f"{medal} **{name}** ({uname})\n"
                f"      ↳ Hits: `{hits}` | Avg: `{time_str}` | {conf}"
            )

        text = (
            f"👁️ **𝐖𝐇𝐎 𝐕𝐈𝐄𝐖𝐄𝐃 𝐘𝐎𝐔𝐑 𝐏𝐑𝐎𝐅𝐈𝐋𝐄?** 👁️\n"
            f"⟡ ═══════════════════ ⟡\n\n"
            f"📊 **PFP Events Tracked:** `{total_events}`\n"
            f"👤 **Unique Suspects:** `{len(suspects)}`\n\n"
            f"⟡ ═══════════════════ ⟡\n\n"
            + "\n\n".join(lines)
            + "\n\n⟡ ═══════════════════ ⟡\n"
            "💡 *More PFP changes = more accurate results*"
        )
        await event.reply(text)

    # ── RESET ──────────────────────────────────────────────────────────────
    elif arg == "reset":
        save_db({"suspects": {}, "total_events": 0})
        await event.reply("🔄 **WhoViewed data cleared!** Starting fresh.")

    # ── HELP ───────────────────────────────────────────────────────────────
    else:
        db = load_db()
        status = "🟢 Running" if _monitor_running else "🔴 Stopped"
        suspects = len(db.get("suspects", {}))
        events_count = db.get("total_events", 0)

        await event.reply(
            f"👁️ **WhoViewed Your Profile**\n\n"
            f"**Status:** {status}\n"
            f"**Suspects:** `{suspects}`\n"
            f"**Events:** `{events_count}`\n\n"
            f"`.whoviewed start` — Begin monitoring\n"
            f"`.whoviewed stop` — Stop monitoring\n"
            f"`.whoviewed snap` — Manual detection trigger\n"
            f"`.whoviewed list` — See ranked suspects\n"
            f"`.whoviewed reset` — Clear all data"
        )
