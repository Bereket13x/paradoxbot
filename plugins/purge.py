# =============================================================================
#  PARADOX Userbot Plugin
#
#  Plugin Name:    purge
#  Description:    Purge messages in the current chat and delete all history
#
# =============================================================================

import asyncio
from telethon import events
from telethon.errors import RPCError, MessageDeleteForbiddenError
from telethon.tl.functions.messages import DeleteHistoryRequest
from telethon.tl.types import ChannelParticipantsAdmins

from utils.utils import CipherElite
from utils.decorators import rishabh
from plugins.bot import add_handler


def init(client):
    commands = [
        ".purge  — Delete all messages from replied msg to current (must reply)",
        ".p      — Alias for .purge",
        ".delall — Delete entire chat history (or a specific user's msgs if replied)",
    ]
    add_handler("purge", commands, "Message Purge Plugin")


# ─── Helpers ──────────────────────────────────────────────────────────────────

async def _is_admin(client, chat_id, user_id) -> bool:
    """Return True if user is admin/creator in a group/channel, or if it's a DM."""
    try:
        async for admin in client.iter_participants(
            chat_id, filter=ChannelParticipantsAdmins
        ):
            if admin.id == user_id:
                return True
        return False
    except Exception:
        # Can't check → assume DM or small group; allow
        return True





# ─── Global cancellation flags ────────────────────────────────────────────────
# Key: chat_id  →  Value: asyncio.Event  (set = cancel requested)
_cancel_flags: dict[int, asyncio.Event] = {}


# ─────────────────────────────────────────────────────────────────────────────
#  .purge / .p  — delete from replied message up to .purge message (inclusive)
# ─────────────────────────────────────────────────────────────────────────────
@CipherElite.on(events.NewMessage(pattern=r"^\.(purge|p)$", outgoing=True))
@rishabh()
async def purge_cmd(event):
    """Delete every message between the replied-to message and this one."""

    reply = await event.get_reply_message()
    if not reply:
        await event.reply("❌ **Reply to the message you want to start purging from.**")
        return

    chat_id = event.chat_id
    me = await CipherElite.get_me()

    # Admin check for groups/channels
    if not event.is_private:
        if not await _is_admin(CipherElite, chat_id, me.id):
            await event.reply(
                "❌ **I need admin rights with delete-messages permission to purge here.**"
            )
            return

    start_id = reply.id
    end_id = event.id  # the .purge command itself (already deleted by decorator)

    if start_id >= end_id:
        await event.reply("❌ **No messages to purge.**")
        return

    # Collect all real message IDs in this chat between start and end
    # Using iter_messages with min_id / max_id avoids touching other chats
    ids_to_delete = []
    async for msg in CipherElite.iter_messages(
        chat_id,
        min_id=start_id - 1,   # iter_messages is exclusive on min side
        max_id=end_id + 1,     # exclusive on max side
        reverse=True,
    ):
        ids_to_delete.append(msg.id)

    if not ids_to_delete:
        await event.reply("❌ **No messages found in that range.**")
        return

    # Delete in batches of 100 (Telegram API limit)
    BATCH = 100
    deleted = 0
    try:
        for i in range(0, len(ids_to_delete), BATCH):
            batch = ids_to_delete[i : i + BATCH]
            await CipherElite.delete_messages(chat_id, batch, revoke=True)
            deleted += len(batch)
            if i + BATCH < len(ids_to_delete):
                await asyncio.sleep(0.4)
    except (RPCError, MessageDeleteForbiddenError) as e:
        await event.reply(f"❌ **Purge failed:** `{e}`")
        return
    except Exception as e:
        await event.reply(f"❌ **Unexpected error:** `{e}`")
        return

    confirm = await event.reply(f"✅ **Purged {deleted} messages.**")
    await asyncio.sleep(3)
    try:
        await confirm.delete()
    except Exception:
        pass


# ─────────────────────────────────────────────────────────────────────────────
#  .delall  — delete full history or a specific user's messages
# ─────────────────────────────────────────────────────────────────────────────
@CipherElite.on(events.NewMessage(pattern=r"^\.delall$", outgoing=True))
@rishabh()
async def delall_cmd(event):
    """
    Delete entire chat history.
    • No reply  → delete ALL messages in the chat (needs admin in groups).
    • Reply     → delete that user's messages only (needs admin if not yourself).
    """
    chat_id = event.chat_id
    me = await CipherElite.get_me()
    private = event.is_private

    # Determine target
    target_user = None
    if event.is_reply:
        reply = await event.get_reply_message()
        if reply and reply.sender_id:
            target_user = reply.sender_id

    # ── Permission checks ────────────────────────────────────────────────────
    if not private:
        # Deleting someone else's messages or ALL messages → need admin
        if target_user != me.id:
            if not await _is_admin(CipherElite, chat_id, me.id):
                msg = await event.reply(
                    "🚫 **Admin rights required** to delete messages in this chat."
                )
                await asyncio.sleep(5)
                try:
                    await msg.delete()
                except Exception:
                    pass
                return

    # ── Set up cancellation ──────────────────────────────────────────────────
    flag = asyncio.Event()
    _cancel_flags[chat_id] = flag

    scope_text = (
        "your messages"
        if target_user == me.id
        else f"messages from user `{target_user}`"
        if target_user
        else "**ALL messages**"
    )
    warning = await event.reply(
        f"⚠️ About to delete {scope_text} in **20 seconds**.\n"
        "Reply `.cancel` to abort."
    )

    # ── 20-second countdown ──────────────────────────────────────────────────
    try:
        await asyncio.wait_for(flag.wait(), timeout=20)
        # Cancelled
        try:
            await warning.edit("🚫 **Deletion cancelled.**")
            await asyncio.sleep(3)
            await warning.delete()
        except Exception:
            pass
        return
    except asyncio.TimeoutError:
        pass
    finally:
        _cancel_flags.pop(chat_id, None)

    # ── Perform deletion ─────────────────────────────────────────────────────
    try:
        await warning.edit("🗑️ **Deleting messages…**")
    except Exception:
        pass

    deleted_count = 0
    error_msg = None

    try:
        if target_user is None:
            # Delete entire history via Telegram's API (works in DMs + groups where you own them)
            await CipherElite(
                DeleteHistoryRequest(
                    peer=chat_id,
                    max_id=2_147_483_647,   # delete everything up to the last possible ID
                    revoke=True,            # delete for everyone
                    just_clear=False,
                )
            )
            deleted_count = "all"
        else:
            # Delete specific user's messages one by one
            BATCH = 100
            batch_ids = []

            async for msg in CipherElite.iter_messages(
                chat_id, from_user=target_user
            ):
                if msg.id == warning.id:
                    continue
                batch_ids.append(msg.id)

                if len(batch_ids) >= BATCH:
                    await CipherElite.delete_messages(
                        chat_id, batch_ids, revoke=True
                    )
                    deleted_count += len(batch_ids)
                    batch_ids.clear()
                    await asyncio.sleep(0.4)

            # Flush remainder
            if batch_ids:
                await CipherElite.delete_messages(
                    chat_id, batch_ids, revoke=True
                )
                deleted_count += len(batch_ids)

    except Exception as e:
        error_msg = str(e)

    # ── Final status ─────────────────────────────────────────────────────────
    try:
        if error_msg:
            await warning.edit(f"❌ **Error:** `{error_msg}`")
            await asyncio.sleep(6)
        else:
            await warning.edit(f"✅ **Deleted {deleted_count} messages.**")
            await asyncio.sleep(3)
        await warning.delete()
    except Exception:
        pass


# ─────────────────────────────────────────────────────────────────────────────
#  .cancel  — abort a running .delall countdown
# ─────────────────────────────────────────────────────────────────────────────
@CipherElite.on(events.NewMessage(pattern=r"^\.cancel$", outgoing=True))
async def cancel_cmd(event):
    """Cancel a pending .delall operation in the current chat."""
    chat_id = event.chat_id
    if chat_id in _cancel_flags:
        _cancel_flags[chat_id].set()
        try:
            await event.delete()
        except Exception:
            pass
