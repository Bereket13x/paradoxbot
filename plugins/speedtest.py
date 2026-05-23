import os
import platform
import subprocess
import urllib.request
import tarfile
import zipfile
import json
import time
import asyncio
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
        ".speedtest file",
        ".speedtest link"
    ]
    desc = "Botserver's speedtest by ookla."
    add_handler("speedtest", commands, desc)

def install_ookla_cli():
    system = platform.system()
    bin_name = "speedtest.exe" if system == "Windows" else "speedtest"
    bin_path = os.path.join(os.path.dirname(__file__), bin_name)
    
    if os.path.exists(bin_path):
        return bin_path
        
    if system == "Linux":
        url = "https://install.speedtest.net/app/cli/ookla-speedtest-1.2.0-linux-x86_64.tgz"
        tgz_path = os.path.join(os.path.dirname(__file__), "speedtest.tgz")
        urllib.request.urlretrieve(url, tgz_path)
        with tarfile.open(tgz_path, "r:gz") as tar:
            tar.extract("speedtest", path=os.path.dirname(__file__))
        os.remove(tgz_path)
    elif system == "Windows":
        url = "https://install.speedtest.net/app/cli/ookla-speedtest-1.2.0-win64.zip"
        zip_path = os.path.join(os.path.dirname(__file__), "speedtest.zip")
        urllib.request.urlretrieve(url, zip_path)
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extract("speedtest.exe", path=os.path.dirname(__file__))
        os.remove(zip_path)
    else:
        raise Exception("Unsupported OS for Ookla CLI auto-install.")
        
    if system != "Windows":
        os.chmod(bin_path, 0o755)
        
    return bin_path

def run_ookla_speedtest():
    start = time.time()
    bin_path = install_ookla_cli()
    
    proc = subprocess.run(
        [bin_path, "--accept-license", "--accept-gdpr", "--format=json"],
        capture_output=True, text=True
    )
    
    if proc.returncode != 0:
        raise Exception(f"Ookla CLI Error: {proc.stderr.strip() or proc.stdout.strip()}")
        
    data = json.loads(proc.stdout)
    end = time.time()
    ms = round(end - start, 2)
    
    dl_bps = data['download']['bandwidth'] * 8
    ul_bps = data['upload']['bandwidth'] * 8
    ping_ms = data['ping']['latency']
    isp = data['isp']
    share_url = data['result']['url'] + ".png"
    
    return ms, dl_bps, ul_bps, ping_ms, isp, share_url

@CipherElite.on(events.NewMessage(pattern=r"\.speedtest(?:\s|$)([\s\S]*)"))
@rishabh()
async def speedtest_cmd(event):
    input_str = event.pattern_match.group(1).strip().lower()
    as_text = False
    as_document = False
    as_link = False
    if input_str == "file":
        as_document = True
    elif input_str == "image":
        as_document = False
    elif input_str == "text":
        as_text = True
    elif input_str == "link":
        as_link = True

    catevent = await event.reply("`Calculating internet speed using Official Ookla CLI. Please wait...`")
    
    try:
        loop = asyncio.get_event_loop()
        ms, dl_bps, ul_bps, ping_time, i_s_p, speedtest_image = await loop.run_in_executor(None, run_ookla_speedtest)
        
        reply_msg_id = event.reply_to_msg_id or event.id

        if as_link:
            raw_url = speedtest_image.replace(".png", "")
            await catevent.edit(
                f"🚀 **SpeedTest Results**\n\n"
                f"⬇️ **Download:** `{convert_from_bytes(dl_bps)}`\n"
                f"⬆️ **Upload:** `{convert_from_bytes(ul_bps)}`\n"
                f"🏓 **Ping:** `{ping_time} ms`\n"
                f"🌐 **ISP:** `{i_s_p}`\n\n"
                f"🔗 **Result Link:** [Click Here to View]({raw_url})"
            )
        elif as_text:
            await catevent.edit(
                f"""`SpeedTest completed in {ms} seconds`

`Download: {convert_from_bytes(dl_bps)} (or) {round(dl_bps / 8e6, 2)} MB/s`
`Upload: {convert_from_bytes(ul_bps)} (or) {round(ul_bps / 8e6, 2)} MB/s`
`Ping: {ping_time} ms`
`Internet Service Provider: {i_s_p}`"""
            )
        else:
            await event.client.send_file(
                event.chat_id,
                speedtest_image,
                caption=f"**SpeedTest** completed in {ms} seconds\n\n**ISP:** `{i_s_p}`",
                force_document=as_document,
                reply_to=reply_msg_id,
                allow_cache=False,
            )
            await catevent.delete()
            
    except Exception as exc:
        await catevent.edit(f"`Speedtest failed!`\n\n**Error:** `{str(exc)}`")

