# =============================================================================
#  CipherElite Userbot Plugin
#
#  Plugin Name:    poll
#  Author:         CipherElite Dev (@rishabhops)
#  Repository:     https://github.com/rishabhops/CipherElite
#
#  License:        MIT
# =============================================================================
#
#  Commands:
#    .poll                               — Sends a default "Do you agree?" poll
#    .poll question ; option1 ; option2  — Creates a custom poll (2–10 options)
#
# =============================================================================

import random

from telethon import events
from telethon.errors.rpcbaseerrors import ForbiddenError
from telethon.errors.rpcerrorlist import PollOptionInvalidError
from telethon.tl import types

from utils.utils import CipherElite
from utils.decorators import rishabh
from plugins.bot import add_handler


# ─── Plugin Registration ──────────────────────────────────────────────────────

def init(client_instance):
    commands = [
        ".poll  —  Sends a default 'Do you agree?' poll.\n"
        "    Reply to a message to send the poll as a reply.",

        ".poll <question> ; <opt1> ; <opt2> [; opt3 ...]  —  Create a custom poll.\n"
        "    Requires at least 2 and at most 10 options.\n"
        "    Separate question and options with semicolons  `;`\n"
        "    Example:\n"
        "      .poll Are you a morning person? ; Yes! 🌅 ; Nope 🌙 ; Sometimes 😴",
    ]
    description = "📊 Poll — Create quick polls in any chat"
    add_handler("poll", commands, description)


# ─── Helper ───────────────────────────────────────────────────────────────────

def _make_question(text: str):
    """
    Returns the correct question type for the installed Telethon version.
    Telethon >= 1.24 (Layer 166+): question must be TextWithEntities.
    Older versions:                question is a plain string.
    """
    try:
        return types.TextWithEntities(text=text, entities=[])
    except AttributeError:
        return text


def _make_answer_text(text: str):
    """Same logic for PollAnswer.text field."""
    try:
        return types.TextWithEntities(text=text.strip(), entities=[])
    except AttributeError:
        return text.strip()


def _build_poll(options: list[str]) -> list:
    """
    Convert option strings into PollAnswer objects.
    Uses ASCII-encoded index bytes: b'0', b'1', ... b'9'
    (null bytes and raw ints cause MEDIA_INVALID on some layers).
    """
    return [
        types.PollAnswer(
            text=_make_answer_text(opt),
            option=str(i).encode(),   # b'0', b'1', ...
        )
        for i, opt in enumerate(options)
    ]


def _build_media(question: str, answers: list) -> types.InputMediaPoll:
    """Wrap a Poll in InputMediaPoll. id=0 lets Telegram assign the real ID."""
    return types.InputMediaPoll(
        poll=types.Poll(
            id=0,
            question=_make_question(question),
            answers=answers,
            closed=False,
            public_voters=False,
            multiple_choice=False,
            quiz=False,
        )
    )


# ─── Command Registration ─────────────────────────────────────────────────────

async def register_commands():

    @CipherElite.on(events.NewMessage(pattern=r"^\.poll(?:\s|$)([\s\S]*)"))
    @rishabh()
    async def poll_creator(event):
        """Create a poll — custom or default."""
        input_str = event.pattern_match.group(1).strip()
        reply_to  = event.reply_to_msg_id or event.id

        if input_str:
            # ── Custom poll ──────────────────────────────────────────────────
            parts    = [p.strip() for p in input_str.split(";")]
            question = parts[0]
            options  = parts[1:]

            if len(options) < 2:
                return await event.reply(
                    "❌ **Too few options.**\n"
                    "Provide at least **2** options separated by `;`\n\n"
                    "**Format:** `.poll question ; option1 ; option2`"
                )
            if len(options) > 10:
                return await event.reply(
                    "❌ **Too many options.**\n"
                    "Telegram only allows a maximum of **10** options per poll."
                )

            try:
                media = _build_media(question, _build_poll(options))
                await event.client.send_message(
                    event.chat_id,
                    file=media,
                    reply_to=reply_to,
                )
                await event.delete()

            except PollOptionInvalidError:
                await event.reply(
                    "❌ `One or more options are too long or contain invalid data.`"
                )
            except ForbiddenError:
                await event.reply("`❌ Polls are not allowed in this chat.`")
            except Exception as e:
                await event.reply(f"**❌ Error:**\n`{e}`")

        else:
            # ── Default poll ─────────────────────────────────────────────────
            try:
                media = _build_media(
                    "👆 So do you guys agree with this?",
                    _build_poll(["Yeah, sure! 😊✌️", "Nah 😏😕", "Whatever 🥱🙄"]),
                )
                await event.client.send_message(
                    event.chat_id,
                    file=media,
                    reply_to=reply_to,
                )
                await event.delete()

            except PollOptionInvalidError:
                await event.reply("❌ `Poll option invalid data.`")
            except ForbiddenError:
                await event.reply("`❌ Polls are not allowed in this chat.`")
            except Exception as e:
                await event.reply(f"**❌ Error:**\n`{e}`")

