# =============================================================================
#  CipherElite Userbot Plugin
#
#  Plugin Name:    telegraph
#  Author:         CipherElite Dev (@rishabhops)
#  Repository:     https://github.com/rishabhops/CipherElite
#
#  License:        MIT
# =============================================================================
#
#  Commands:
#    .tgm               — Reply to media → get Telegraph link
#    .tgt [title]       — Reply to text  → post on Telegraph
#    .ctg <url/reply>   — Get instant link preview via @chotamreaderbot
#
# =============================================================================

import os
import random
import string
from datetime import datetime

from PIL import Image
from telegraph import Telegraph, exceptions, upload_file
from telethon import events
from telethon.errors.rpcerrorlist import YouBlockedUserError
from telethon.tl.functions.contacts import UnblockRequest as UnblockRequest
from telethon.utils import get_display_name
from urlextract import URLExtract

from utils.utils import CipherElite
from utils.decorators import rishabh
from plugins.bot import add_handler


# ─── Telegraph account (created once at module load) ─────────────────────────

def _random_short_name(length: int = 10) -> str:
    return "".join(
        random.choices(string.ascii_lowercase + string.digits, k=length)
    )


telegraph = Telegraph()
try:
    _r = telegraph.create_account(short_name=_random_short_name())
    _auth_url = _r.get("auth_url", "N/A")
except Exception as _e:
    _auth_url = f"(account creation failed: {_e})"

extractor = URLExtract()

TEMP_DIR = "./temp"
os.makedirs(TEMP_DIR, exist_ok=True)


# ─── Plugin Registration ──────────────────────────────────────────────────────

def init(client_instance):
    commands = [
        ".tgm  —  Reply to any media (image/video/gif/sticker) to upload it to\n"
        "    Telegraph and get a permanent shareable link.\n"
        "    (Max size: 5 MB)",

        ".tgt [title]  —  Reply to a text message (or media with caption) to\n"
        "    post its content as a Telegraph page. Optionally pass a custom\n"
        "    page title after the command.\n"
        "    Example:  .tgt My Custom Title",

        ".ctg <url>  —  Get an instant link preview (AMP page) for a URL.\n"
        "    You can also reply to a message containing a URL instead of\n"
        "    typing it manually.\n"
        "    Example:  .ctg https://example.com",
    ]
    description = "📝 Telegraph Tools — Upload media & create Telegraph pages"
    add_handler("telegraph", commands, description)


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _resize_webp(path: str):
    """Convert a .webp sticker to PNG so Telegraph can accept it."""
    img = Image.open(path)
    img.save(path, "PNG")


# ─── Command Registration ─────────────────────────────────────────────────────

async def register_commands():

    # ── .tgm — Upload media to Telegraph ─────────────────────────────────────
    @CipherElite.on(events.NewMessage(pattern=r"^\.tgm$"))
    @rishabh()
    async def tg_media(event):
        """Reply to any media → get a permanent Telegraph link."""
        if not event.is_reply:
            return await event.reply("`Reply to a media message to get its Telegraph link.`")

        reply = await event.get_reply_message()
        if not reply.media:
            return await event.reply("`Replied message has no media.`")

        catevent = await event.reply("`⬇️ Downloading media...`")
        start = datetime.now()
        downloaded = None

        try:
            downloaded = await event.client.download_media(reply, TEMP_DIR)
            if not downloaded:
                return await catevent.edit("`❌ Failed to download media.`")

            await catevent.edit("`📤 Uploading to Telegraph...`")

            # Convert .webp stickers so Telegraph accepts them
            if downloaded.endswith(".webp"):
                _resize_webp(downloaded)

            media_urls = upload_file(downloaded)
            elapsed = (datetime.now() - start).seconds
            link = f"https://graph.org{media_urls[0]}"

            await catevent.edit(
                f"**📎 Telegraph Link:** [View Media]({link})\n"
                f"**⏱️ Time Taken:** `{elapsed}s`",
                link_preview=True,
            )
        except exceptions.TelegraphException as exc:
            await catevent.edit(f"**❌ Telegraph Error:**\n`{exc}`")
        except Exception as e:
            await catevent.edit(f"**❌ Error:**\n`{e}`")
        finally:
            if downloaded and os.path.exists(downloaded):
                os.remove(downloaded)


    # ── .tgt — Post text/content to Telegraph ────────────────────────────────
    @CipherElite.on(events.NewMessage(pattern=r"^\.tgt(?:\s+([\s\S]*))?$"))
    @rishabh()
    async def tg_text(event):
        """Reply to a text message → post on Telegraph, returns link."""
        if not event.is_reply:
            return await event.reply("`Reply to a text message to post it on Telegraph.`")

        reply = await event.get_reply_message()
        custom_title = (event.pattern_match.group(1) or "").strip()

        catevent = await event.reply("`📝 Creating Telegraph page...`")
        start = datetime.now()
        downloaded = None

        try:
            # Determine page title
            if custom_title:
                title = custom_title
            else:
                try:
                    sender = await event.client.get_entity(reply.sender_id)
                    title = get_display_name(sender) or "Telegraph Post"
                except Exception:
                    title = "Telegraph Post"

            page_content = reply.message or ""

            # If the reply has media (e.g. a text file), read its content
            if reply.media and not reply.photo and not reply.video:
                await catevent.edit("`📥 Downloading attached file...`")
                downloaded = await event.client.download_media(reply, TEMP_DIR)
                if downloaded:
                    if not custom_title and page_content:
                        title = page_content  # use existing caption as title
                    try:
                        with open(downloaded, "rb") as fd:
                            page_content = fd.read().decode("utf-8", errors="replace")
                    except Exception:
                        pass

            if not page_content:
                return await catevent.edit("`❌ No text content found to post.`")

            # Telegraph uses HTML line breaks
            html_content = page_content.replace("\n", "<br>")

            try:
                response = telegraph.create_page(title, html_content=html_content)
            except Exception:
                # Title might be invalid — fall back to a random one
                title = "".join(
                    random.choices(
                        string.ascii_lowercase + string.ascii_uppercase, k=16
                    )
                )
                response = telegraph.create_page(title, html_content=html_content)

            elapsed = (datetime.now() - start).seconds
            link = f"https://graph.org/{response['path']}"

            await catevent.edit(
                f"**📄 Telegraph Page:** [Read Here]({link})\n"
                f"**📌 Title:** `{response.get('title', title)}`\n"
                f"**⏱️ Time Taken:** `{elapsed}s`",
                link_preview=True,
            )
        except Exception as e:
            await catevent.edit(f"**❌ Error:**\n`{e}`")
        finally:
            if downloaded and os.path.exists(downloaded):
                os.remove(downloaded)


    # ── .ctg — Link preview via @chotamreaderbot ─────────────────────────────
    @CipherElite.on(events.NewMessage(pattern=r"^\.ctg(?:\s+([\s\S]*))?$"))
    @rishabh()
    async def ctg(event):
        """Get an instant link preview (AMP) for a URL."""
        input_str = (event.pattern_match.group(1) or "").strip()

        # Allow replying to a message that contains a URL
        if not input_str and event.is_reply:
            replied = await event.get_reply_message()
            if replied and replied.message:
                input_str = replied.message.strip()

        if not input_str:
            return await event.reply(
                "❌ **Usage:** `.ctg <url>` or reply to a message containing a URL."
            )

        urls = extractor.find_urls(input_str)
        if not urls:
            return await event.reply("`❌ No valid URL found in the text.`")

        target_url = urls[0]
        catevent = await event.reply(f"`🔗 Fetching preview for:` `{target_url}`")
        bot_chat = "@chotamreaderbot"

        try:
            async with event.client.conversation(bot_chat, timeout=30) as conv:
                try:
                    sent = await conv.send_message(target_url)
                except YouBlockedUserError:
                    await catevent.edit(
                        "`⚠️ You have blocked @chotamreaderbot. Unblocking and retrying...`"
                    )
                    await event.client(UnblockRequest("chotamreaderbot"))
                    sent = await conv.send_message(target_url)

                response = await conv.get_response()
                await event.client.send_read_acknowledge(conv.chat_id)

                if not response or not response.text:
                    await catevent.edit("`❌ Bot returned an empty response.`")
                    return

                await catevent.delete()
                await event.client.send_message(
                    event.chat_id,
                    response,
                    reply_to=event.reply_to_msg_id or event.id,
                    link_preview=True,
                )

                # Clean up: delete our sent message from the bot's chat
                try:
                    await event.client.delete_messages(bot_chat, [sent.id, response.id])
                except Exception:
                    pass

        except Exception as e:
            await catevent.edit(f"**❌ Error:**\n`{e}`")
