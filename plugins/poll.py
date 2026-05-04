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
from telethon.tl.types import InputMediaPoll, Poll, PollAnswer

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

def _build_poll(options: list[str]) -> list[PollAnswer]:
    """Convert a list of option strings into Telethon PollAnswer objects."""
    return [
        PollAnswer(text=opt.strip(), option=bytes([i]))
        for i, opt in enumerate(options)
    ]


# ─── Command Registration ─────────────────────────────────────────────────────

async def register_commands():

    @CipherElite.on(events.NewMessage(pattern=r"^\.poll(?:\s|$)([\s\S]*)"))
    @rishabh()
    async def poll_creator(event):
        """Create a poll — custom or default."""
        input_str = event.pattern_match.group(1).strip()
        reply_to = event.reply_to_msg_id or event.id

        if input_str:
            # ── Custom poll ──────────────────────────────────────────────────
            parts = [p.strip() for p in input_str.split(";")]
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

            poll_answers = _build_poll(options)

            try:
                await event.client.send_message(
                    event.chat_id,
                    file=InputMediaPoll(
                        poll=Poll(
                            id=random.getrandbits(32),
                            question=question,
                            answers=poll_answers,
                        )
                    ),
                    reply_to=reply_to,
                )
                await event.delete()

            except PollOptionInvalidError:
                await event.reply(
                    "❌ `One or more poll options contain invalid data (possibly too long).`"
                )
            except ForbiddenError:
                await event.reply("`❌ Polls are not allowed in this chat.`")
            except Exception as e:
                await event.reply(f"**❌ Error:**\n`{e}`")

        else:
            # ── Default poll ─────────────────────────────────────────────────
            default_options = _build_poll([
                "Yeah, sure! 😊✌️",
                "Nah 😏😕",
                "Whatever 🥱🙄",
            ])

            try:
                await event.client.send_message(
                    event.chat_id,
                    file=InputMediaPoll(
                        poll=Poll(
                            id=random.getrandbits(32),
                            question="👆 So do you guys agree with this?",
                            answers=default_options,
                        )
                    ),
                    reply_to=reply_to,
                )
                await event.delete()

            except PollOptionInvalidError:
                await event.reply(
                    "❌ `One or more poll options contain invalid data.`"
                )
            except ForbiddenError:
                await event.reply("`❌ Polls are not allowed in this chat.`")
            except Exception as e:
                await event.reply(f"**❌ Error:**\n`{e}`")
