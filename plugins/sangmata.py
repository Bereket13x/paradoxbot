# =============================================================================
#  CipherElite Userbot Plugin
#
#  Plugin Name:    sangmata
#  Author:         CipherElite Dev (@rishabhops)
#  Repository:     https://github.com/rishabhops/CipherElite
#
#  License:        MIT
# =============================================================================
#
#  Commands:
#    .sg  <user/reply/id>   — Fetch name history via @SangMata_beta_bot
#    .sgu <user/reply/id>   — Fetch username history via @SangMata_beta_bot
#
# =============================================================================

import asyncio

from telethon import events
from telethon.errors.rpcerrorlist import YouBlockedUserError
from telethon.tl import types
from telethon.tl.functions.contacts import UnblockRequest as UnblockRequest

from utils.utils import CipherElite
from utils.decorators import rishabh
from plugins.bot import add_handler


# ─── Plugin Registration ──────────────────────────────────────────────────────

def init(client_instance):
    commands = [
        ".sg <user>   —  Fetch the full **name history** of a user.\n"
        "    Pass a @username, user ID, or simply reply to their message.\n"
        "    Example:  .sg @username",

        ".sgu <user>  —  Fetch the full **username history** of a user.\n"
        "    Pass a @username, user ID, or simply reply to their message.\n"
        "    Example:  .sgu @username",
    ]
    description = "🕵️ SangMata — Name & username history lookup via @SangMata_beta_bot"
    add_handler("sangmata", commands, description)


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _mention(display_name: str, user_id: int) -> str:
    """Build a Telegram mention link."""
    return f"[{display_name}](tg://user?id={user_id})"


def _sangmata_parse(responses: list[str]) -> tuple[str, str]:
    """
    Split SangMata bot responses into name-history and username-history blocks.

    @SangMata_beta_bot sends one message per record, usually:
      - Lines mentioning 'first name', 'last name', 'name' → names
      - Lines mentioning 'username', '@'                    → usernames
    Everything not sorted goes to names as a catch-all.
    """
    name_lines: list[str] = []
    user_lines: list[str] = []

    for text in responses:
        low = text.lower()
        if any(kw in low for kw in ("username", "@")):
            user_lines.append(text.strip())
        else:
            name_lines.append(text.strip())

    names_out    = "\n\n".join(name_lines)    or "`No name records found.`"
    usernames_out = "\n\n".join(user_lines)   or "`No username records found.`"
    return names_out, usernames_out


async def _resolve_user(event, raw: str):
    """
    Try to resolve `raw` (could be @username, numeric ID string, or empty)
    to a Telethon User entity. If raw is empty, uses the reply's sender.
    Returns (user_entity, error_string).
    """
    try:
        if raw:
            target = int(raw) if raw.lstrip("-").isdigit() else raw.strip()
        else:
            reply = await event.get_reply_message()
            if not reply:
                return None, (
                    "❌ Reply to a user's message, or pass a @username / user ID."
                )
            target = reply.sender_id

        entity = await event.client.get_entity(target)
        if not isinstance(entity, types.User):
            return None, "❌ That entity is not a user (might be a group or channel)."
        return entity, None

    except Exception as e:
        return None, f"❌ Could not resolve user: `{e}`"


# ─── Command Registration ─────────────────────────────────────────────────────

async def register_commands():

    @CipherElite.on(events.NewMessage(pattern=r"^\.sg(u?)(?:\s|$)([\s\S]*)"))
    @rishabh()
    async def sangmata(event):
        """
        .sg  → name history
        .sgu → username history
        """
        want_usernames = bool(event.pattern_match.group(1))   # 'u' flag present?
        raw_input      = (event.pattern_match.group(2) or "").strip()

        catevent = await event.reply("`🔍 Looking up user...`")

        # ── Resolve the target user ───────────────────────────────────────────
        user, err = await _resolve_user(event, raw_input)
        if err:
            return await catevent.edit(err)

        display_name = (
            f"{user.first_name} {user.last_name}"
            if user.last_name
            else user.first_name or "Unknown"
        )
        mention = _mention(display_name, user.id)

        await catevent.edit(
            f"`⏳ Querying @SangMata_beta_bot for` {mention}`…`",
            parse_mode="md",
        )

        # ── Conversation with the bot ─────────────────────────────────────────
        bot_chat = "@SangMata_beta_bot"
        responses: list[str] = []

        try:
            async with event.client.conversation(bot_chat, timeout=30) as conv:

                # Send the user ID (the bot accepts plain numeric IDs)
                try:
                    await conv.send_message(str(user.id))
                except YouBlockedUserError:
                    await catevent.edit(
                        "`⚠️ You had @SangMata_beta_bot blocked. Unblocking & retrying…`"
                    )
                    await event.client(UnblockRequest("SangMata_beta_bot"))
                    await conv.send_message(str(user.id))

                # Collect all responses until the bot stops replying
                while True:
                    try:
                        resp = await conv.get_response(timeout=5)
                        if resp.text:
                            responses.append(resp.text)
                    except asyncio.TimeoutError:
                        break

                await event.client.send_read_acknowledge(conv.chat_id)

        except asyncio.TimeoutError:
            pass  # Outer timeout — use whatever we collected
        except Exception as e:
            return await catevent.edit(f"**❌ Conversation Error:**\n`{e}`")

        # ── Handle empty / failure responses ──────────────────────────────────
        if not responses:
            return await catevent.edit(
                f"**🕵️ SangMata**\n"
                f"**User:** {mention}\n\n"
                "`❌ Bot returned no data. The user may not be tracked yet.`"
            )

        full_text = " ".join(responses).lower()
        if "no records found" in full_text or "not found" in full_text:
            return await catevent.edit(
                f"**🕵️ SangMata**\n"
                f"**User:** {mention}\n\n"
                "`ℹ️ No records found for this user.`"
            )

        # ── Parse & format output ─────────────────────────────────────────────
        names_history, usernames_history = _sangmata_parse(responses)

        if want_usernames:
            history_label   = "Username History"
            history_content = usernames_history
        else:
            history_label   = "Name History"
            history_content = names_history

        output = (
            f"**🕵️ SangMata Lookup**\n"
            f"━━━━━━━━━━━━━━━━━\n"
            f"**👤 User:** {mention}\n"
            f"**🆔 ID:** `{user.id}`\n"
            f"━━━━━━━━━━━━━━━━━\n"
            f"**📋 {history_label}:**\n"
            f"{history_content}"
        )

        # Telegram message cap is 4096 chars
        if len(output) > 4096:
            output = output[:4090] + "\n…`[truncated]`"

        await catevent.edit(output, link_preview=False)
