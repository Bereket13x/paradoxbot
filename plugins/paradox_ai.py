```python name=plugins/paradox_ai.py url=https://github.com/Bereket13x/paradoxbot/blob/main/plugins/paradox_ai.py
# =============================================================================
#  PARADOX Userbot Plugin
#
#  Plugin Name:    paradoxAI
#  Author:         PARADOX Dev
# =============================================================================

import asyncio
import re
import os
import json
from datetime import datetime

from openai import AsyncOpenAI, OpenAIError, AuthenticationError, RateLimitError
from telethon import events
from utils.utils import CipherElite
from utils.decorators import rishabh
from plugins.bot import add_handler

NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"
NVIDIA_DEFAULT_MODEL = "mistralai/mistral-nemotron"
GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
GEMINI_DEFAULT_MODEL = "gemini-2.0-flash"

conversation_history: dict = {}
AUTO_AI_STATE = "OFF"   # "OFF" | "ALL"

def get_system_prompt() -> dict:
    current_time = datetime.now().strftime("%A, %B %d, %Y - %I:%M %p")
    return {
        "role": "system",
        "content": (
            f"You are the user's personal AI assistant. You were developed by Paradox Ethiopian Developer. "
            f"Current Date: {current_time}. Provide natural and highly accurate answers to the people messaging you. "
            "Do not unnecessarily introduce yourself or mention technical details about being a userbot in every message. Just directly and politely answer. "
            "By default, keep your answers short and concise but ensure they provide a good, clear explanation. "
            "If the user explicitly asks you to be brief, answer as briefly as possible. "
            "Return only the final result without any thinking process, internal deliberations, or <think> blocks. "
            "Avoid technical model details or markdown unless absolutely necessary. "
            "IMPORTANT LANGUAGE RULE: You must communicate ONLY in English. "
            "If you receive a prompt in ANY other language, refuse and reply EXACTLY: "
            "'I'm sorry, I can only understand and respond in English. Please message me in English for assistance.'"
        )
    }

def _build_client(provider: str, nvidia_key: str | None, gemini_key: str | None):
    if provider == "gemini" and gemini_key:
        return AsyncOpenAI(base_url=GEMINI_BASE_URL, api_key=gemini_key), GEMINI_DEFAULT_MODEL
    if nvidia_key:
        return AsyncOpenAI(base_url=NVIDIA_BASE_URL, api_key=nvidia_key), NVIDIA_DEFAULT_MODEL
    return None, None

def is_english(text: str) -> bool:
    if not text:
        return True
    # Checks that most of the message consists of ASCII characters.
    ascii_ratio = sum(1 for c in text if c.isascii()) / max(1, len(text))
    return ascii_ratio >= 0.9

async def make_ai_request(messages: list, temperature=0.6, top_p=0.7, max_tokens=2048) -> str:
    try:
        from plugins.ai_setup import ai_config
        provider   = ai_config.get_provider()
        nvidia_key = ai_config.get_nvidia_key()
        gemini_key = ai_config.get_gemini_key()

        client, model = _build_client(provider, nvidia_key, gemini_key)
        if not client:
            if provider == "gemini":
                return "❌ **Auth Error:** Gemini API key not set. Use `.paigemini <key>` or `.setai <key>`"
            return "❌ **Auth Error:** NVIDIA API key not set. Use `.paiset <key>` or `.setnai <key>`"

        stream = await client.chat.completions.create(
            model=model, messages=messages,
            temperature=temperature, top_p=top_p,
            max_tokens=max_tokens, stream=True
        )
        response = ""
        async for chunk in stream:
            if chunk.choices[0].delta.content is not None:
                response += chunk.choices[0].delta.content

        return re.sub(r'<think>.*?</think>', '', response, flags=re.DOTALL).strip()

    except AuthenticationError:
        return "❌ **Authentication Error:** Invalid API key. Update via `.paiset` or `.paigemini`."
    except RateLimitError:
        return "⏳ **Rate Limited:** Too many requests. Please wait a moment."
    except OpenAIError as e:
        return f"❌ **API Error:** {str(e)[:200]}"
    except asyncio.TimeoutError:
        return "⏰ **Timeout Error:** Request took too long."
    except Exception as e:
        print("Exception in make_ai_request:", e)
        return f"❌ **Unexpected Error:** {str(e)}"

async def animate_thinking(message, api_task):
    frames = [
        "**[░░░░░░░░░░]  5%** ⏳ `Initializing neuro-link...`",
        "**[█░░░░░░░░░] 15%** 🧠 `Analyzing query patterns...`",
        "**[███░░░░░░░] 30%** 🔍 `Searching databanks...`",
        "**[█████░░░░░] 50%** ⚙️ `Synthesizing information...`",
        "**[███████░░░] 75%** ⚡ `Optimizing tokens...`",
        "**[█████████░] 90%** 🚀 `Finalizing output...`",
        "**[██████████] 100%** ✅ `Response ready!`",
    ]
    idx = 0
    try:
        while not api_task.done():
            try:
                await message.edit(frames[idx])
                idx = (idx + 1) if idx < len(frames) - 1 else 0
            except Exception:
                pass
            await asyncio.sleep(1.5)
    except asyncio.CancelledError:
        pass

def init(client):
    commands = [
        ".pai <question>          — Ask PARADOX AI a question",
        ".pautoai <on/off>        — Enable / disable auto AI responder",
        ".paimode <nvidia/gemini> — Switch AI provider",
        ".paiset <key>            — Set NVIDIA API key",
        ".paigemini <key>         — Set Gemini API key",
        ".paitest                 — Test current AI connection",
        ".paiclear                — Clear conversation history",
        ".paistatus               — Show AI status",
    ]
    description = "🤖 PARADOX AI — NVIDIA or Gemini powered assistant with auto-reply support."
    add_handler("paradox_ai", commands, description)
    print("🤖 PARADOX AI Plugin initialized successfully")
    return True

@CipherElite.on(events.NewMessage(pattern=r"(?i)\.pautoai(?:\s+(on|off|status))?"))
@rishabh()
async def autoai_handler(event):
    global AUTO_AI_STATE
    action = event.pattern_match.group(1)

    if not action:
        await event.reply(
            f"🤖 **Auto AI is currently `{AUTO_AI_STATE}`.**\n\n"
            "Usage: `.pautoai on` · `.pautoai off`"
        )
        return

    action = action.lower()
    if action == "on":
        AUTO_AI_STATE = "ALL"
        await event.reply(
            "✅ **Auto AI enabled globally.**\n"
            "PARADOX will now automatically reply to incoming messages."
        )
    elif action == "off":
        AUTO_AI_STATE = "OFF"
        await event.reply("❌ **Auto AI disabled.**")
    elif action == "status":
        await event.reply(f"🤖 **Auto AI is currently `{AUTO_AI_STATE}`.**")

@CipherElite.on(events.NewMessage())
async def auto_reply_handler(event):
    global AUTO_AI_STATE
    if AUTO_AI_STATE == "OFF":
        return

    try:
        from plugins.ai_setup import ai_config
        if not ai_config.is_enabled():
            return
    except Exception:
        return

    if not event.is_private:
        return

    try:
        sender = await event.get_sender()
        if getattr(sender, "bot", False):
            return
    except Exception as e:
        print("Exception getting sender:", e)
        return

    if event.text and event.text.startswith((".", "/", "!")):
        return

    text = event.text
    if not text:
        return

    if not is_english(text):
        await event.respond("I'm sorry, I can only understand and respond in English. Please message me in English for assistance.")
        return

    chat_id = event.chat_id
    if chat_id not in conversation_history:
        conversation_history[chat_id] = [get_system_prompt()]

    conversation_history[chat_id].append({"role": "user", "content": text})
    if len(conversation_history[chat_id]) > 5:
        conversation_history[chat_id] = [get_system_prompt()] + conversation_history[chat_id][-4:]

    try:
        thinking_msg = await event.respond("**[░░░░░░░░░░]  0%** ⏳ `Connecting to PARADOX AI...`")

        api_task = asyncio.create_task(
            asyncio.wait_for(make_ai_request(conversation_history[chat_id]), timeout=30.0)
        )
        anim_task = asyncio.create_task(animate_thinking(thinking_msg, api_task))

        try:
            response = await api_task
        except asyncio.TimeoutError:
            response = "❌ Timeout"
        finally:
            if not anim_task.done():
                anim_task.cancel()

        if not str(response).startswith(("❌", "⏳")):
            conversation_history[chat_id].append({"role": "assistant", "content": str(response)})
            await thinking_msg.edit(str(response))
        else:
            await thinking_msg.delete()
    except Exception as e:
        print("Exception in auto_reply_handler:", e)
        pass

# ...rest of the plugin (pai commands, provider config, clear, status, etc.) stay the same...
