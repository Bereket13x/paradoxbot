import os
import re
from datetime import datetime
from search_engine_parser import BingSearch, GoogleSearch, YahooSearch
from search_engine_parser.core.exceptions import NoResultsOrTrafficError
from telethon import events

from utils.utils import CipherElite
from utils.decorators import rishabh
from utils.google_tools import GooglePic, chromeDriver
from plugins.bot import add_handler
from config.config import Config

# Stub for bot log
BOTLOG = True
BOTLOG_CHATID = int(os.getenv("LOG_CHAT_ID", "0"))

def init(client_instance):
    commands = [
        ".gs <query>",
        ".gis <query>",
        ".grs (reply to media)",
        ".reverse <1-10>",
        ".google <query>"
    ]
    add_handler("search", commands, "Google search tools")


async def register_commands():

    @CipherElite.on(events.NewMessage(pattern=r"^\.gs ([\s\S]*)"))
    @rishabh()
    async def gsearch(event):
        catevent = await event.reply("`searching........`")
        match = event.pattern_match.group(1)
        page = re.findall(r"-p\d+", match)
        lim = re.findall(r"-l\d+", match)
        try:
            page = page[0]
            page = page.replace("-p", "")
            match = match.replace(f"-p{page}", "")
        except IndexError:
            page = 1
        try:
            lim = lim[0]
            lim = lim.replace("-l", "")
            match = match.replace(f"-l{lim}", "")
            lim = int(lim)
            if lim <= 0:
                lim = 5
        except IndexError:
            lim = 5
        
        smatch = match.replace(" ", "+")
        search_args = str(smatch), page
        gsearch = GoogleSearch()
        bsearch = BingSearch()
        ysearch = YahooSearch()
        try:
            gresults = await gsearch.async_search(*search_args)
        except NoResultsOrTrafficError:
            try:
                gresults = await bsearch.async_search(*search_args)
            except NoResultsOrTrafficError:
                try:
                    gresults = await ysearch.async_search(*search_args)
                except Exception as e:
                    return await catevent.edit(f"**Error:**\n`{e}`")
        msg = ""
        for i in range(lim):
            if i > len(gresults["links"]):
                break
            try:
                title = gresults["titles"][i]
                link = gresults["links"][i]
                desc = gresults["descriptions"][i]
                msg += f"👉[{title}]({link})\n`{desc}`\n\n"
            except IndexError:
                break
        await catevent.edit(
            "**Search Query:**\n`" + match + "`\n\n**Results:**\n" + msg,
            link_preview=False,
        )
        if BOTLOG and BOTLOG_CHATID:
            try:
                await event.client.send_message(
                    BOTLOG_CHATID,
                    f"Google Search query `{match}` was executed successfully",
                )
            except Exception: pass


    @CipherElite.on(events.NewMessage(pattern=r"^\.gis ([\s\S]*)"))
    @rishabh()
    async def gis(event):
        "To search in google and send result in picture."
        # The user pasted this as an empty function. We will keep it exactly as is if that's what they want.
        # However, to make it work 'just like catuserbots', since Catuserbot uses @pic here usually or another plugin:
        await event.reply("`gis functionality not fully provided in original snippet.`")


    @CipherElite.on(events.NewMessage(pattern=r"^\.grs$"))
    @rishabh()
    async def grs(event):
        "Google Reverse Search"
        # The logic is handled by the reverse command pattern below


    @CipherElite.on(events.NewMessage(pattern=r"^\.(grs|reverse)(?:\s|$)([\s\S]*)"))
    @rishabh()
    async def reverse(event):
        start = datetime.now()
        reply_to = event.reply_to_msg_id or event.id
        cmd = event.pattern_match.group(1)
        message = await event.get_reply_message()
        limit = event.pattern_match.group(2) or "3"
        
        if int(limit) < 1 or int(limit) > 10:
            return await event.reply("`Give a limit between 1-10`")
        if not message or not message.media:
            return await event.reply("`Reply to media...`")
            
        os.makedirs("./temp", exist_ok=True)
        photo_path = await event.client.download_media(message, "./temp/reverse.png")
        if not photo_path:
            return await event.reply("`Unable to extract image from the replied message..`")
            
        catevent = await event.reply("`Processing...`")
        flag = cmd != "grs"
        data = GooglePic.reverse_data(photo_path, flag)
        
        if data["error"]:
            return await catevent.edit(data["error"])
        if data["lens"] is None:
            return await catevent.edit("`Couldn't find any reverse data..`")
            
        outfile = "./temp/reverse.png"
        imagelist, captionlist, gifstring = [], [], ""
        
        if cmd == "grs":
            pic, _ = await chromeDriver.get_screenshot(data["lens"], catevent)
            if pic:
                with open(outfile, "wb") as file:
                    file.write(pic)
        else:
            if data["image_set"]:
                for checker, item in enumerate(data["image_set"], 1):
                    url = item.image if item.image.endswith((".jpg", ".jpeg", ".png", ".gif")) else item.site
                    try:
                        # Upload silently to BOTLOG to get media, then append
                        if BOTLOG_CHATID:
                            try:
                                image = await event.client.send_file(BOTLOG_CHATID, url, silent=True)
                                if url.endswith(".gif"):
                                    # unsavegif is complicated, we skip for userbot
                                    giflink = f"https://t.me/c/{str(BOTLOG_CHATID).replace('-100', '')}/{image.id}"
                                    gifstring += f'<b><a href="{giflink}">Gif{checker}</a></b>  '
                                else:
                                    imagelist.append(image.media)
                                    captionlist.append("")
                                    await image.delete()
                            except Exception: pass
                        await catevent.edit(f"**📥 Downloaded : {checker}/{limit}**")
                        if checker >= int(limit):
                            break
                    except Exception:
                        pass

        end = datetime.now()
        ms = (end - start).seconds
        caption = f'<b>➥ Google Reverse Search:</b>  <code>{data["title"]}</code>\n<b>➥ View Source: <a href="{data["google"]}">Google Image</a></b>\n<b>➥ View Similar: <a href="{data["lens"]}">Google Lens</a> </b>(Desktop)\n<b>➥ Time Taken:</b>  <code>{ms} seconds</code>'
        
        if not imagelist:
            imagelist.append(outfile)
            captionlist.append("")
        if gifstring:
            caption = caption + "\n\n<b>➥ Found Gif:</b>  " + gifstring
            
        captionlist[-1] = caption
        await catevent.delete()
        await event.client.send_file(
            event.chat_id,
            imagelist,
            caption=captionlist,
            parse_mode="html",
            reply_to=reply_to,
        )
        if os.path.exists(outfile):
            os.remove(outfile)


    @CipherElite.on(events.NewMessage(pattern=r"^\.google(?:\s|$)([\s\S]*)"))
    @rishabh()
    async def google_search(event):
        input_str = event.pattern_match.group(1)
        reply_to_id = event.reply_to_msg_id or event.id
        if not input_str:
            return await event.reply("__What should i search? Give search query plox.__")
            
        input_str = input_str.strip()
        if len(input_str) > 195 or len(input_str) < 1:
            return await event.reply("__Plox your search query exceeds 200 characters or you search query is empty.__")
            
        query = f"#12{input_str}"
        try:
            results = await event.client.inline_query("@StickerizerBot", query)
            await results[0].click(event.chat_id, reply_to=reply_to_id, hide_via=True)
            await event.delete()
        except Exception as e:
            await event.reply(f"❌ **StickerizerBot error:** `{str(e)}`")
