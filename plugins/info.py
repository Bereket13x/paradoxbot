# =============================================================================
#  CipherElite Userbot Plugin
#
#  Plugin Name:    info
#  Author:         CipherElite Dev (@rishabhops)
#  Repository:     https://github.com/rishabhops/CipherElite
#
#  License:        MIT
#
#  IMPORTANT:
#    • If you copy, fork, or include this plugin in your own bot,
#      you MUST keep this header intact.
#    • You MUST give proper credit to the CipherElite Userbot author:
#        – GitHub:    https://github.com/rishabhops/CipherElite
#        – Telegram:  @thanosceo
#
#  Thank you for respecting open-source software!
# =============================================================================

import html
from datetime import datetime, timedelta, timezone

from telethon import events
from telethon.tl.functions.channels import GetFullChannelRequest
from telethon.tl.functions.messages import GetFullChatRequest
from telethon.tl.functions.users import GetFullUserRequest
from telethon.tl.types import (
    Channel, Chat, User,
    UserStatusLastMonth, UserStatusLastWeek,
    UserStatusOffline, UserStatusOnline, UserStatusRecently,
)

from utils.utils import CipherElite
from utils.decorators import rishabh
from plugins.bot import add_handler


# ─────────────────────────────────────────────────────────────────────────────
# 📚  Registration
# ─────────────────────────────────────────────────────────────────────────────

def init(client_instance):
    commands = [
        ".info <username / user_id / reply>   — Detailed Telegram user profile",
        ".whois <username / user_id / reply>  — Alias for .info",
        ".chatinfo [chat / reply]             — Detailed group or channel info",
    ]
    description = "🔎 Info — Deep-scan any user, group, or channel"
    add_handler("info", commands, description)


# ─────────────────────────────────────────────────────────────────────────────
# 🛠  Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _safe(text) -> str:
    return html.escape(str(text)) if text else "N/A"


def _flag(val: bool, yes="✅", no="❌") -> str:
    return yes if val else no


def _account_age(date) -> str:
    if not date:
        return "Unknown"
    if date.tzinfo is None:
        date = date.replace(tzinfo=timezone.utc)
    delta = datetime.now(timezone.utc) - date
    years, rem   = divmod(delta.days, 365)
    months, days = divmod(rem, 30)
    parts = []
    if years:  parts.append(f"{years}y")
    if months: parts.append(f"{months}mo")
    if days:   parts.append(f"{days}d")
    return " ".join(parts) or "Just created"


def _online_status(user: User) -> str:
    s = getattr(user, "status", None)
    if s is None:
        return "⚫️ <i>Status hidden</i>"
    if isinstance(s, UserStatusOnline):
        return "🟢 <b>Online right now</b>"
    if isinstance(s, UserStatusRecently):
        return "🟡 Recently online"
    if isinstance(s, UserStatusLastWeek):
        return "🟠 Seen this week"
    if isinstance(s, UserStatusLastMonth):
        return "🔴 Seen this month"
    if isinstance(s, UserStatusOffline):
        was = s.was_online
        diff = datetime.now(timezone.utc) - was
        if diff < timedelta(minutes=1):
            return "🟢 <b>Just now</b>"
        if diff < timedelta(hours=1):
            return f"🟡 {diff.seconds // 60} min ago"
        if diff < timedelta(days=1):
            return f"🟠 {diff.seconds // 3600}h ago"
        return f"🔴 {diff.days}d ago"
    return "⚫️ Status unknown"


def _divider(label: str = "") -> str:
    if label:
        return f"\n╔══〔 <b>{label}</b> 〕\n"
    return "╚══════════════════\n"


# ─────────────────────────────────────────────────────────────────────────────
# 👤  .info / .whois
# ─────────────────────────────────────────────────────────────────────────────

async def register_commands():

    @CipherElite.on(events.NewMessage(pattern=r"^\.(?:info|whois)(?:\s|$)(.*)"))
    @rishabh()
    async def info_command(event):
        await event.delete()
        arg = (event.pattern_match.group(1) or "").strip()

        catevent = await event.respond("<code>🔍 Scanning user...</code>", parse_mode="html")

        try:
            # ── Resolve target ────────────────────────────────────────────────
            if event.reply_to_msg_id:
                reply = await event.get_reply_message()
                target = reply.sender_id
            elif arg:
                target = int(arg) if arg.lstrip("-").isdigit() else arg
            else:
                target = (await event.client.get_me()).id

            user   = await event.client.get_entity(target)
            if not isinstance(user, User):
                return await catevent.edit("❌ <b>Target is not a user.</b>", parse_mode="html")

            full   = await event.client(GetFullUserRequest(user.id))
            bio    = full.full_user.about or None
            photos = await event.client.get_profile_photos(user)
            photo_count = len(photos)

            # ── Build name & mention ──────────────────────────────────────────
            first  = _safe(user.first_name)
            last   = _safe(user.last_name) if user.last_name else ""
            name   = f"{first} {last}".strip()
            mention = f'<a href="tg://user?id={user.id}">{name}</a>'
            uname   = f"@{_safe(user.username)}" if user.username else "—"

            # ── Common chats (best-effort) ────────────────────────────────────
            try:
                common = await event.client.get_common_chats(user.id)
                common_count = len(common)
            except Exception:
                common_count = "—"

            # ── Compose message ───────────────────────────────────────────────
            text = (
                "┌─────────────────────────\n"
                f"│  👤  <b>USER ANALYSIS</b>  —  PARADOX\n"
                "└─────────────────────────\n"
                "\n"
                f"  <b>Name</b>     ›  {mention}\n"
                f"  <b>Username</b> ›  {uname}\n"
                f"  <b>User ID</b>  ›  <code>{user.id}</code>\n"
                "\n"
                "╔══〔 <b>ACCOUNT FLAGS</b> 〕\n"
                f"║  🤖 Bot          ›  {_flag(user.bot)}\n"
                f"║  ✅ Verified     ›  {_flag(user.verified)}\n"
                f"║  ⭐ Premium      ›  {_flag(getattr(user, 'premium', False))}\n"
                f"║  ⚠️ Scam         ›  {_flag(getattr(user, 'scam', False), '⚠️ Yes', '✅ No')}\n"
                f"║  🛑 Fake         ›  {_flag(getattr(user, 'fake', False), '🛑 Yes', '✅ No')}\n"
                f"║  🔒 Restricted   ›  {_flag(getattr(user, 'restricted', False), '⚠️ Yes', '✅ No')}\n"
                "╚══════════════════\n"
                "\n"
                "╔══〔 <b>ACTIVITY</b> 〕\n"
                f"║  📡 Status       ›  {_online_status(user)}\n"
                f"║  📅 Acc. Age     ›  {_account_age(getattr(user, 'date', None))}\n"
                f"║  🌍 Language     ›  {_safe(getattr(user, 'lang_code', None)) or '—'}\n"
                f"║  📸 Photos       ›  {photo_count}\n"
                f"║  👥 Mutual chats ›  {common_count}\n"
                "╚══════════════════\n"
            )

            if bio:
                text += (
                    "\n"
                    "╔══〔 <b>BIO</b> 〕\n"
                    f"║  {_safe(bio)}\n"
                    "╚══════════════════\n"
                )

            # ── Permanent profile link (ID-based, never changes) ──────────────
            profile_link = f"tg://user?id={user.id}"

            text += (
                "\n"
                "╔══〔 <b>PERMANENT LINK</b> 〕\n"
                f'║  🔗 <a href="{profile_link}">tg://user?id={user.id}</a>\n'
                "╚══════════════════\n"
                "\n<i>Powered by PARADOX</i>"
            )

            await catevent.delete()
            if photos:
                await event.client.send_file(
                    event.chat_id,
                    photos[0],
                    caption=text,
                    parse_mode="html",
                )
            else:
                await event.respond(text, parse_mode="html")

        except Exception as e:
            await catevent.edit(f"<b>❌ Error:</b>\n<code>{_safe(e)}</code>", parse_mode="html")


    # ─────────────────────────────────────────────────────────────────────────
    # 👥  .chatinfo
    # ─────────────────────────────────────────────────────────────────────────

    @CipherElite.on(events.NewMessage(pattern=r"^\.chatinfo(?:\s|$)(.*)"))
    @rishabh()
    async def chatinfo_command(event):
        await event.delete()
        arg = (event.pattern_match.group(1) or "").strip()

        catevent = await event.respond("<code>🔍 Scanning chat...</code>", parse_mode="html")

        try:
            # ── Resolve target ────────────────────────────────────────────────
            if event.reply_to_msg_id:
                reply  = await event.get_reply_message()
                entity = await event.client.get_entity(reply.chat_id)
            elif arg:
                target = int(arg) if arg.lstrip("-").isdigit() else arg
                entity = await event.client.get_entity(target)
            else:
                entity = await event.client.get_entity(event.chat_id)

            if not isinstance(entity, (Channel, Chat)):
                return await catevent.edit("❌ <b>Target is not a group or channel.</b>", parse_mode="html")

            # ── Fetch full info ───────────────────────────────────────────────
            if isinstance(entity, Channel):
                full = await event.client(GetFullChannelRequest(entity))
            else:
                full = await event.client(GetFullChatRequest(entity.id))

            description = (full.full_chat.about or "").strip()

            # ── Member count ──────────────────────────────────────────────────
            try:
                members = full.full_chat.participants_count
                if members is None:
                    members = (await event.client.get_participants(entity, limit=0)).total
            except Exception:
                members = "—"

            # ── Build flags ───────────────────────────────────────────────────
            is_broadcast = getattr(entity, "broadcast", False)
            is_megagroup = getattr(entity, "megagroup", False)
            is_public    = bool(getattr(entity, "username", None))
            is_verified  = getattr(entity, "verified", False)
            is_scam      = getattr(entity, "scam", False)
            is_fake      = getattr(entity, "fake", False)

            if is_broadcast:
                chat_type = "📢 Channel"
            elif is_megagroup:
                chat_type = "👥 Supergroup"
            else:
                chat_type = "💬 Group"

            link = f"https://t.me/{entity.username}" if is_public else "Private (invite link only)"

            # ── Compose ───────────────────────────────────────────────────────
            text = (
                "┌─────────────────────────\n"
                f"│  👥  <b>CHAT ANALYSIS</b>  —  PARADOX\n"
                "└─────────────────────────\n"
                "\n"
                f"  <b>Name</b>     ›  {_safe(entity.title)}\n"
                f"  <b>Type</b>     ›  {chat_type}\n"
                f"  <b>Chat ID</b>  ›  <code>{entity.id}</code>\n"
                f"  <b>Link</b>     ›  {link}\n"
                "\n"
                "╔══〔 <b>STATISTICS</b> 〕\n"
                f"║  👥 Members      ›  {members:,}" if isinstance(members, int) else f"║  👥 Members      ›  {members}"
            )
            text += (
                "\n"
                f"║  🔓 Visibility   ›  {'🌍 Public' if is_public else '🔒 Private'}\n"
                f"║  ✅ Verified     ›  {_flag(is_verified)}\n"
                f"║  ⚠️ Scam         ›  {_flag(is_scam, '⚠️ Yes', '✅ No')}\n"
                f"║  🛑 Fake         ›  {_flag(is_fake, '🛑 Yes', '✅ No')}\n"
                "╚══════════════════\n"
            )

            if description:
                text += (
                    "\n"
                    "╔══〔 <b>DESCRIPTION</b> 〕\n"
                    f"║  {_safe(description)}\n"
                    "╚══════════════════\n"
                )

            # ── Permanent chat link ───────────────────────────────────────────
            if is_public:
                chat_link_display = f"https://t.me/{entity.username}"
            else:
                chat_link_display = "Private (no public link)"

            text += (
                "\n"
                "╔══〔 <b>CHAT LINK</b> 〕\n"
                f'║  🔗 {f"<a href=\'https://t.me/{entity.username}\'>https://t.me/{entity.username}</a>" if is_public else "Private (no public link)"}\n'
                "╚══════════════════\n"
                "\n<i>Powered by PARADOX</i>"
            )

            # ── Send with photo if available ──────────────────────────────────
            await catevent.delete()
            try:
                photos = await event.client.get_profile_photos(entity, limit=1)
                if photos:
                    await event.client.send_file(
                        event.chat_id,
                        photos[0],
                        caption=text,
                        parse_mode="html",
                    )
                    return
            except Exception:
                pass
            await event.respond(text, parse_mode="html")

        except Exception as e:
            await catevent.edit(f"<b>❌ Error:</b>\n<code>{_safe(e)}</code>", parse_mode="html")
