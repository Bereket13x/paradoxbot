import os
import requests
import re
from telethon import events, Button
from telethon.errors.rpcerrorlist import YouBlockedUserError
try:
    from googlesearch import search
except ImportError:
    search = None
    
from utils.utils import CipherElite
from utils.decorators import rishabh
from plugins.bot import add_handler, bot
from config.config import Config

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
        
        url = f"https://www.bing.com/images/search?q={query.replace(' ', '+')}"
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        try:
            r = requests.get(url, headers=headers)
            urls = re.findall(r'murl&quot;:&quot;(.*?)&quot;', r.text)
            if not urls:
                return await status.edit("❌ **No images found!**")
                
            urls = list(set(urls))[:3]
            await event.client.send_file(
                event.chat_id,
                urls,
                caption=f"🖼 **Image Search**\n🔍 `{query}`",
                reply_to=event.reply_to_msg_id or event.id
            )
            await event.delete()
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

            await status.edit("📤 `Uploading image...`")
            
            with open(file_path, "rb") as f:
                response = requests.post("https://telegra.ph/upload", files={"file": f})
            
            os.remove(file_path)

            if response.status_code == 200:
                data = response.json()
                if isinstance(data, list) and "src" in data[0]:
                    img_url = "https://telegra.ph" + data[0]["src"]
                    lens_url = f"https://lens.google.com/uploadbyurl?url={img_url}"
                    yandex_url = f"https://yandex.com/images/search?rpt=imageview&url={img_url}"
                    
                    caption = (
                        "**🖼 Reverse Image Search Results**\n\n"
                        f"🔍 [Search with Google Lens]({lens_url})\n"
                        f"🔍 [Search with Yandex]({yandex_url})"
                    )
                    await status.edit(caption, link_preview=False)
                else:
                    await status.edit("❌ **Failed to upload image to telegraph.**")
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
            results = await event.client.inline_query(Config.TG_BOT_USERNAME, f"google {query}")
            if results:
                await results[0].click(event.chat_id, reply_to=event.reply_to_msg_id or event.id, hide_via=True)
                await event.delete()
            else:
                await status.edit("❌ **Could not generate Google button.**")
        except Exception as e:
            await status.edit(f"❌ **Error:** `{str(e)}`")


if bot:
    @bot.on(events.InlineQuery(pattern=r"^google\s+(.+)"))
    async def inline_google(event):
        query = event.pattern_match.group(1)
        builder = event.builder
        url = f"https://www.google.com/search?q={query.replace(' ', '+')}"
        
        result = builder.article(
            title="Google Search",
            text=f"🔍 **Google Search**\n\n**Query:** `{query}`",
            buttons=[Button.url("Search Google", url)]
        )
        await event.answer([result], cache_time=1)
