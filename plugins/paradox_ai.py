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
from typing import Optional

from openai import AsyncOpenAI, OpenAIError, AuthenticationError, RateLimitError
from telethon import events
from utils.utils import CipherElite
from utils.decorators import rishabh
from plugins.bot import add_handler

NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"
NVIDIA_DEFAULT_MODEL = "mistralai/mistral-nemotron"
GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
GEMINI_DEFAULT_MODEL = "gemini-2.0-flash"

conversation_history = {}
AUTO_AI_STATE = "OFF"   # "OFF" | "ALL"

def get_system_prompt():
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

def _build_client(provider: str, nvidia_key: Optional[str], gemini_key: Optional[str]):
    if provider == "gemini" and gemini_key:
        return AsyncOpenAI(base_url=GEMINI_BASE_URL, api_key=gemini_key), GEMINI_DEFAULT_MODEL
    if nvidia_key:
        return AsyncOpenAI(base_url=NVIDIA_BASE_URL, api_key=nvidia_key), NVIDIA_DEFAULT_MODEL
    return None, None

def is_english(text: str) -> bool:
    if not text:
        return True
    ascii_ratio = sum(1 for c in text if c.isascii()) / max(1, len(text))
    return ascii_ratio >= 0.9

async def make_ai_request(messages, temperature=0.6, top_p=0.7, max_tokens=2048):
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
        await event.reply(f"🤖 **Auto AI is currently `{AUTO_AI_STATE}`.")

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

    # Ignore outgoing messages (your own)
    if event.out:
        return

    # Do not reply if user is approved (pmpermit)
    db_path = "DB/assistant_db.json"
    chat_id = str(event.chat_id)
    if os.path.exists(db_path):
        try:
            with open(db_path, "r", encoding="utf-8") as f:
                db = json.load(f)
            if "approved_users" in db and chat_id in db["approved_users"]:
                return
        except Exception as e:
            print("Exception checking approved users:", e)

    if event.text and event.text.startswith((".", "/", "!")):
        return

    text = event.text
    if not text:
        return

    if not is_english(text):
        await event.respond("I'm sorry, I can only understand and respond in English. Please message me in English for assistance.")
        return

    chat_id_int = event.chat_id
    if chat_id_int not in conversation_history:
        conversation_history[chat_id_int] = [get_system_prompt()]

    conversation_history[chat_id_int].append({"role": "user", "content": text})
    if len(conversation_history[chat_id_int]) > 5:
        conversation_history[chat_id_int] = [get_system_prompt()] + conversation_history[chat_id_int][-4:]

    try:
        thinking_msg = await event.respond("**[░░░░░░░░░░]  0%** ⏳ `Connecting to PARADOX AI...`")

        api_task = asyncio.create_task(
            asyncio.wait_for(make_ai_request(conversation_history[chat_id_int]), timeout=30.0)
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
            conversation_history[chat_id_int].append({"role": "assistant", "content": str(response)})
            await thinking_msg.edit(str(response))
        else:
            await thinking_msg.delete()
    except Exception as e:
        print("Exception in auto_reply_handler:", e)

@CipherElite.on(events.NewMessage(pattern=r"\.pai(?:\s+(.*))?"))
@rishabh()
async def ai_handler(event):
    thinking_msg = None
    try:
        from plugins.ai_setup import ai_config

        if not ai_config.is_enabled():
            provider = ai_config.get_provider()
            hint = "`.paigemini <key>` or `.setai <key>`" if provider == "gemini" else "`.paiset <key>` or `.setnai <key>`"
            await event.reply(f"🔑 **API Key Required!**\n\nUse {hint} to set your key.")
            return

        query = event.pattern_match.group(1)

        try:
            reply_msg = await event.get_reply_message()
            if reply_msg and reply_msg.text:
                ctx = f"Context message: {reply_msg.text}\n\n"
                query = f"{ctx}{query}" if query else f"Analyze or reply to this:\n\n{ctx}"
        except Exception:
            pass

        if not query:
            await event.reply(
                "❓ **Usage:** `.pai <your question>`\n"
                "Or reply to a message with `.pai` to analyze it."
            )
            return

        if len(query) > 2000:
            await event.reply("📝 **Query too long!** Keep it under 2000 characters.")
            return

        if not is_english(query):
            await event.reply("I'm sorry, I can only understand and respond in English. Please message me in English for assistance.")
            return

        thinking_msg = await event.respond("**[░░░░░░░░░░]  0%** ⏳ `Connecting to PARADOX AI...`")

        chat_id = event.chat_id
        if chat_id not in conversation_history:
            conversation_history[chat_id] = [get_system_prompt()]

        conversation_history[chat_id].append({"role": "user", "content": query})
        if len(conversation_history[chat_id]) > 6:
            conversation_history[chat_id] = [get_system_prompt()] + conversation_history[chat_id][-5:]

        api_task = asyncio.create_task(
            asyncio.wait_for(make_ai_request(conversation_history[chat_id]), timeout=45.0)
        )
        anim_task = asyncio.create_task(animate_thinking(thinking_msg, api_task))

        try:
            response = await api_task
        except asyncio.TimeoutError:
            response = "⏰ **Timeout:** AI took too long. Try a shorter question."
        finally:
            if not anim_task.done():
                anim_task.cancel()

        if response.startswith(("❌", "⏳")):
            await thinking_msg.edit(response)
            return

        conversation_history[chat_id].append({"role": "assistant", "content": response})

        if len(response) > 3500:
            parts = [response[i:i+3500] for i in range(0, len(response), 3500)]
            await thinking_msg.edit(f"🤖 **PARADOX AI (Part 1/{len(parts)}):**\n\n{parts[0]}")
            for i, part in enumerate(parts[1:], 2):
                await event.respond(f"🤖 **Part {i}/{len(parts)}:**\n\n{part}")
        else:
            short_q = query[:100] + ("..." if len(query) > 100 else "")
            await thinking_msg.edit(
                f"🤖 **PARADOX AI:**\n\n{response}\n\n"
                f"💭 **Query:** `{short_q}`"
            )

    except Exception as e:
        if thinking_msg:
            try:
                await thinking_msg.edit(f"❌ **Error:** {str(e)}")
            except Exception:
                pass

@CipherElite.on(events.NewMessage(pattern=r"\.paiset(?:\s+(.*))?"))
@rishabh()
async def aiset_handler(event):
    try:
        from plugins.ai_setup import ai_config
        api_key = event.pattern_match.group(1)
        if not api_key:
            await event.reply("🔑 **Usage:** `.paiset <your_nvidia_api_key>`")
            return

        ai_config.set_nvidia_key(api_key.strip())
        msg = await event.respond("✅ **NVIDIA API Key set successfully!**")
        await asyncio.sleep(5)
        try:
            await msg.delete()
        except Exception:
            pass
    except Exception as e:
        await event.reply(f"❌ **Error:** {str(e)}")

@CipherElite.on(events.NewMessage(pattern=r"\.paigemini(?:\s+(.*))?"))
@rishabh()
async def aigemini_handler(event):
    try:
        from plugins.ai_setup import ai_config
        api_key = event.pattern_match.group(1)
        if not api_key:
            await event.reply("🔑 **Usage:** `.paigemini <your_gemini_api_key>`")
            return

        ai_config.set_gemini_key(api_key.strip())
        ai_config.set_provider("gemini")
        msg = await event.respond("✅ **Gemini API Key set! Provider auto-switched to Gemini.**")
        await asyncio.sleep(5)
        try:
            await msg.delete()
        except Exception:
            pass
    except Exception as e:
        await event.reply(f"❌ **Error:** {str(e)}")

@CipherElite.on(events.NewMessage(pattern=r"(?i)\.paimode(?:\s+(nvidia|gemini))?"))
@rishabh()
async def aimode_handler(event):
    try:
        from plugins.ai_setup import ai_config
        mode = event.pattern_match.group(1)
        if not mode:
            await event.reply(
                f"⚙️ **Usage:** `.paimode nvidia` or `.paimode gemini`\n\n"
                f"Current provider: **{ai_config.get_provider().upper()}**"
            )
            return
        ai_config.set_provider(mode.lower())
        await event.reply(f"✅ **AI Provider switched to: {mode.upper()}**")
    except Exception as e:
        await event.reply(f"❌ **Error:** {str(e)}")

@CipherElite.on(events.NewMessage(pattern=r"\.paitest"))
@rishabh()
async def aitest_handler(event):
    try:
        from plugins.ai_setup import ai_config
        if not ai_config.is_enabled():
            provider = ai_config.get_provider()
            hint = "`.paigemini <key>`" if provider == "gemini" else "`.paiset <key>`"
            await event.reply(f"❌ **No {provider.upper()} key set.** Use {hint} first.")
            return

        provider = ai_config.get_provider()
        test_msg = await event.respond(f"🧪 **Testing {provider.upper()} API connection...**")
        test_messages = [
            get_system_prompt(),
            {"role": "user", "content": "Say 'Hello, I am PARADOX AI!' in exactly those words."}
        ]

        response = await asyncio.wait_for(make_ai_request(test_messages), timeout=20.0)

        if response.startswith(("❌", "⏳")):
            await test_msg.edit(f"❌ **Test Failed:**\n\n{response}")
        else:
            await test_msg.edit(f"✅ **Test Successful!**\n\n🤖 **PARADOX AI:** {response}")
    except Exception as e:
        await event.reply(f"❌ **Test Error:** {str(e)}")

@CipherElite.on(events.NewMessage(pattern=r"\.paiclear"))
@rishabh()
async def aiclear_handler(event):
    try:
        chat_id = event.chat_id
        if chat_id in conversation_history:
            count = len(conversation_history.pop(chat_id))
            await event.reply(f"🗑️ **History cleared!** Removed `{count}` messages.")
        else:
            await event.reply("📭 **No history found** for this chat.")
    except Exception as e:
        await event.reply(f"❌ **Error:** {str(e)}")

@CipherElite.on(events.NewMessage(pattern=r"\.paistatus"))
@rishabh()
async def aistatus_handler(event):
    try:
        from plugins.ai_setup import ai_config
        provider    = ai_config.get_provider()
        nvidia_key  = ai_config.get_nvidia_key()
        gemini_key  = ai_config.get_gemini_key()
        model       = GEMINI_DEFAULT_MODEL if provider == "gemini" else NVIDIA_DEFAULT_MODEL
        history_cnt = len(conversation_history)
        msg_cnt     = sum(len(h) for h in conversation_history.values())

        await event.reply(
            f"📊 **PARADOX AI Status:**\n\n"
            f"⚡ **Active Provider:** `{provider.upper()}`\n"
            f"🤖 **Model:** `{model}`\n"
            f"📩 **Auto-responder:** `{AUTO_AI_STATE}`\n\n"
            f"🔑 **NVIDIA Key:** `{'✅ Set' if nvidia_key else '❌ Not Set'}`\n"
            f"🔑 **Gemini Key:** `{'✅ Set' if gemini_key else '❌ Not Set'}`\n\n"
            f"💾 **Active Chats:** `{history_cnt}`\n"
            f"💬 **Total Messages:** `{msg_cnt}`"
        )
    except Exception as e:
        await event.reply(f"❌ **Error:** {str(e)}")

print("✅ PARADOX AI Plugin loaded successfully")
