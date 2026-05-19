# =============================================================================
#  CipherElite Assistant Bot Plugin (CLEAN FULL VERSION)
# =============================================================================

import json
import html
from pathlib import Path
from telethon import events, Button

DB_PATH = Path(__file__).parent.parent / "DB" / "bot_assistant_db.json"

bot_instance = None
owner_user_id = None
owner_display_name = None


# ─────────────────────────────────────────────
# EVENT LOCK SYSTEM (FIXES DUPLICATION)
# ─────────────────────────────────────────────

def is_handled(event):
    return getattr(event, "_handled", False)

def mark_handled(event):
    event._handled = True


# ─────────────────────────────────────────────
# DATABASE
# ─────────────────────────────────────────────

def load_db():
    default = {
        "assistant_enabled": False,
        "users": [],
        "map": {},
        "stats": {
            "messages": 0,
            "replies": 0
        }
    }

    if DB_PATH.exists():
        try:
            with open(DB_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)

            for k in default:
                data.setdefault(k, default[k])

            data.setdefault("stats", default["stats"])
            data["stats"].setdefault("messages", 0)
            data["stats"].setdefault("replies", 0)

            return data
        except:
            return default

    return default


def save_db(db):
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(DB_PATH, "w", encoding="utf-8") as f:
        json.dump(db, f, indent=2)


# ─────────────────────────────────────────────
# INIT
# ─────────────────────────────────────────────

def init_bot_plugin(bot, owner_id, owner_name):
    global bot_instance, owner_user_id, owner_display_name

    bot_instance = bot
    owner_user_id = owner_id
    owner_display_name = owner_name

    print("✅ Assistant Plugin Loaded (FULL CLEAN VERSION)")


    # ─────────────────────────────────────────
    # START COMMAND
    # ─────────────────────────────────────────
    @bot.on(events.NewMessage(pattern=r"^/start"))
    async def start(event):
        if is_handled(event):
            return

        mark_handled(event)

        db = load_db()

        if event.sender_id == owner_user_id:
            text = (
                "👑 Assistant Panel\n\n"
                "Commands:\n"
                "/assistant on\n"
                "/assistant off\n"
                "/assistant status"
            )
        else:
            text = (
                "👋 Hello!\n\n"
                "Send your message to contact the owner.\n"
                "Powered Assistant Bot."
                if db["assistant_enabled"]
                else "⚠️ Assistant is currently OFF."
            )

        await event.reply(text)


    # ─────────────────────────────────────────
    # ASSISTANT COMMAND
    # ─────────────────────────────────────────
    @bot.on(events.NewMessage(pattern=r"^/assistant(?:\s+(on|off|status))?$"))
    async def assistant_cmd(event):
        if is_handled(event):
            return

        mark_handled(event)

        if event.sender_id != owner_user_id:
            return

        db = load_db()
        arg = event.pattern_match.group(1)

        if not arg:
            await event.reply("Use: /assistant on | off | status")
            return

        arg = arg.lower()

        if arg == "on":
            db["assistant_enabled"] = True
            save_db(db)
            await event.reply("🟢 Assistant Enabled")

        elif arg == "off":
            db["assistant_enabled"] = False
            save_db(db)
            await event.reply("🔴 Assistant Disabled")

        elif arg == "status":
            status = "ON" if db["assistant_enabled"] else "OFF"
            await event.reply(f"Assistant: {status}")


    # ─────────────────────────────────────────
    # USER → OWNER
    # ─────────────────────────────────────────
    @bot.on(events.NewMessage(incoming=True))
    async def user_handler(event):
        if is_handled(event):
            return

        if not event.is_private:
            return

        if event.sender_id == owner_user_id:
            return

        db = load_db()

        if not db["assistant_enabled"]:
            return

        sender = await event.get_sender()
        name = sender.first_name or "Unknown"
        uid = sender.id

        text = event.text or "[Media]"

        msg = (
            "📩 New Message\n\n"
            "👤 {}\n"
            "🆔 {}\n\n"
            "{}"
        ).format(html.escape(name), uid, html.escape(text))

        sent = await bot.send_message(owner_user_id, msg)

        db["map"][str(sent.id)] = uid
        db["stats"]["messages"] += 1
        save_db(db)

        mark_handled(event)

        await event.reply("✅ Sent to owner")


    # ─────────────────────────────────────────
    # OWNER → USER REPLY
    # ─────────────────────────────────────────
    @bot.on(events.NewMessage(from_users=owner_user_id))
    async def owner_reply(event):
        if is_handled(event):
            return

        if not event.is_reply:
            return

        db = load_db()
        reply = await event.get_reply_message()

        if not reply:
            return

        target = db["map"].get(str(reply.id))

        if not target:
            return

        text = event.text or "[Media]"

        await bot.send_message(
            target,
            "💬 {}\n\n{}".format(owner_display_name, html.escape(text))
        )

        db["stats"]["replies"] += 1
        save_db(db)

        mark_handled(event)

        await event.reply("✅ Sent")


    # ─────────────────────────────────────────
    # HELP
    # ─────────────────────────────────────────
    @bot.on(events.NewMessage(pattern=r"^/help$"))
    async def help_cmd(event):
        if is_handled(event):
            return

        mark_handled(event)

        if event.sender_id == owner_user_id:
            text = (
                "/assistant on\n"
                "/assistant off\n"
                "/assistant status"
            )
        else:
            text = "Just send a message to contact the owner."

        await event.reply(text)


    print("🚀 Assistant Ready (No Duplication Mode)")
