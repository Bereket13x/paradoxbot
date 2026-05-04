import os
import requests
from telethon import events
from telethon.errors.rpcerrorlist import YouBlockedUserError
try:
    from googlesearch import search
except ImportError:
    search = None
    
from utils.utils import CipherElite
from utils.decorators import rishabh
from plugins.bot import add_handler

def init(client_instance):
    commands = [
        ".gs <query> - Google Search",
        ".gis <query> - Google Image Search",
        ".reverse - Google Reverse Image Search (reply to media)",
        ".google <query> - Get a Google Search button"
    ]
    description = "🔍 Search Tools - Google, Images, Reverse Search"
    add_handler("search", commands, description)


async def register_commands():
    @CipherElite.on(events.NewMessage(pattern=r"^\.gs(?:\s+(.+))?$"))
    @rishabh()
    async def gsearch(event):
        query = event.pattern_match.group(1)
        if not query:
            return await event.reply("❌ **Give me something to search!**\n`Example: .gs PARADOX Userbot`")
        
        status = await event.reply("🔍 `Searching Google...`")
        
        if not search:
            return await status.edit("❌ **Error: googlesearch-python is not installed.**\n`pip install googlesearch-python`")

        try:
            results = list(search(query, num_results=5, advanced=True))
            if not results:
                return await status.edit("❌ **No results found!**")
                
            msg = f"🔍 **Search Query:** `{query}`\n\n**Results:**\n"
            for r in results:
                msg += f"👉 **[{r.title}]({r.url})**\n`{r.description}`\n\n"
                
            await status.edit(msg, link_preview=False)
        except Exception as e:
            await status.edit(f"❌ **Error:**\n`{str(e)}`")


    @CipherElite.on(events.NewMessage(pattern=r"^\.gis(?:\s+(.+))?$"))
    @rishabh()
    async def gis(event):
        query = event.pattern_match.group(1)
        if not query:
            return await event.reply("❌ **Give me something to search!**\n`Example: .gis cat`")
        
        status = await event.reply("🖼 `Searching Images...`")
        
        try:
            results = await event.client.inline_query("@pic", query)
            if results:
                await results[0].click(event.chat_id, reply_to=event.reply_to_msg_id or event.id, hide_via=True)
                await event.delete()
            else:
                await status.edit("❌ **No images found!**")
        except Exception as e:
            await status.edit(f"❌ **Error:**\n`{str(e)}`")


    @CipherElite.on(events.NewMessage(pattern=r"^\.(grs|reverse)$"))
    @rishabh()
    async def reverse_search(event):
        reply = await event.get_reply_message()
        if not reply or not reply.media:
            return await event.reply("❌ **Reply to an image or media to reverse search!**")

        status = await event.reply("🔄 `Downloading image...`")
        
        try:
            file_path = await event.client.download_media(reply, "temp_reverse.jpg")
            if not file_path:
                return await status.edit("❌ **Failed to download media.**")

            await status.edit("📤 `Uploading to Catbox for Reverse Search...`")
            
            with open(file_path, "rb") as f:
                response = requests.post(
                    "https://catbox.moe/user/api.php",
                    data={"reqtype": "fileupload"},
                    files={"fileToUpload": f}
                )
            
            os.remove(file_path)

            if response.status_code == 200:
                catbox_url = response.text.strip()
                lens_url = f"https://lens.google.com/uploadbyurl?url={catbox_url}"
                yandex_url = f"https://yandex.com/images/search?rpt=imageview&url={catbox_url}"
                
                caption = (
                    "**🖼 Reverse Image Search Results**\n\n"
                    f"🔍 [Search with Google Lens]({lens_url})\n"
                    f"🔍 [Search with Yandex]({yandex_url})"
                )
                await status.edit(caption, link_preview=False)
            else:
                await status.edit("❌ **Failed to upload image for reverse search.**")
                
        except Exception as e:
            await status.edit(f"❌ **Error:**\n`{str(e)}`")


    @CipherElite.on(events.NewMessage(pattern=r"^\.google(?:\s+(.+))?$"))
    @rishabh()
    async def google_btn(event):
        query = event.pattern_match.group(1)
        if not query:
            return await event.reply("❌ **What should I search? Give a search query.**")
            
        status = await event.reply("🔍 `Generating Google link...`")
        try:
            inline_query = f"#12{query}"
            results = await event.client.inline_query("@StickerizerBot", inline_query)
            if results:
                await results[0].click(event.chat_id, reply_to=event.reply_to_msg_id or event.id, hide_via=True)
                await event.delete()
            else:
                await status.edit("❌ **Could not generate Google button.**")
        except Exception as e:
            await status.edit(f"❌ **Error:** `{str(e)}`")
