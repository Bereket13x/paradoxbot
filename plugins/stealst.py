"""
PARADOX Stickers Plugin
Created for sticker stealing and management.
"""

from telethon import events
from telethon.tl.types import DocumentAttributeSticker, InputStickerSetID, InputStickerSetShortName
from telethon.tl.functions.messages import GetStickerSetRequest
from telethon.errors import MessageNotModifiedError
from telethon.utils import get_extension
import io
import os
import math
import asyncio
from PIL import Image

from utils.utils import CipherElite
from utils.decorators import rishabh
from plugins.bot import add_handler
from config.config import Config

def init(client_instance):
    commands = [
        ".steal <pack_name> - Steal a replied sticker into your custom pack",
        ".stealpack <pack_name> - Steal an entire replied sticker pack",
        ".stickerinfo - Get information about the replied sticker"
    ]
    description = "🎨 PARADOX Stickers – Manage, steal, and view stickers"
    add_handler("stealst", commands, description)

async def register_commands():
    @CipherElite.on(events.NewMessage(pattern=r"^\.steal(?:\s+(.*))?$"))
    @rishabh()
    async def kang_sticker(event):
        """Steals a sticker and adds it to your pack."""
        reply = await event.get_reply_message()
        if not reply or not (reply.media):
            await event.reply("❌ **Please reply to a sticker or image to steal it!**")
            return

        status = await event.reply("🔄 **Stealing sticker...**")
        user = await event.client.get_me()
        
        custom_name = event.pattern_match.group(1)
        
        is_anim = False
        is_vid = False
        is_emoji = False
        
        if reply.document:
            if reply.document.mime_type == "application/x-tgsticker":
                is_anim = True
            elif reply.document.mime_type == "video/webm":
                is_vid = True
            
            for attr in reply.document.attributes:
                if type(attr).__name__ == 'DocumentAttributeCustomEmoji':
                    is_emoji = True
                if isinstance(attr, DocumentAttributeSticker):
                    if attr.alt:
                        emoji = attr.alt

        file_ext = get_extension(reply.media)
        if not file_ext:
            file_ext = ".webp"
        
        downloaded_file = await reply.download_media("kang_media" + file_ext)

        # Convert photo to 512x512 webp if needed
        if not is_anim and not is_vid and not downloaded_file.endswith(".webp"):
            img = Image.open(downloaded_file)
            img.thumbnail((512, 512))
            new_file = "kang_media.webp"
            img.save(new_file, "WebP")
            os.remove(downloaded_file)
            downloaded_file = new_file

        import re
        base_name = custom_name.strip() if custom_name else "PARADOX"
        clean_name = re.sub(r'[^a-zA-Z0-9]', '', base_name)
        if not clean_name:
            clean_name = "pack"
            
        clean_name = clean_name[:30]
        
        pack_title = f"{base_name[:40]} @netcorexp"
        short_name = f"prdx_{clean_name}_{user.id}"

        pack_type_msg = ""
        if is_emoji:
            pack_title += " Emoji"
            short_name += "_emj"
            cmd_new = "/newemojipack"
            if is_anim:
                pack_type_msg = "Animated"
            elif is_vid:
                pack_type_msg = "Video"
            else:
                pack_type_msg = "Static"
        elif is_anim:
            pack_title += " Anim"
            short_name += "_anim"
            cmd_new = "/newanimated"
        elif is_vid:
            pack_title += " Vid"
            short_name += "_vid"
            cmd_new = "/newvideo"
        else:
            cmd_new = "/newpack"

        pack_num = 1
        success = False
        link = ""

        try:
            async with event.client.conversation("@Stickers", timeout=15) as conv:
                while not success and pack_num <= 5:
                    curr_title = f"{pack_title} V{pack_num}"
                    curr_short = f"{short_name}_v{pack_num}"
                    
                    await conv.send_message("/addsticker")
                    resp = await conv.get_response()
                    
                    if "Invalid pack selected" in resp.text or "choose the sticker pack" not in resp.text.lower():
                        # Pack probably doesn't exist, try to create it
                        await conv.send_message("/cancel")
                        await conv.get_response()
                        await conv.send_message(cmd_new)
                        r_type = await conv.get_response() # How to call it OR type of emoji pack
                        if cmd_new == "/newemojipack" and "choose the type" in r_type.text.lower():
                            await conv.send_message(pack_type_msg)
                            await conv.get_response()
                        await conv.send_message(curr_title)
                        await conv.get_response() # Send sticker
                        
                        await conv.send_file(downloaded_file, force_document=True)
                        r = await conv.get_response() # Send emoji
                        if "Sorry, the file type is invalid" in r.text or "invalid" in r.text.lower():
                            await status.edit(f"❌ **Failed to add sticker:**\n`{r.text}`")
                            if os.path.exists(downloaded_file):
                                os.remove(downloaded_file)
                            return
                        
                        await conv.send_message(emoji)
                        await conv.get_response() # Publish
                        await conv.send_message("/publish")
                        await conv.get_response() # Icon
                        await conv.send_message("/skip")
                        await conv.get_response() # Short name
                        await conv.send_message(curr_short)
                        final_resp = await conv.get_response()
                        
                        if "Sorry, this short name is already taken" in final_resp.text:
                            await conv.send_message("/cancel")
                            pack_num += 1
                            continue
                        
                        link = f"https://t.me/addstickers/{curr_short}"
                        success = True
                    else:
                        # Choose pack
                        await conv.send_message(curr_short)
                        r1 = await conv.get_response()
                        if "Invalid pack" in r1.text or "does not exist" in r1.text:
                            await conv.send_message("/cancel")
                            # We need to create it
                            await conv.get_response()
                            await conv.send_message(cmd_new)
                            r_type = await conv.get_response()
                            if cmd_new == "/newemojipack" and "choose the type" in r_type.text.lower():
                                await conv.send_message(pack_type_msg)
                                await conv.get_response()
                            await conv.send_message(curr_title)
                            await conv.get_response()
                            await conv.send_file(downloaded_file, force_document=True)
                            await conv.get_response()
                            await conv.send_message(emoji)
                            await conv.get_response()
                            await conv.send_message("/publish")
                            await conv.get_response()
                            await conv.send_message("/skip")
                            await conv.get_response()
                            await conv.send_message(curr_short)
                            r_short = await conv.get_response()
                            if "already taken" in r_short.text:
                                await conv.send_message("/cancel")
                                pack_num += 1
                                continue
                            link = f"https://t.me/addstickers/{curr_short}"
                            success = True
                        elif "send me the sticker" in r1.text.lower() or "send me the custom emoji" in r1.text.lower():
                            await conv.send_file(downloaded_file, force_document=True)
                            r2 = await conv.get_response()
                            if "invalid" in r2.text.lower():
                                await status.edit(f"❌ **Failed to upload:** {r2.text}")
                                if os.path.exists(downloaded_file):
                                    os.remove(downloaded_file)
                                return
                            await conv.send_message(emoji)
                            r3 = await conv.get_response()
                            if "limit reached" in r3.text.lower() or "120" in r3.text:
                                await conv.send_message("/cancel")
                                pack_num += 1
                                continue
                            await conv.send_message("/done")
                            await conv.get_response()
                            link = f"https://t.me/addstickers/{curr_short}"
                            success = True
                        else:
                            await conv.send_message("/cancel")
                            await status.edit(f"❌ **Unknown error from @Stickers:**\n`{r1.text}`")
                            if os.path.exists(downloaded_file):
                                os.remove(downloaded_file)
                            return
        except asyncio.TimeoutError:
            await event.client.send_message("@Stickers", "/cancel")
            await status.edit("❌ **Error:** `@Stickers` bot took too long to respond. The operation was cancelled safely.")
        except Exception as e:
            await event.client.send_message("@Stickers", "/cancel")
            await status.edit(f"❌ **An unexpected error occurred during stealing:** `{str(e)}`")

        if os.path.exists(downloaded_file):
            os.remove(downloaded_file)

        if success:
            await status.edit(f"✅ **Sticker stolen successfully!**\n\n📦 **Pack:** [Click Here]({link})\n👤 **Owner:** @netcorexp", link_preview=False)
            try:
                if Config.LOG_CHAT_ID:
                    await event.client.send_message(Config.LOG_CHAT_ID, f"🎨 **Sticker Stolen!**\n📦 **Pack Link:** {link}")
            except Exception as e:
                pass
        elif "Error" not in status.text:
            await status.edit("❌ **Failed to steal sticker. Tried multiple pack volumes but failed.**")

    @CipherElite.on(events.NewMessage(pattern=r"^\.stealpack(?:\s+(.*))?$"))
    @rishabh()
    async def kang_pack(event):
        """Steals an entire sticker pack."""
        import re
        input_str = event.pattern_match.group(1)
        reply = await event.get_reply_message()
        sticker_set = None
        custom_name = None

        if input_str and "t.me/addstickers/" in input_str:
            match = re.search(r'(?:https?://)?t\.me/addstickers/([a-zA-Z0-9_]+)', input_str)
            if match:
                pack_shortname = match.group(1)
                sticker_set = InputStickerSetShortName(short_name=pack_shortname)
                rest = input_str.replace(match.group(0), "").strip()
                custom_name = rest if rest else None
            else:
                await event.reply("❌ **Invalid sticker pack link provided!**")
                return
        elif reply and reply.document:
            for attr in reply.document.attributes:
                if isinstance(attr, DocumentAttributeSticker):
                    sticker_set = attr.stickerset
                    break
            custom_name = input_str
        else:
            await event.reply("❌ **Please reply to a sticker or provide a valid t.me/addstickers/ link!**")
            return

        if not sticker_set:
            await event.reply("❌ **Could not find sticker set information.**")
            return

        status = await event.reply("🔄 **Fetching pack details...**")
        
        try:
            pack = await event.client(GetStickerSetRequest(stickerset=sticker_set, hash=0))
        except Exception as e:
            await status.edit(f"❌ **Error fetching pack:** `{str(e)}`")
            return
        
        try:
            user = await event.client.get_me()
            base_name = custom_name.strip() if custom_name else str(pack.set.title)
            clean_name = re.sub(r'[^a-zA-Z0-9]', '', base_name)
            if not clean_name:
                clean_name = "pack"
                
            clean_name = clean_name[:30]
            
            pack_title = f"{base_name[:40]} @netcorexp"
            if custom_name:
                short_name = f"prdx_{clean_name}_{user.id}"
            else:
                short_name = f"prdx_pk_{clean_name}_{user.id}"

            is_anim = getattr(pack.set, 'animated', False)
            is_vid = getattr(pack.set, 'videos', False)
            is_emoji = getattr(pack.set, 'emojis', False)

            if not is_anim and not is_vid and getattr(pack, 'documents', None):
                for d in pack.documents:
                    if d.mime_type == "application/x-tgsticker":
                        is_anim = True
                        break
                    elif d.mime_type == "video/webm":
                        is_vid = True
                        break

            pack_type_msg = ""
            if is_emoji:
                pack_title += " Emoji"
                short_name += "_emj"
                cmd_new = "/newemojipack"
                if is_anim:
                    pack_type_msg = "Animated"
                elif is_vid:
                    pack_type_msg = "Video"
                else:
                    pack_type_msg = "Static"
            elif is_anim:
                pack_title += " Anim"
                short_name += "_anim"
                cmd_new = "/newanimated"
            elif is_vid:
                pack_title += " Vid"
                short_name += "_vid"
                cmd_new = "/newvideo"
            else:
                cmd_new = "/newpack"

            safe_title = str(pack.set.title).replace('`', '')
            limit = getattr(pack.set, 'count', len(pack.documents))
            eta_seconds = limit * 2.5 # ~2.5s per sticker
        except Exception as e:
            await status.edit(f"❌ **CRITICAL ERROR (Setup):** `{str(e)}`")
            return
        
        success_count = 0
        link = ""
        
        try:
            await status.edit(f"🔄 **Stealing pack:** `{safe_title}`\n"
                              f"📊 **Total stickers:** `{limit}`\n"
                              f"⏳ **ETA:** `~{int(eta_seconds)}s`\n"
                              f"🛡️ **Status:** Waiting securely between requests...")
                              
            async with event.client.conversation("@Stickers", timeout=90) as conv:
                curr_title = f"{pack_title}"
                curr_short = f"{short_name}"
                
                await conv.send_message("/addsticker")
                resp = await conv.get_response()
                
                is_new = False
                if "choose the sticker pack" not in resp.text.lower():
                    is_new = True
                    await conv.send_message("/cancel")
                    await conv.get_response()
                    await conv.send_message(cmd_new)
                    r_type = await conv.get_response() # How to call it OR type of emoji pack
                    if cmd_new == "/newemojipack" and "choose the type" in r_type.text.lower():
                        await conv.send_message(pack_type_msg)
                        await conv.get_response()
                    await conv.send_message(curr_title)
                    await conv.get_response() # Send sticker
                else:
                    await conv.send_message(curr_short)
                    r_choose = await conv.get_response()
                    if "Invalid pack" in r_choose.text or "does not exist" in r_choose.text:
                        is_new = True
                        await conv.send_message("/cancel")
                        await conv.get_response()
                        await conv.send_message(cmd_new)
                        r_type = await conv.get_response() # How to call it OR type of emoji pack
                        if cmd_new == "/newemojipack" and "choose the type" in r_type.text.lower():
                            await conv.send_message(pack_type_msg)
                            await conv.get_response()
                        await conv.send_message(curr_title)
                        await conv.get_response() # Send sticker
                    elif "send me the sticker" not in r_choose.text.lower() and "send me the custom emoji" not in r_choose.text.lower():
                        await conv.send_message("/cancel")
                        await status.edit(f"❌ **Error from @Stickers:**\n`{r_choose.text}`")
                        return

                for i, doc in enumerate(pack.documents[:120]): # 120 is max allowed per pack
                    try:
                        # Only edit status every 5 stickers to prevent FloodWaitError on message edit
                        if i % 5 == 0 or i == limit - 1:
                            await status.edit(f"⏳ **Stealing sticker {i+1}/{limit}...**\n🛡️ Safely pacing requests.\n*(Status updates every 5 stickers to prevent bans)*")
                    except Exception:
                        pass
                    
                    # Get emoji
                    emoji = "🤔"
                    for attr in doc.attributes:
                        if isinstance(attr, DocumentAttributeSticker):
                            if attr.alt:
                                emoji = attr.alt
                            break
                    
                    downloaded_file = None
                    try:
                        from telethon.utils import get_extension
                        file_ext = get_extension(doc)
                        if not file_ext:
                            if is_anim: file_ext = ".tgs"
                            elif is_vid: file_ext = ".webm"
                            else: file_ext = ".webp"
                            
                        # Download with lenient timeout
                        downloaded_file = await asyncio.wait_for(
                            event.client.download_media(doc, "kang_pack_media" + file_ext),
                            timeout=60
                        )
                        
                        # Upload with lenient timeout to survive FloodWaits
                        await asyncio.wait_for(
                            conv.send_file(downloaded_file, force_document=True),
                            timeout=60
                        )
                        
                        r = await conv.get_response()
                        
                        if "whoa" in r.text.lower() or "wait" in r.text.lower() or "too fast" in r.text.lower():
                            import re
                            match = re.search(r'(\d+)\s*(s|sec|minute|m)', r.text.lower())
                            wait_time = 15
                            if match:
                                val = int(match.group(1))
                                wait_time = val * 60 if match.group(2).startswith('m') else val
                            await status.edit(f"⏳ **Rate limited by @Stickers!** Waiting `{wait_time}s`... (Sticker {i+1}/{limit})")
                            await asyncio.sleep(wait_time + 2)
                            await conv.send_file(downloaded_file, force_document=True)
                            r = await conv.get_response()

                        if "invalid" in r.text.lower():
                            if downloaded_file and os.path.exists(downloaded_file):
                                os.remove(downloaded_file)
                            continue
                        
                        # Emoji
                        await conv.send_message(emoji)
                        r_emoji = await conv.get_response()
                        
                        if "whoa" in r_emoji.text.lower() or "wait" in r_emoji.text.lower() or "too fast" in r_emoji.text.lower():
                            import re
                            match = re.search(r'(\d+)\s*(s|sec|minute|m)', r_emoji.text.lower())
                            wait_time = 15
                            if match:
                                val = int(match.group(1))
                                wait_time = val * 60 if match.group(2).startswith('m') else val
                            await status.edit(f"⏳ **Rate limited by @Stickers!** Waiting `{wait_time}s`... (Sticker {i+1}/{limit})")
                            await asyncio.sleep(wait_time + 2)
                            await conv.send_message(emoji)
                            r_emoji = await conv.get_response()

                        # Prevent going over standard limit
                        if "limit reached" in r_emoji.text.lower() or "120" in r_emoji.text:
                            if downloaded_file and os.path.exists(downloaded_file):
                                os.remove(downloaded_file)
                            break
                        
                        success_count += 1
                    except asyncio.TimeoutError:
                        if downloaded_file and os.path.exists(downloaded_file):
                            os.remove(downloaded_file)
                        break # Break loop and try to publish what we have
                    except Exception:
                        if downloaded_file and os.path.exists(downloaded_file):
                            os.remove(downloaded_file)
                        break
                        
                    if downloaded_file and os.path.exists(downloaded_file):
                        os.remove(downloaded_file)
                        
                    # SLEEP to prevent floodwaits
                    await asyncio.sleep(2)

                # Check if we stole at least 40% or if we got everything possible
                if success_count > 0 and (success_count >= (limit * 0.4) or success_count == limit):
                    if is_new:
                        await conv.send_message("/publish")
                        await conv.get_response()
                        await conv.send_message("/skip")
                        await conv.get_response()
                        await conv.send_message(curr_short)
                        r_short = await conv.get_response()
                        
                        if "already taken" in r_short.text:
                            await conv.send_message("/cancel")
                            await status.edit(f"❌ **Short name taken! Try another name.**")
                            return
                    else:
                        await conv.send_message("/done")
                        await conv.get_response()

                    link = f"https://t.me/addstickers/{curr_short}"
                else:
                    await conv.send_message("/cancel")
                    try:
                        await status.edit(f"❌ **Cancelled:** `@Stickers` bot timed out early. Only `{success_count}/{limit}` stickers were processed (less than 40%).")
                    except Exception:
                        await event.reply(f"❌ **Cancelled:** `@Stickers` bot timed out early. Only `{success_count}/{limit}` stickers were processed (less than 40%).")
                    return
                
        except asyncio.TimeoutError:
            await event.client.send_message("@Stickers", "/cancel")
            try:
                await status.edit("❌ **Error:** `@Stickers` bot took too long to respond. Saved what was done and cancelled the rest.")
            except Exception:
                await event.reply("❌ **Error:** `@Stickers` bot took too long to respond. Saved what was done and cancelled the rest.")
            return
        except Exception as e:
            await event.client.send_message("@Stickers", "/cancel")
            try:
                await status.edit(f"❌ **An unexpected error occurred during pack steal:** `{str(e)}`\nThe operation was safely cancelled.")
            except Exception:
                await event.reply(f"❌ **An unexpected error occurred during pack steal:** `{str(e)}`\nThe operation was safely cancelled.")
            return

        await status.edit(f"✅ **Pack stolen successfully!**\n\n"
                          f"📊 **Stickers copied:** `{success_count}/{limit}`\n"
                          f"📦 **Pack:** [Click Here]({link})\n"
                          f"👤 **Owner:** @netcorexp", link_preview=False)
        
        try:
            if Config.LOG_CHAT_ID:
                await event.client.send_message(Config.LOG_CHAT_ID, f"🎨 **Full Pack Stolen!**\n📊 **Stickers copied:** `{success_count}/{limit}`\n📦 **Pack Link:** {link}")
        except Exception as e:
            pass

    @CipherElite.on(events.NewMessage(pattern=r"\.stickerinfo$"))
    @rishabh()
    async def sticker_info(event):
        """Displays info about the replied sticker."""
        reply = await event.get_reply_message()
        if not reply or not reply.document:
            await event.reply("❌ **Please reply to a sticker!**")
            return

        is_sticker = False
        emoji = "N/A"
        pack_name = "N/A"
        pack_short = "N/A"

        for attr in reply.document.attributes:
            if isinstance(attr, DocumentAttributeSticker):
                is_sticker = True
                if attr.alt:
                    emoji = attr.alt
                if attr.stickerset:
                    if isinstance(attr.stickerset, InputStickerSetID):
                        pack_name = str(attr.stickerset.id)
                    elif isinstance(attr.stickerset, InputStickerSetShortName):
                        pack_short = attr.stickerset.short_name
                break
        
        if not is_sticker:
            await event.reply("❌ **The replied message is not a sticker!**")
            return
            
        file_size = reply.document.size
        mime = reply.document.mime_type
        doc_id = reply.document.id
        
        info = (
            f"ℹ️ **PARADOX Sticker Info** ℹ️\n\n"
            f"🆔 **Sticker ID:** `{doc_id}`\n"
            f"😀 **Emoji:** {emoji}\n"
            f"📦 **Pack Shortname:** `{pack_short}`\n"
            f"📁 **Size:** `{file_size} bytes`\n"
            f"🎭 **Type:** `{mime}`\n"
        )
        await event.reply(info)
