# =============================================================================
#  CipherElite Userbot Plugin - Personal Assistant PM Manager
#
#  Plugin Name:    pmpermit
#  Author:         CipherElite Dev (@rishabhops)
#  Repository:     https://github.com/rishabhops/CipherElite
#
#  LICENSE:        MIT
# =============================================================================

import os
import json
import random
import asyncio
import logging
from datetime import datetime
from pathlib import Path

import google.generativeai as genai
from telethon import events
from utils.utils import CipherElite
from utils.decorators import rishabh
from plugins.bot import add_handler
from config.config import Config

# Default PM permit picture
DEFAULT_PMPERMIT_PIC = Config.DEFAULT_PMPERMIT_PIC
LOG_CHAT_ID = Config.LOG_CHAT_ID

# DB setup
PROJECT_ROOT = Path(__file__).parent.parent
DB_DIR = PROJECT_ROOT / "DB"
DB_DIR.mkdir(exist_ok=True)
DB_FILE = DB_DIR / "assistant_db.json"


class PersonalAssistant:
    def __init__(self, ai_config):
        self.ai_config = ai_config
        self.data = {
            "config": {
                "alive_name": os.environ.get("ALIVE_NAME", "Owner"),
                "assistant_name": os.environ.get("ASSISTANT_NAME", "ParadoxAI"),
                "pmpermit_pic": os.environ.get(
                    "PMPERMIT_PIC",
                    DEFAULT_PMPERMIT_PIC
                ),
                "use_pic": True,
                "pmpermit_enabled": True,
            },
            "users": {},
            "approved_users": [],
            "user_states": {},
        }

        self.ai_sessions = {}
        self.model = None

        self._load()
        self._init_ai()

        cfg = self.data["config"]
        if not cfg.get("pmpermit_pic"):
            cfg["pmpermit_pic"] = DEFAULT_PMPERMIT_PIC
            self._save()

    def _init_ai(self):
        api_key = self.ai_config.get_api_key()

        if not api_key:
            self.model = None
            return False

        try:
            genai.configure(api_key=api_key)

            system_instruction = (
                f"You are {self.data['config']['assistant_name']}, a professional "
                f"AI assistant managing the private inbox of "
                f"{self.data['config']['alive_name']}. "
                "The owner is currently unavailable. "
                "Assist incoming contacts professionally. "
                "Let users know their message will be forwarded. "
                "Keep responses polite and under 80 words."
            )

            self.model = genai.GenerativeModel(
                "gemini-2.5-flash",
                system_instruction=system_instruction
            )

            return True

        except Exception as e:
            logging.error(f"AI init failed: {e}")
            self.model = None
            return False

    def _load(self):
        try:
            if DB_FILE.exists():
                with DB_FILE.open("r", encoding="utf-8") as f:
                    on_disk = json.load(f)

                for k, v in on_disk.items():
                    if k in ["users", "user_states"]:
                        self.data[k] = v if isinstance(v, dict) else {}

                    elif k == "approved_users":
                        self.data[k] = v if isinstance(v, list) else []

                    elif k == "config" and isinstance(v, dict):
                        self.data["config"].update(v)

        except Exception as e:
            logging.error(f"Load error: {e}")

    def _save(self):
        try:
            with DB_FILE.open("w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=2, ensure_ascii=False)

        except Exception as e:
            logging.error(f"Save error: {e}")

    async def send_notification(self, event, user_info, message_text):
        try:
            text = (
                f"📨 **New PM from Unapproved User**\n\n"
                f"👤 **Name:** {user_info.get('name', 'Unknown')}\n"
                f"🔗 **Username:** @{user_info.get('username', 'N/A')}\n"
                f"🆔 **User ID:** `{user_info.get('id', 'N/A')}`\n"
                f"⏰ **Time:** `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`\n\n"
                f"💬 **Message:**\n```{message_text[:200]}```"
            )

            await event.client.send_message(LOG_CHAT_ID, text)

        except Exception as e:
            logging.error(f"Notification failed: {e}")

    async def send_message(self, event, mtype, **kwargs):
        try:
            target = await event.get_sender()
        except Exception:
            target = event.chat_id

        cfg = self.data["config"]

        texts = {
            "introduction": [
                f"Good day, **{{first_name}}**.\n\n"
                f"The owner **{cfg['alive_name']}** is currently unavailable.\n\n"
                f"You are connected to **{cfg['assistant_name']}**, "
                f"the inbox assistant.\n\n"
                f"Please send your message and it will be forwarded."
            ],

            "approved": [
                "✅ You have been approved. You may now message directly."
            ],

            "disapproved": [
                "❌ Approval removed."
            ],
        }

        lst = texts.get(mtype, [])

        if not lst:
            return

        msg = random.choice(lst).format(**kwargs)

        try:
            async with event.client.action(target, "typing"):
                await asyncio.sleep(1)
        except Exception:
            pass

        if mtype == "introduction" and cfg.get("use_pic"):
            try:
                await event.client.send_file(
                    target,
                    cfg["pmpermit_pic"],
                    caption=msg
                )
                return
            except Exception:
                pass

        await event.reply(msg)

    async def handle_message(self, event):
        if not event.is_private:
            return

        if not self.data["config"].get("pmpermit_enabled", True):
            return

        sender = await event.get_sender()
        uid = str(sender.id)

        if (
            getattr(sender, "bot", False)
            or getattr(sender, "is_self", False)
            or uid in self.data["approved_users"]
        ):
            return

        msg_text = event.message.text or ""

        # ===========================
        # NEW USER
        # ===========================
        if uid not in self.data["users"]:
            self.data["users"][uid] = {
                "name": sender.first_name,
                "username": sender.username,
                "first_seen": datetime.now().isoformat(),
                "id": uid,
            }

            self.data["user_states"][uid] = "introduced"
            self._save()

            await self.send_message(
                event,
                "introduction",
                first_name=sender.first_name or "there"
            )

            await self.send_notification(
                event,
                self.data["users"][uid],
                msg_text or "[No text]"
            )

            if self.model and msg_text:
                if uid not in self.ai_sessions:
                    self.ai_sessions[uid] = self.model.start_chat(history=[])

                try:
                    async with event.client.action(event.chat_id, "typing"):
                        response = await self.ai_sessions[
                            uid
                        ].send_message_async(msg_text)

                    await event.reply(
                        getattr(
                            response,
                            "text",
                            "Your message has been received."
                        )
                    )

                except Exception as e:
                    logging.error(f"AI first message error: {e}")

            return

        # ===========================
        # RETURNING USER
        # ===========================
        if self.model:
            if uid not in self.ai_sessions:
                self.ai_sessions[uid] = self.model.start_chat(history=[])

            try:
                async with event.client.action(event.chat_id, "typing"):
                    response = await self.ai_sessions[
                        uid
                    ].send_message_async(msg_text or "(no text)")

                await event.reply(
                    getattr(
                        response,
                        "text",
                        "Your message has been forwarded."
                    )
                )

            except Exception as e:
                logging.error(f"AI reply error: {e}")

                await event.reply(
                    "⏳ Assistant unavailable right now. "
                    "Your message has been forwarded."
                )

            await self.send_notification(
                event,
                self.data["users"][uid],
                msg_text or "[No text]"
            )


def init(client):
    try:
        from plugins.ai_setup import ai_config
    except ImportError:
        print("❌ ai_setup.py not found")
        return False

    assistant = PersonalAssistant(ai_config)

    commands = [
        ".a / .approve",
        ".da / .disapprove",
        ".listapproved",
        ".setpermitpic",
        ".togglepermitpic",
        ".pmpermit on|off",
    ]

    add_handler("pmpermit", commands, "Personal Assistant PM Manager")

    @CipherElite.on(events.NewMessage(incoming=True))
    async def _incoming(event):
        await assistant.handle_message(event)

    @CipherElite.on(
        events.NewMessage(
            outgoing=True,
            pattern=r"\.(?:a|approve)(?:$|\s)"
        )
    )
    @rishabh()
    async def _approve(event):
        uid = str(event.chat_id)

        if uid not in assistant.data["approved_users"]:
            assistant.data["approved_users"].append(uid)

        assistant._save()
        await assistant.send_message(event, "approved")

    @CipherElite.on(
        events.NewMessage(
            outgoing=True,
            pattern=r"\.(?:da|disapprove)(?:$|\s)"
        )
    )
    @rishabh()
    async def _disapprove(event):
        uid = str(event.chat_id)

        assistant.data["approved_users"] = [
            u for u in assistant.data["approved_users"]
            if u != uid
        ]

        assistant.ai_sessions.pop(uid, None)
        assistant._save()

        await assistant.send_message(event, "disapproved")

    @CipherElite.on(
        events.NewMessage(
            outgoing=True,
            pattern=r"\.listapproved$"
        )
    )
    @rishabh()
    async def _list(event):
        approved = assistant.data["approved_users"]

        if not approved:
            return await event.reply("No approved users.")

        text = "**Approved Users:**\n"

        for uid in approved:
            info = assistant.data["users"].get(uid, {})
            name = info.get("name", "Unknown")
            text += f"• {name} (`{uid}`)\n"

        await event.reply(text)

    @CipherElite.on(
        events.NewMessage(
            outgoing=True,
            pattern=r"\.togglepermitpic$"
        )
    )
    @rishabh()
    async def _toggle(event):
        cfg = assistant.data["config"]

        cfg["use_pic"] = not cfg.get("use_pic", True)

        assistant._save()

        state = "enabled" if cfg["use_pic"] else "disabled"

        await event.reply(f"Permit picture {state}")

    @CipherElite.on(
        events.NewMessage(
            outgoing=True,
            pattern=r"\.pmpermit(?:\s+(on|off))?$"
        )
    )
    @rishabh()
    async def _pmpermit(event):
        arg = (event.pattern_match.group(1) or "").lower()

        cfg = assistant.data["config"]

        if arg in ("on", "off"):
            cfg["pmpermit_enabled"] = arg == "on"
            assistant._save()

            state = "enabled ✅" if cfg["pmpermit_enabled"] else "disabled 🚫"
            return await event.reply(f"PM permit {state}")

        state = "ON ✅" if cfg["pmpermit_enabled"] else "OFF 🚫"

        await event.reply(
            f"PM permit is {state}\n"
            f"Use `.pmpermit on` or `.pmpermit off`"
        )

    print("✅ PM Permit Plugin Loaded")
    return assistant
