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
        self.ai_config = ai_config  # Reference to centralized config
        self.data = {
            "config": {
                "alive_name": os.environ.get("ALIVE_NAME", "Owner"),
                "assistant_name": os.environ.get("ASSISTANT_NAME", "ParadoxAI"),
                "pmpermit_pic": os.environ.get("PMPERMIT_PIC", DEFAULT_PMPERMIT_PIC),
                "use_pic": True,
                "pmpermit_enabled": True,
            },
            "users": {},
            "approved_users": [],
            "user_states": {},
            "warnings": {},  # Fix: was missing, caused KeyError on first new PM
        }
        self.ai_sessions = {}
        self.model = None

        # 1. Load and safely validate data from JSON
        self._load()

        # 2. Attempt to boot up the AI
        self._init_ai()

        # Ensure default pic exists
        cfg = self.data["config"]
        if not cfg.get("pmpermit_pic"):
            cfg["pmpermit_pic"] = DEFAULT_PMPERMIT_PIC
            self._save()

    def _init_ai(self):
        """Initializes the Gemini model using centralized config."""
        api_key = self.ai_config.get_api_key()  # Get from centralized config
        if not api_key:
            self.model = None
            return False

        try:
            genai.configure(api_key=api_key)
            system_instruction = (
                f"You are {self.data['config']['assistant_name']}, a professional AI assistant managing "
                f"the private inbox of {self.data['config']['alive_name']}. "
                "The owner is currently unavailable. Your role is to assist incoming contacts "
                "professionally and ensure their queries are noted for the owner's review. "
                "Greet users warmly, assist with their queries where possible, and let them know "
                "their message will be forwarded to the owner. "
                "If asked when the owner will be available, state that the exact time cannot be "
                "confirmed but their message will be forwarded promptly. "
                "Maintain a professional, courteous tone at all times. Keep responses under 80 words."
            )
            self.model = genai.GenerativeModel(
                "gemini-2.5-flash",
                system_instruction=system_instruction,
            )
            return True
        except Exception as e:
            logging.error(f"Failed to initialize AI Gatekeeper: {e}")
            self.model = None
            return False

    def _load(self):
        """Loads DB and strictly enforces data types to prevent crashes."""
        try:
            if DB_FILE.exists():
                with DB_FILE.open("r", encoding="utf-8") as f:
                    on_disk = json.load(f)
                for k, v in on_disk.items():
                    # Force these to ALWAYS be dictionaries
                    if k in ["users", "warnings", "user_states"]:
                        self.data[k] = v if isinstance(v, dict) else {}
                    # Force approved users to ALWAYS be a list
                    elif k == "approved_users":
                        self.data[k] = v if isinstance(v, list) else []
                    # Safely update config without overwriting
                    elif k == "config" and isinstance(v, dict):
                        self.data["config"].update(v)
                    else:
                        self.data[k] = v
        except Exception as e:
            logging.error(f"Assistant load error: {e}")

    def _save(self):
        try:
            with DB_FILE.open("w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logging.error(f"Assistant save error: {e}")

    async def send_notification(self, event, user_info, message_text):
        """Send notification to log group about new PM."""
        try:
            notification_text = (
                f"📨 **New PM from Unapproved User**\n\n"
                f"👤 **Name:** {user_info.get('name', 'Unknown')}\n"
                f"🔗 **Username:** @{user_info.get('username', 'N/A')}\n"
                f"🆔 **User ID:** `{user_info.get('id', 'N/A')}`\n"
                f"⏰ **Time:** `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`\n\n"
                f"💬 **Message:**\n```\n{message_text[:200]}\n```\n\n"
                f"📌 **Quick Actions:**\n"
                f"→ Reply `.a` to approve\n"
                f"→ Reply `.da` to disapprove\n"
                f"→ Reply `.block` to block"
            )
            await event.client.send_message(LOG_CHAT_ID, notification_text)
        except Exception as e:
            logging.error(f"Failed to send notification: {e}")

    async def send_message(self, event, mtype, **kwargs):
        """Fallback non-AI messaging system."""
        try:
            target = await event.get_sender()
        except Exception:
            target = event.chat_id

        cfg = self.data["config"]
        texts = {
            "introduction": [
                f"Good day, **{{first_name}}**. The owner, **{cfg['alive_name']}**, is currently unavailable.\n\n"
                f"You are now connected to **{cfg['assistant_name']}**, a dedicated AI assistant "
                f"managing this inbox. Please feel free to share your query and you will be "
                f"assisted promptly.\n\n"
                f"Your message will also be forwarded to the owner for their attention."
            ],
            "approved": [
                "✅ You have been approved. You may now communicate directly. Welcome."
            ],
            "disapproved": [
                "❌ Your access has been revoked by the owner."
            ],
        }

        lst = texts.get(mtype, [])
        if not lst:
            return

        msg = random.choice(lst).format(**kwargs)

        try:
            async with event.client.action(target, "typing"):
                await asyncio.sleep(1.0)
        except Exception:
            pass

        if mtype == "introduction" and cfg.get("use_pic"):
            try:
                await event.client.send_file(target, cfg["pmpermit_pic"], caption=msg)
            except Exception:
                await event.reply(msg)
        else:
            await event.reply(msg)

    async def handle_message(self, event):
        if not event.is_private:
            return

        if not self.data["config"].get("pmpermit_enabled", True):
            return

        sender = await event.get_sender()
        uid = str(sender.id)

        # Ignore bots, yourself, and approved users
        if sender.bot or sender.is_self or uid in self.data["approved_users"]:
            return

        msg_text = event.message.text or ""

        # ── 1) First contact ──────────────────────────────────────────────────
        if uid not in self.data["users"]:
            self.data["users"][uid] = {
                "name": sender.first_name,
                "username": sender.username,
                "first_seen": datetime.now().isoformat(),
                "id": uid,
            }
            self.data["user_states"][uid] = "introduced"
            self.data["warnings"].setdefault(uid, 0)
            self._save()

            # Always send the formal introduction (with the user's first name)
            await self.send_message(event, "introduction", first_name=sender.first_name or "there")
            await self.send_notification(event, self.data["users"][uid], msg_text or "[No text]")

            # If AI is ready, immediately respond to their first message too
            if self.model and msg_text:
                if uid not in self.ai_sessions:
                    self.ai_sessions[uid] = self.model.start_chat(history=[])
                try:
                    async with event.client.action(event.chat_id, "typing"):
                        response = await self.ai_sessions[uid].send_message_async(msg_text)
                    await event.reply(response.text)
                except Exception as e:
                    logging.error(f"AI Error (first contact): {e}")
            return

        # ── 2) Returning unapproved user — AI handles everything ──────────────
        if self.model:
            if uid not in self.ai_sessions:
                self.ai_sessions[uid] = self.model.start_chat(history=[])
            try:
                async with event.client.action(event.chat_id, "typing"):
                    response = await self.ai_sessions[uid].send_message_async(
                        msg_text or "(no text)"
                    )
                await event.reply(response.text)
                await self.send_notification(event, self.data["users"][uid], msg_text or "[No text]")
            except Exception as e:
                logging.error(f"AI Error: {e}")
                await event.reply(
                    "⏳ Apologies, the assistant is momentarily unavailable. "
                    "Your message has been forwarded to the owner."
                )
                await self.send_notification(event, self.data["users"][uid], msg_text or "[No text]")
            return


def init(client):
    try:
        from plugins.ai_setup import ai_config  # Import centralized config
    except ImportError:
        print("❌ ERROR: ai_setup.py not found! Please create it first.")
        return False

    assistant = PersonalAssistant(ai_config)  # Pass config to assistant
    commands = [
        ".a / .approve        — Approve a user (AI stops, direct chat begins)",
        ".da / .disapprove    — Revoke approval (AI resumes)",
        ".listapproved        — List approved users",
        ".setpermitpic        — Set the permit picture",
        ".togglepermitpic     — Enable/disable the picture",
        ".pmpermit on|off     — Enable/disable PM permit globally",
    ]
    add_handler("pmpermit", commands, "Personal Assistant PM Manager")

    @CipherElite.on(events.NewMessage(incoming=True))
    async def _incoming(event):
        await assistant.handle_message(event)

    @CipherElite.on(events.NewMessage(outgoing=True, pattern=r"\.(?:a|approve)(?:$|\s)"))
    @rishabh()
    async def _approve(event):
        if event.is_private:
            uid = str(event.chat_id)
        else:
            reply = await event.get_reply_message()
            if not reply:
                return await event.reply("↪️ Reply to the user to approve.")
            uid = str(reply.sender_id)

        if uid not in assistant.data["approved_users"]:
            assistant.data["approved_users"].append(uid)
        assistant._save()
        await assistant.send_message(event, "approved")

    @CipherElite.on(events.NewMessage(outgoing=True, pattern=r"\.(?:da|disapprove)(?:$|\s)"))
    @rishabh()
    async def _disapprove(event):
        if event.is_private:
            uid = str(event.chat_id)
        else:
            reply = await event.get_reply_message()
            if not reply:
                return await event.reply("↪️ Reply to the user to disapprove.")
            uid = str(reply.sender_id)

        assistant.data["approved_users"] = [u for u in assistant.data["approved_users"] if u != uid]
        # Clear AI session so conversation starts fresh when AI resumes
        assistant.ai_sessions.pop(uid, None)
        assistant._save()
        await assistant.send_message(event, "disapproved")

    @CipherElite.on(events.NewMessage(outgoing=True, pattern=r"\.listapproved$"))
    @rishabh()
    async def _list(event):
        approved = assistant.data["approved_users"]
        if not approved:
            return await event.reply("No users are approved.")
        text = "**Approved Users:**\n"
        for uid in approved:
            info = assistant.data["users"].get(uid, {})
            name = info.get("name", "Unknown")
            text += f"• {name} (`{uid}`)\n"
        await event.reply(text)

    @CipherElite.on(events.NewMessage(outgoing=True, pattern=r"\.setpermitpic(?:\s+.*)?$"))
    @rishabh()
    async def _setpic(event):
        if event.reply_to_msg_id:
            msg = await event.get_reply_message()
            if msg.media:
                path = await CipherElite.download_media(msg)
                assistant.data["config"]["pmpermit_pic"] = path
                assistant.data["config"]["use_pic"] = True
                assistant._save()
                return await event.reply("✅ Permit picture set from reply")
            return await event.reply("❌ Reply to an image.")
        parts = event.text.split(None, 1)
        if len(parts) > 1:
            assistant.data["config"]["pmpermit_pic"] = parts[1].strip()
            assistant.data["config"]["use_pic"] = True
            assistant._save()
            return await event.reply("✅ Permit picture set from URL")
        await event.reply("❌ Usage: .setpermitpic <url> or reply to an image")

    @CipherElite.on(events.NewMessage(outgoing=True, pattern=r"\.togglepermitpic$"))
    @rishabh()
    async def _togglepic(event):
        cfg = assistant.data["config"]
        cfg["use_pic"] = not cfg.get("use_pic", True)
        assistant._save()
        state = "enabled" if cfg["use_pic"] else "disabled"
        await event.reply(f"✅ Permit picture {state}")

    # NEW: global pmpermit toggle
    @CipherElite.on(events.NewMessage(outgoing=True, pattern=r"\.pmpermit(?:$|\s)(on|off)?"))
    @rishabh()
    async def _toggle_pmpermit(event):
        arg = (event.pattern_match.group(1) or "").lower()
        cfg = assistant.data["config"]

        if arg in ("on", "off"):
            cfg["pmpermit_enabled"] = arg == "on"
            assistant._save()
            state = "enabled ✅" if cfg["pmpermit_enabled"] else "disabled 🚫"
            return await event.reply(f"PM permit is now {state}")

        state = "ON ✅" if cfg.get("pmpermit_enabled", True) else "OFF 🚫"
        await event.reply(f"PM permit is currently {state}\nUsage: `.pmpermit on` or `.pmpermit off`")


    print(
        f"✅ PM Permit Plugin initialized (pmpermit_enabled={assistant.data['config'].get('pmpermit_enabled', True)})"
    )
    return assistant
