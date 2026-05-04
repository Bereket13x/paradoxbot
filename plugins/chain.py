# =============================================================================
#  CipherElite Userbot Plugin
#
#  Plugin Name:    chain
#  Author:         CipherElite Dev (@rishabhops)
#  Repository:     https://github.com/rishabhops/CipherElite
#
#  License:        MIT
# =============================================================================
#
#  Commands:
#    .chain   —  Reply to any message to count the reply-chain depth
#                and get a direct thread link to the root message.
#
# =============================================================================

from telethon import events
from telethon.tl.functions.messages import SaveDraftRequest

from utils.utils import CipherElite
from utils.decorators import rishabh
from plugins.bot import add_handler


# ─── Plugin Registration ──────────────────────────────────────────────────────

def init(client_instance):
    commands = [
        ".chain  —  Reply to any message in a thread to count how deep\n"
        "    the reply chain is and get a link to the thread root.\n"
        "    Example:  .chain  (while replying to a message)"
    ]
    description = "🔗 Chain — Count the reply-chain depth of any message thread"
    add_handler("chain", commands, description)


# ─── Command Registration ─────────────────────────────────────────────────────

async def register_commands():

    @CipherElite.on(events.NewMessage(pattern=r"^\.chain$"))
    @rishabh()
    async def chain(event):
        """Reply to any message → counts the full reply-chain length."""
        msg = await event.get_reply_message()
        if not msg:
            return await event.reply("`❌ Reply to a message to count its chain length.`")

        catevent = await event.reply("`🔗 Counting chain...`")

        try:
            # Resolve the numeric chat ID (strips the -100 prefix for supergroups)
            chat_entity = await event.client.get_entity(event.chat_id)
            chat_id = chat_entity.id

            # Walk to the thread root if the replied message is itself a reply
            root_msg_id = msg.id
            if msg.reply_to:
                root_msg_id = (
                    msg.reply_to.reply_to_top_id
                    or msg.reply_to.reply_to_msg_id
                )

            thread_link = f"https://t.me/c/{chat_id}/{root_msg_id}?thread={root_msg_id}"

            # Walk the chain upward, counting each hop
            count = -1
            current = msg
            while current:
                reply = await current.get_reply_message()
                if reply is None:
                    # Save a draft reply-to at the chain root so it's easy to jump back
                    try:
                        await event.client(
                            SaveDraftRequest(
                                await event.get_input_chat(),
                                "",
                                reply_to_msg_id=current.id,
                            )
                        )
                    except Exception:
                        pass
                current = reply
                count += 1

            await catevent.edit(
                f"**🔗 Chain Length:** `{count}`\n"
                f"**📎 Thread Root:** [Jump Here]({thread_link})"
            )

        except Exception as e:
            await catevent.edit(f"**❌ Error:**\n`{e}`")
