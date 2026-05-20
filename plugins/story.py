import os
import re
import asyncio

from telethon import events
from telethon.tl.types import (
    InputPeerSelf,
    InputPrivacyValueAllowAll,
    InputPrivacyValueAllowContacts,
    Channel,
)
from telethon.tl.functions.stories import (
    SendStoryRequest,
    GetStoriesByIDRequest,
    DeleteStoriesRequest,
)
from telethon.tl.functions.users import GetFullUserRequest
from telethon.tl.functions.channels import GetFullChannelRequest

from utils.utils import CipherElite
from utils.decorators import rishabh
from plugins.bot import add_handler


def init(client_instance):
    commands = [
        ".setstory <reply media> [caption] [-contacts] - Set replied media as your story",
        ".storydl <username / reply / link> - Download user stories stealthily",
        ".delstory <id> - Delete your story by ID",
    ]
    description = "🎭 Story Tools - Upload, Download, & Manage Telegram Stories Stealthily"
    add_handler("story", commands, description)


# ================= SET STORY ================= #

@CipherElite.on(events.NewMessage(outgoing=True, pattern=r"\.setstory(?:\s+(.*))?$"))
@rishabh()
async def set_story(event):
    try:
        reply = await event.get_reply_message()
        if not reply or not (reply.photo or reply.video):
            return await event.reply("❌ **Please reply to a photo or video to set it as a story!**")

        args = event.pattern_match.group(1) or ""
        caption = args.replace("-contacts", "").strip()
        
        privacy = [InputPrivacyValueAllowAll()]
        if "-contacts" in args.lower():
            privacy = [InputPrivacyValueAllowContacts()]

        status = await event.reply("🔄 **Uploading your masterpiece to Stories...** ✨")

        # Fallback to downloading and uploading if direct media pass fails
        try:
            await event.client(
                SendStoryRequest(
                    peer=InputPeerSelf(),
                    media=reply.media,
                    privacy_rules=privacy,
                    caption=caption if caption else None
                )
            )
        except Exception as upload_err:
            # Direct forward failed, try downloading and uploading manually
            dl_path = await reply.download_media()
            if not dl_path:
                return await status.edit("❌ **Failed to process media.**")
            
            # Need to upload as InputMedia first, SendStoryRequest is a raw API call
            uploaded = await event.client.upload_file(dl_path)
            from telethon.tl.types import InputMediaUploadedPhoto, InputMediaUploadedDocument
            
            if reply.photo:
                in_media = InputMediaUploadedPhoto(file=uploaded)
            else:
                in_media = InputMediaUploadedDocument(
                    file=uploaded,
                    mime_type=reply.file.mime_type or "video/mp4",
                    attributes=reply.document.attributes
                )
            
            await event.client(
                SendStoryRequest(
                    peer=InputPeerSelf(),
                    media=in_media,
                    privacy_rules=privacy,
                    caption=caption if caption else None
                )
            )
            os.remove(dl_path)

        await status.edit("🔥 **Story is now Live!** 🎉")

    except Exception as e:
        await event.reply(f"❌ **Error:** `{str(e)}`")


# ================= STORY DOWNLOAD / VIEW ================= #

@CipherElite.on(events.NewMessage(outgoing=True, pattern=r"\.storydl(?:\s+(.*))?$"))
@rishabh()
async def story_download(event):
    try:
        text = event.pattern_match.group(1)
        reply = await event.get_reply_message()

        status = await event.reply("🔄 **Fetching stories stealthily...** 🕵️‍♂️")

        files = []
        captions = []

        # ---------- Link ----------
        if text and re.match(r"https?://t\.me/([^/]+)/s/(\d+)", text):
            match = re.match(r"https?://t\.me/([^/]+)/s/(\d+)", text)
            username = match.group(1)
            story_id = int(match.group(2))

            entity = await event.client.get_entity(username)
            result = await event.client(GetStoriesByIDRequest(entity.id, [story_id]))

            if not result.stories:
                return await status.edit("❌ **Story not found or has expired!**")

            for story in result.stories:
                dl = await event.client.download_media(story.media)
                if dl:
                    files.append(dl)
                    captions.append(story.caption or "📸 *Story*")

            if files:
                await event.client.send_file(event.chat_id, files, caption="🎭 **Downloaded Story:**\n\n" + "\n".join(captions))
                for f in files: os.remove(f)
                return await status.edit("✅ **Story Downloaded Successfully!**")
            else:
                return await status.edit("❌ **Failed to download story.**")

        # ---------- Username / Reply ----------
        if not text:
            if reply:
                entity = reply.sender_id
            else:
                return await status.edit("❌ **Reply to a user, provide a username, or paste a story link!**")
        else:
            entity = text
            try:
                entity = int(entity)
            except ValueError:
                pass

        try:
            target = await event.client.get_entity(entity)
        except Exception:
            return await status.edit("❌ **Could not find that user!**")

        if isinstance(target, Channel):
            full = (await event.client(GetFullChannelRequest(target.id))).full_channel
            stories = full.stories
        else:
            full = (await event.client(GetFullUserRequest(target.id))).full_user
            stories = full.stories

        if not stories or not stories.stories:
            return await status.edit("❌ **No active stories found for this user!**")

        await status.edit(f"🔄 **Found {len(stories.stories)} active stories! Downloading...** 📥")

        for story in stories.stories[:10]:  # Cap at 10 to avoid flood
            dl = await event.client.download_media(story.media)
            if dl:
                files.append(dl)
                captions.append(story.caption or "")

        if files:
            title_name = getattr(target, 'first_name', None) or getattr(target, 'title', 'User')
            await event.client.send_file(
                event.chat_id, 
                files, 
                caption=f"🎭 **{title_name}'s Stories:**"
            )
            for f in files: os.remove(f)
            await status.delete()
        else:
            await status.edit("❌ **Failed to download media from stories.**")

    except Exception as e:
        await event.reply(f"❌ **Error:** `{str(e)}`")


# ================= DELETE STORY ================= #

@CipherElite.on(events.NewMessage(outgoing=True, pattern=r"\.delstory(?:\s+(\d+))?$"))
@rishabh()
async def del_story(event):
    try:
        story_id = event.pattern_match.group(1)
        if not story_id:
            return await event.reply("❌ **Usage:** `.delstory <story_id>`")

        story_id = int(story_id)
        status = await event.reply("🔄 **Deleting story...** 🗑️")

        await event.client(
            DeleteStoriesRequest(
                peer=InputPeerSelf(),
                id=[story_id]
            )
        )
        await status.edit(f"✅ **Story #{story_id} deleted successfully!**")

    except Exception as e:
        await event.reply(f"❌ **Error:** `{str(e)}`")
