# =============================================================================
#  PARADOX Userbot Plugin
#
#  Plugin Name:    speedtest
#  Description:    Botserver's speedtest by ookla.
# =============================================================================

from time import time
import asyncio
import speedtest
from telethon import events
from utils.utils import CipherElite
from utils.decorators import rishabh
from plugins.bot import add_handler

def convert_from_bytes(size):
    power = 2**10
    n = 0
    units = {0: "", 1: "Kbps", 2: "Mbps", 3: "Gbps", 4: "Tbps"}
    while size > power:
        size /= power
        n += 1
    return f"{round(size, 2)} {units[n]}"

def init(client):
    commands = [
        ".speedtest",
        ".speedtest text",
        ".speedtest image",
        ".speedtest file"
    ]
    desc = "Botserver's speedtest by ookla."
    add_handler("speedtest", commands, desc)

def run_speedtest():
    start = time()
    try:
        s = speedtest.Speedtest(secure=True)
        s.get_best_server()
    except Exception:
        # Bypassing the ping-based best server check, which usually causes the error
        try:
            s = speedtest.Speedtest(secure=True)
            s.get_servers()
            s._best = s.servers[min(s.servers.keys())][0]
        except Exception as e:
            raise Exception(f"Speedtest.net API is blocking or rate-limiting your bot's IP. Try again later. (Error: {e})")
    s.download()
    s.upload()
    end = time()
    ms = round(end - start, 2)
    
    response_dict = s.results.dict()
    share_link = s.results.share()
    
    return ms, response_dict, share_link

@CipherElite.on(events.NewMessage(pattern=r"\.speedtest(?:\s|$)([\s\S]*)"))
@rishabh()
async def speedtest_cmd(event):
    input_str = event.pattern_match.group(1).strip().lower()
    as_text = False
    as_document = False
    if input_str == "file":
        as_document = True
    elif input_str == "image":
        as_document = False
    elif input_str == "text":
        as_text = True

    catevent = await event.reply("`Calculating my internet speed. Please wait!`")
    
    try:
        loop = asyncio.get_event_loop()
        # Run synchronous blocking tasks in executor
        ms, response, speedtest_image = await loop.run_in_executor(None, run_speedtest)
        
        download_speed = response.get("download", 0)
        upload_speed = response.get("upload", 0)
        ping_time = response.get("ping", 0)
        client_infos = response.get("client", {})
        i_s_p = client_infos.get("isp", "Unknown")
        i_s_p_rating = client_infos.get("isprating", "Unknown")
        
        reply_msg_id = event.reply_to_msg_id or event.id

        if as_text:
            await catevent.edit(
                """`SpeedTest completed in {} seconds`

`Download: {} (or) {} MB/s`
`Upload: {} (or) {} MB/s`
`Ping: {} ms`
`Internet Service Provider: {}`
`ISP Rating: {}`""".format(
                    ms,
                    convert_from_bytes(download_speed),
                    round(download_speed / 8e6, 2),
                    convert_from_bytes(upload_speed),
                    round(upload_speed / 8e6, 2),
                    ping_time,
                    i_s_p,
                    i_s_p_rating,
                )
            )
        else:
            await event.client.send_file(
                event.chat_id,
                speedtest_image,
                caption=f"**SpeedTest** completed in {ms} seconds",
                force_document=as_document,
                reply_to=reply_msg_id,
                allow_cache=False,
            )
            await catevent.delete()
            
    except Exception as exc:
        await catevent.edit(f"`Speedtest failed!`\n\n**Error:** `{str(exc)}`")
