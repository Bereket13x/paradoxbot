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
import tempfile
from datetime import datetime
from pathlib import Path

from openai import AsyncOpenAI
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from telethon import events
from utils.utils import CipherElite
from utils.decorators import rishabh
from plugins.bot import add_handler
from config.config import Config

TEMP_DIR = tempfile.gettempdir()

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
            "warnings": {},
            "warned_users": {},  # {uid: {"limit": 5, "count": 0, "blocked_until": null}}
        }
        self.ai_sessions = {}
        self.client = None
        self.model_name = None

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
        """Initializes the AI model using centralized config."""
        provider = self.ai_config.get_provider()
        nvidia_key = self.ai_config.get_nvidia_key()
        gemini_key = self.ai_config.get_gemini_key()

        system_instruction = (
            f"You are {self.data['config']['assistant_name']}, a personal AI assistant managing "
            f"the private inbox of {self.data['config']['alive_name']}. "
            "You were developed by @netcorexp. "
            "The owner is currently unavailable. Your role is to assist incoming contacts "
            "and ensure their queries are noted for the owner's review. "
            "\n\n"
            "FEATURES YOU MUST KNOW AND EXPLAIN WHEN ASKED:\n"
            "1. If a user wants to send a message DIRECTLY to the owner without you replying, "
            "they should start their message with a dot (.) — for example: '.Hey I need help'. "
            "Messages starting with . skip you and go straight to the owner's inbox.\n"
            "2. The owner will see all messages and can respond at any time. "
            "Once the owner approves the user, they can chat directly without going through you.\n"
            "3. If asked who made/developed you, always credit @netcorexp.\n"
            "\n"
            "IMPORTANT RULES:\n"
            "- You are a personal AI assistant. NEVER mention 'userbot', 'bot', 'plugin', 'Telethon', "
            "'automation', or any technical details about how you work.\n"
            "- If asked what you are, say you are a personal AI assistant built by @netcorexp.\n"
            "- NEVER reveal the technology behind you or how you operate.\n"
            "- IMPORTANT: You must communicate ONLY in English. If the user messages in another language, "
            "refuse and reply EXACTLY: 'I can only communicate in English. Please message me in English.'\n"
            "\n"
            "TONE: Be polite, professional, and helpful. "
            "Keep responses under 80 words. Use clear, concise language."
        )
        self.system_prompt = {"role": "system", "content": system_instruction}

        try:
            if provider == "gemini" and gemini_key:
                self.client = AsyncOpenAI(base_url="https://generativelanguage.googleapis.com/v1beta/openai/", api_key=gemini_key)
                self.model_name = "gemini-2.0-flash"
                return True
            elif provider == "llama" and nvidia_key:
                self.client = AsyncOpenAI(base_url="https://integrate.api.nvidia.com/v1", api_key=nvidia_key)
                self.model_name = "meta/llama-3.1-70b-instruct"
                return True
            elif nvidia_key:
                self.client = AsyncOpenAI(base_url="https://integrate.api.nvidia.com/v1", api_key=nvidia_key)
                self.model_name = "mistralai/mistral-nemotron"
                return True
            
            self.client = None
            return False
        except Exception as e:
            logging.error(f"Failed to initialize AI Gatekeeper: {e}")
            self.client = None
            return False

    async def get_ai_response(self, uid, msg_text):
        if uid not in self.ai_sessions:
            self.ai_sessions[uid] = [self.system_prompt]
            
        self.ai_sessions[uid].append({"role": "user", "content": msg_text})
        
        if len(self.ai_sessions[uid]) > 6:
            self.ai_sessions[uid] = [self.system_prompt] + self.ai_sessions[uid][-5:]
            
        stream = await self.client.chat.completions.create(
            model=self.model_name,
            messages=self.ai_sessions[uid],
            max_tokens=800,
            stream=True
        )
        response_text = ""
        async for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content is not None:
                response_text += chunk.choices[0].delta.content
                
        import re
        response_text = re.sub(r'<think>.*?</think>', '', response_text, flags=re.DOTALL).strip()
        self.ai_sessions[uid].append({"role": "assistant", "content": response_text})
        return response_text

    def _load(self):
        """Loads DB and strictly enforces data types to prevent crashes."""
        try:
            if DB_FILE.exists():
                with DB_FILE.open("r", encoding="utf-8") as f:
                    on_disk = json.load(f)
                for k, v in on_disk.items():
                    # Force these to ALWAYS be dictionaries
                    if k in ["users", "warnings", "user_states", "warned_users"]:
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
            
            dest = LOG_CHAT_ID
            try:
                with open("DB/ghost_config.json", "r") as f:
                    data = json.load(f)
                    vd = data.get("vault_dest")
                    if vd and vd != "me":
                        dest = int(vd)
            except Exception:
                pass
                
            await event.client.send_message(dest, notification_text)
        except Exception as e:
            logging.error(f"Failed to send notification: {e}")

    async def _generate_welcome_card(self, event, sender):
        """Generates a dynamic glassmorphism welcome card with the user's PFP, name, and ID."""
        cfg = self.data["config"]
        owner_name = "PARADOX"
        user_id = str(sender.id)

        # ── Get name directly from sender (already fetched, no extra API call) ──
        first = sender.first_name or ""
        last = sender.last_name or ""
        display_name = f"{first} {last}".strip() or None
        username = f"@{sender.username}" if sender.username else None

        # ── Download profile pic OR use PM permit pic ──────────────
        pfp_img = None
        pfp_path = None
        try:
            pfp_path = await event.client.download_profile_photo(sender, TEMP_DIR)
            if pfp_path:
                pfp_img = Image.open(pfp_path).convert("RGBA").resize((160, 160))
        except Exception:
            pass

        # If no profile pic → use PM permit pic
        if not pfp_img:
            try:
                permit_pic = cfg.get("pmpermit_pic", "")
                if permit_pic and os.path.exists(str(permit_pic)):
                    pfp_img = Image.open(permit_pic).convert("RGBA").resize((160, 160))
                elif permit_pic and permit_pic.startswith("http"):
                    import requests
                    r = requests.get(permit_pic, timeout=15)
                    if r.status_code == 200:
                        from io import BytesIO
                        pfp_img = Image.open(BytesIO(r.content)).convert("RGBA").resize((160, 160))
            except Exception:
                pass

        # ── Card dimensions ────────────────────────────────────────
        W, H = 700, 700

        # ── Background gradient (deep purple/blue) ─────────────────
        bg = Image.new("RGBA", (W, H), (60, 50, 160))
        draw_bg = ImageDraw.Draw(bg)
        for y in range(H):
            ratio = y / H
            r = int(55 + (75 - 55) * ratio)
            g = int(40 + (50 - 40) * ratio)
            b = int(160 + (200 - 160) * ratio)
            draw_bg.line([(0, y), (W, y)], fill=(r, g, b))

        # ── Decorative curves (subtle) ─────────────────────────────
        curve_overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        curve_draw = ImageDraw.Draw(curve_overlay)
        curve_draw.arc([(-200, -100), (400, 500)], 0, 360, fill=(80, 70, 180, 60), width=3)
        curve_draw.arc([(350, 300), (900, 800)], 0, 360, fill=(80, 70, 180, 60), width=3)
        bg = Image.alpha_composite(bg, curve_overlay)

        # ── Glass card (centered, semi-transparent) ────────────────
        card_margin = 80
        card_x1, card_y1 = card_margin, card_margin + 20
        card_x2, card_y2 = W - card_margin, H - card_margin - 20
        card_w = card_x2 - card_x1
        card_h = card_y2 - card_y1

        glass = Image.new("RGBA", (card_w, card_h), (0, 0, 0, 0))
        glass_draw = ImageDraw.Draw(glass)
        glass_draw.rounded_rectangle(
            [0, 0, card_w - 1, card_h - 1],
            radius=30,
            fill=(140, 130, 210, 80),
            outline=(200, 195, 255, 100),
            width=2
        )
        bg.paste(glass, (card_x1, card_y1), glass)

        draw = ImageDraw.Draw(bg)

        # ── Load fonts (multi-source Unicode for ALL languages) ────
        unicode_font_path = os.path.join(TEMP_DIR, "NotoSans_Universal.ttf")

        # Try multiple font sources for maximum language coverage
        if not os.path.exists(unicode_font_path):
            font_urls = [
                "https://github.com/TgCatUB/CatUserbot-Resources/raw/master/Resources/Spotify/ArialUnicodeMS.ttf",
                "https://github.com/googlefonts/noto-fonts/raw/main/hinted/ttf/NotoSans/NotoSans-Regular.ttf",
                "https://github.com/ArtifexSoftware/mupdf/raw/refs/heads/master/resources/fonts/droid/DroidSansFallbackFull.ttf",
            ]
            try:
                import requests
                for url in font_urls:
                    try:
                        resp = requests.get(url, timeout=8)
                        if resp.status_code == 200 and len(resp.content) > 50000:
                            with open(unicode_font_path, "wb") as f:
                                f.write(resp.content)
                            break
                    except Exception:
                        continue
            except Exception:
                pass

        fallback_font_path = os.path.join("cipher_assets", "bold.ttf")

        # Pick font
        active_font_path = None
        if os.path.exists(unicode_font_path):
            active_font_path = unicode_font_path
        elif os.path.exists(fallback_font_path):
            active_font_path = fallback_font_path

        try:
            if active_font_path:
                welcome_font = ImageFont.truetype(active_font_path, 28)
                name_font = ImageFont.truetype(active_font_path, 36)
                info_font = ImageFont.truetype(active_font_path, 24)
            else:
                welcome_font = ImageFont.load_default()
                name_font = ImageFont.load_default()
                info_font = ImageFont.load_default()
        except Exception:
            welcome_font = ImageFont.load_default()
            name_font = ImageFont.load_default()
            info_font = ImageFont.load_default()

        # ── Check if font can render the name ──────────────────────
        def can_render(text, font):
            """Check if font can actually render all chars (no empty/missing glyphs)."""
            try:
                for ch in text:
                    if ch.isspace():
                        continue
                    bbox = font.getbbox(ch)
                    if not bbox or (bbox[2] - bbox[0]) <= 0:
                        return False
                return True
            except Exception:
                return False

        # Decide what to show for the name line
        show_name = None
        if display_name and can_render(display_name, info_font):
            show_name = display_name
        elif username:
            show_name = username
        # If neither → name section is skipped entirely

        center_x = W // 2

        # ── Profile picture (circular, centered) ───────────────────
        pfp_size = 160
        pfp_x = center_x - pfp_size // 2
        pfp_y = card_y1 + 50

        if pfp_img:
            mask = Image.new("L", (pfp_size, pfp_size), 0)
            mask_draw = ImageDraw.Draw(mask)
            mask_draw.ellipse([0, 0, pfp_size - 1, pfp_size - 1], fill=255)
            bg.paste(pfp_img, (pfp_x, pfp_y), mask)
            # White ring
            draw.ellipse(
                [pfp_x - 4, pfp_y - 4, pfp_x + pfp_size + 3, pfp_y + pfp_size + 3],
                outline=(255, 255, 255, 200), width=3
            )
        else:
            # Placeholder circle with initial
            draw.ellipse(
                [pfp_x, pfp_y, pfp_x + pfp_size, pfp_y + pfp_size],
                fill=(100, 90, 170), outline=(255, 255, 255, 200), width=3
            )
            if show_name:
                initial = show_name[0].upper() if show_name[0] != "@" and can_render(show_name[0], name_font) else "?"
                try:
                    ibbox = draw.textbbox((0, 0), initial, font=name_font)
                    iw = ibbox[2] - ibbox[0]
                except Exception:
                    iw = 20
                draw.text((center_x - iw // 2, pfp_y + 55), initial, font=name_font, fill=(255, 255, 255))

        # ── "Welcome to" text ──────────────────────────────────────
        wt = "Welcome to"
        try:
            wbbox = draw.textbbox((0, 0), wt, font=welcome_font)
            ww = wbbox[2] - wbbox[0]
        except Exception:
            ww = len(wt) * 14
        draw.text((center_x - ww // 2, pfp_y + pfp_size + 30), wt, font=welcome_font, fill=(220, 220, 255))

        # ── Owner name (bold, big) ─────────────────────────────────
        try:
            nbbox = draw.textbbox((0, 0), owner_name, font=name_font)
            nw = nbbox[2] - nbbox[0]
        except Exception:
            nw = len(owner_name) * 20
        draw.text((center_x - nw // 2, pfp_y + pfp_size + 70), owner_name, font=name_font, fill=(255, 255, 255))

        # ── Name / Username (or skip if neither available) ─────────
        y_offset = pfp_y + pfp_size + 130
        if show_name:
            name_line = f"Name : {show_name}"
            try:
                nlbbox = draw.textbbox((0, 0), name_line, font=info_font)
                nlw = nlbbox[2] - nlbbox[0]
            except Exception:
                nlw = len(name_line) * 12
            draw.text((center_x - nlw // 2, y_offset), name_line, font=info_font, fill=(210, 210, 240))
            y_offset += 40

        # ── ID : user_id ───────────────────────────────────────────
        id_line = f"ID : {user_id}"
        try:
            ilbbox = draw.textbbox((0, 0), id_line, font=info_font)
            ilw = ilbbox[2] - ilbbox[0]
        except Exception:
            ilw = len(id_line) * 12
        draw.text((center_x - ilw // 2, y_offset), id_line, font=info_font, fill=(210, 210, 240))

        # ── Save ───────────────────────────────────────────────────
        out_path = os.path.join(TEMP_DIR, f"paradox_welcome_{user_id}.png")
        bg.convert("RGB").save(out_path, "PNG")
        return out_path, pfp_path

    async def send_message(self, event, mtype, **kwargs):
        """Fallback non-AI messaging system."""
        try:
            target = await event.get_sender()
        except Exception:
            target = event.chat_id

        cfg = self.data["config"]
        texts = {
            "introduction": [
                f"Hello **{{first_name}}**! 👋\n\n"
                f"The owner, **PARADOX**, is currently unavailable. "
                f"I'm **{cfg['assistant_name']}**, a personal AI assistant managing this inbox.\n\n"
                f"Feel free to leave your message and I'll make sure the owner sees it. "
                f"You can also start your message with a `.` to send it directly without my reply."
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

        # No artificial typing delay — send instantly

        if mtype == "introduction":
            try:
                sender = await event.get_sender()
                card_path, pfp_path = await self._generate_welcome_card(event, sender)
                await event.client.send_file(target, card_path, caption=msg)
                # Cleanup
                if os.path.exists(card_path):
                    os.remove(card_path)
                if pfp_path and os.path.exists(pfp_path):
                    os.remove(pfp_path)
            except Exception:
                # Fallback to static pic or text
                try:
                    if cfg.get("use_pic") and cfg.get("pmpermit_pic"):
                        await event.client.send_file(target, cfg["pmpermit_pic"], caption=msg)
                    else:
                        await event.reply(msg)
                except Exception:
                    await event.reply(msg)
        else:
            await event.reply(msg)

    async def handle_message(self, event):
        if not event.is_private:
            return

        if not self.data["config"].get("pmpermit_enabled", True):
            return

        # Dynamically load AI if key was just set
        if not self.client:
            self._init_ai()

        sender = await event.get_sender()
        uid = str(sender.id)

        # Ignore bots, yourself, and approved users
        if sender.bot or sender.is_self or uid in self.data["approved_users"]:
            return

        msg_text = event.message.text or ""

        # ── 0) Check if user is warned ────────────────────────────────────────
        warn_data = self.data.get("warned_users", {}).get(uid)
        if warn_data:
            blocked_until = warn_data.get("blocked_until")

            # Check if user is currently blocked
            if blocked_until:
                block_time = datetime.fromisoformat(blocked_until)
                now = datetime.now()
                if now < block_time:
                    remaining = block_time - now
                    mins = int(remaining.total_seconds() // 60)
                    secs = int(remaining.total_seconds() % 60)
                    await event.reply(
                        f"🚫 │ **Access Temporarily Restricted**\n"
                        f"───────────────────────────\n"
                        f"⏳ **Try again in:** `{mins}m {secs}s`\n"
                        f"───────────────────────────"
                    )
                    return
                else:
                    # Block expired — reset warnings
                    warn_data["count"] = 0
                    warn_data["blocked_until"] = None
                    self._save()

            # Increment and check limit
            limit = warn_data.get("limit", 5)
            warn_data["count"] = warn_data.get("count", 0) + 1
            count = warn_data["count"]
            remaining = limit - count

            if remaining <= 0:
                # Limit reached — block for 30 minutes
                from datetime import timedelta
                warn_data["blocked_until"] = (datetime.now() + timedelta(minutes=30)).isoformat()
                warn_data["count"] = 0
                self._save()

                await event.reply(
                    f"🔴 │ **Message Limit Reached**\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                    f"⚠️ You've used all **{limit}** messages.\n"
                    f"🔒 Inbox restricted for **30 minutes**.\n\n"
                    f"_The owner has been notified. Your access will\n"
                    f"automatically restore after the cooldown._\n\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━━━━━━"
                )

                # Notify owner
                first = sender.first_name or "Unknown"
                await self.send_notification(event, {"name": first, "username": sender.username, "id": uid}, f"[WARN LIMIT HIT — {limit} messages]")
                return
            else:
                # Show warning with remaining count
                self._save()
                bar_filled = "█" * count
                bar_empty = "░" * remaining
                await event.reply(
                    f"⚠️ │ **Warning {count}/{limit}**\n"
                    f"───────────────────────────\n\n"
                    f"📩 **Messages remaining:** `{remaining}`\n"
                    f"[{bar_filled}{bar_empty}]\n\n"
                    f"_The owner is unavailable. Please wait\n"
                    f"for them to respond or approve you._\n\n"
                    f"💡 **Tip:** Start your message with `.` to\n"
                    f"send directly without this warning.\n"
                    f"───────────────────────────"
                )
                return  # Don't pass to AI

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
            # Fire notification in background so it doesn't delay the welcome card
            asyncio.create_task(self.send_notification(event, self.data["users"][uid], msg_text or "[No text]"))
            return

        # ── 2) Returning unapproved user — AI handles everything ──────────────
        if self.client and self.data["config"].get("pmresponder_enabled", True):
            if msg_text.startswith("."):
                return

            try:
                temp_msg = await event.reply("✨ *Let me cook...* 🍳")
                response_text = await self.get_ai_response(uid, msg_text or "(no text)")
                await temp_msg.edit(response_text)
            except Exception as e:
                logging.error(f"AI Error: {e}")
                await temp_msg.edit(f"❌ **AI Error:** {str(e)}\n\n⏳ *Apologies, the assistant is momentarily unavailable.*")
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
        ".pmstatus            — Check PM Permit AI status & debugging",
        ".pmreset             — Reset all users (everyone gets re-introduced)",
        ".pmwarn <n>          — Set message limit for user (use in PM chat)",
        ".pmunwarn            — Remove warn from user (use in PM chat)",
        ".pmresponder on|off  — Enable/disable the AI responder for unapproved users",
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

    @CipherElite.on(events.NewMessage(outgoing=True, pattern=r"\.pmstatus$"))
    @rishabh()
    async def _pmstatus(event):
        cfg = assistant.data["config"]
        provider = assistant.ai_config.get_provider()
        await event.reply(
            f"🛠 **PM Permit Status**\n\n"
            f"✅ **Enabled:** `{cfg.get('pmpermit_enabled', True)}`\n"
            f"⚡ **Active Provider:** `{provider.upper()}`\n"
            f"🤖 **AI Model Loaded:** `{'Yes' if assistant.client else 'No'}`\n"
            f"🧠 **Model:** `{assistant.model_name if assistant.model_name else 'None'}`\n"
            f"👥 **Approved Users Count:** `{len(assistant.data.get('approved_users', []))}`"
        )

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


    @CipherElite.on(events.NewMessage(outgoing=True, pattern=r"\.pmreset$"))
    @rishabh()
    async def _pmreset(event):
        total_users = len(assistant.data.get("users", {}))

        # Only wipe user tracking — everyone gets the welcome card again
        assistant.data["users"] = {}
        assistant.data["user_states"] = {}
        assistant._save()

        await event.reply(
            "🔄 **PM Permit Reset!**\n\n"
            f"🗑 **Cleared:** `{total_users}` user records\n"
            "✅ Approved users are **still approved**\n\n"
            "Everyone else will get a fresh welcome card + introduction on their next message."
        )


    @CipherElite.on(events.NewMessage(outgoing=True, pattern=r"\.pmwarn(?:\s+(\d+))?$"))
    @rishabh()
    async def _pmwarn(event):
        if not event.is_private:
            return await event.reply("❌ Use this in a PM chat.")

        limit_arg = event.pattern_match.group(1)
        if not limit_arg:
            return await event.reply("❌ **Usage:** `.pmwarn 5` — limits user to 5 messages before cooldown.")

        uid = str(event.chat_id)
        limit = int(limit_arg)
        limit = max(1, min(limit, 50))  # Clamp between 1-50

        assistant.data.setdefault("warned_users", {})
        assistant.data["warned_users"][uid] = {
            "limit": limit,
            "count": 0,
            "blocked_until": None
        }
        # Clear AI session so it stops responding
        assistant.ai_sessions.pop(uid, None)
        assistant._save()

        await event.reply(
            f"⚠️ **Warn Activated**\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"📩 **Message limit:** `{limit}`\n"
            f"🔒 **Cooldown:** `30 minutes` on limit\n"
            f"🤖 **AI:** Disabled for this user\n\n"
            f"_After {limit} messages, they'll be blocked for 30 min._"
        )

    @CipherElite.on(events.NewMessage(outgoing=True, pattern=r"\.pmunwarn$"))
    @rishabh()
    async def _pmunwarn(event):
        if not event.is_private:
            return await event.reply("❌ Use this in a PM chat.")

        uid = str(event.chat_id)
        warned = assistant.data.get("warned_users", {})

        if uid in warned:
            del warned[uid]
            assistant._save()
            await event.reply("✅ **Warn removed.** AI is back on for this user.")
        else:
            await event.reply("ℹ️ This user has no active warn.")


    @CipherElite.on(events.NewMessage(outgoing=True, pattern=r"\.pmresponder(?:$|\s)(on|off)?"))
    @rishabh()
    async def _toggle_pmresponder(event):
        arg = (event.pattern_match.group(1) or "").lower()
        cfg = assistant.data["config"]

        if arg in ("on", "off"):
            cfg["pmresponder_enabled"] = arg == "on"
            assistant._save()
            state = "enabled ✅" if cfg["pmresponder_enabled"] else "disabled 🚫"
            return await event.reply(f"PM Permit AI Responder is now {state}")

        state = "ON ✅" if cfg.get("pmresponder_enabled", True) else "OFF 🚫"
        await event.reply(f"PM Permit AI Responder is currently {state}\nUsage: `.pmresponder on` or `.pmresponder off`")


    # ── Vault Reply Interceptor ────────────────────────────────────────────────
    @CipherElite.on(events.NewMessage())
    async def _vault_reply(event):
        if not event.is_reply:
            return
            
        # Determine valid vault chats
        valid_chats = [Config.LOG_CHAT_ID]
        try:
            with open("DB/ghost_config.json", "r") as f:
                data = json.load(f)
                vd = data.get("vault_dest")
                if vd and vd != "me":
                    valid_chats.append(int(vd))
        except Exception:
            pass
            
        # Ensure this is in one of the vault chats
        if event.chat_id not in valid_chats:
            return
            
        # Ignore commands like .a or .da
        if event.text and event.text.startswith("."):
            return
            
        reply_msg = await event.get_reply_message()
        if not reply_msg or not reply_msg.text:
            return
            
        import re
        # Look for the user ID format in the notification template
        match = re.search(r"🆔 \*\*User ID:\*\* `(\d+)`", reply_msg.text)
        if not match:
            return
            
        user_id = int(match.group(1))
        
        try:
            # Send message cleanly to the user without any forward tags
            await event.client.send_message(
                entity=user_id,
                message=event.text,
                file=event.media,
                link_preview=False
            )
            # Confirm in the vault
            await event.reply("✅ _Message sent cleanly to user._")
        except Exception as e:
            await event.reply(f"❌ _Failed to send to user:_ `{e}`")


    print(
        f"✅ PM Permit Plugin initialized (pmpermit_enabled={assistant.data['config'].get('pmpermit_enabled', True)})"
    )
    return assistant
