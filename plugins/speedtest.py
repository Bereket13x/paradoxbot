# =============================================================================
#  PARADOX Userbot Plugin
#
#  Plugin Name:    speedtest
#  Description:    Botserver's speedtest by ookla.
# =============================================================================

import time
import asyncio
import subprocess
import json
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

import urllib.request
import re

def run_fast_speedtest():
    start_total = time.time()
    
    try:
        req = urllib.request.Request('https://fast.com/', headers={'User-Agent': 'Mozilla/5.0'})
        html = urllib.request.urlopen(req, timeout=10).read().decode()
        js_url = 'https://fast.com' + re.search(r'<script src="(.*?)">', html).group(1)
        js = urllib.request.urlopen(urllib.request.Request(js_url, headers={'User-Agent': 'Mozilla/5.0'}), timeout=10).read().decode()
        token = re.search(r'token:"(.*?)"', js).group(1)
        
        url = f'https://api.fast.com/netflix/speedtest/v2?https=true&token={token}&urlCount=3'
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        resp = json.loads(urllib.request.urlopen(req, timeout=10).read().decode())
        
        client_isp = resp.get('client', {}).get('isp', 'Unknown ISP')
        client_country = resp.get('client', {}).get('location', {}).get('country', 'Unknown')
        
        target_url = resp['targets'][0]['url']
        
        ping_start = time.time()
        urllib.request.urlopen(urllib.request.Request(target_url, headers={'User-Agent': 'Mozilla/5.0'}), timeout=10)
        ping_ms = round((time.time() - ping_start) * 1000, 2)
        
        dl_start = time.time()
        data = urllib.request.urlopen(urllib.request.Request(target_url + '&bytes=25000000', headers={'User-Agent': 'Mozilla/5.0'}), timeout=15).read()
        dl_end = time.time()
        
        download_speed_bps = len(data) * 8 / (dl_end - dl_start)
        
        ms = round(time.time() - start_total, 2)
        
        return ms, download_speed_bps, ping_ms, client_isp, client_country
    except Exception as e:
        raise Exception(f"Fast.com API Error: {e}")

@CipherElite.on(events.NewMessage(pattern=r"\.speedtest(?:\s|$)([\s\S]*)"))
@rishabh()
async def speedtest_cmd(event):
    catevent = await event.reply("`Calculating internet speed using Fast.com (Netflix API). Please wait...`")
    
    try:
        loop = asyncio.get_event_loop()
        ms, dl_bps, ping_time, i_s_p, country = await loop.run_in_executor(None, run_fast_speedtest)
        
        text = f"""`⚡ Fast.com SpeedTest completed in {ms} seconds`

**📥 Download:** `{convert_from_bytes(dl_bps)} (or) {round(dl_bps / 8e6, 2)} MB/s`
**🏓 Ping:** `{ping_time} ms`
**🏢 ISP:** `{i_s_p} ({country})`

_Note: Fast.com API does not support Upload tests or Image sharing._"""

        await catevent.edit(text)
            
    except Exception as exc:
        await catevent.edit(f"`Speedtest failed!`\n\n**Error:** `{str(exc)}`")
