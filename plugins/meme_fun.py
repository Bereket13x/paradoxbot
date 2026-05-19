# =============================================================================
#  CipherElite Userbot Plugin
#
#  Plugin Name:    Meme Fun
#  Author:         CipherElite Plugins (Ported from CatUB)
#  Description:    Image manipulation / Text-to-Sticker memes.
# =============================================================================

import os
import random
import textwrap
import urllib.request
from io import BytesIO

import requests
from PIL import Image, ImageDraw, ImageFont
from telethon import events
from telethon.errors import BotInlineDisabledError, BotResponseTimeoutError

from plugins.bot import add_handler
from utils.utils import CipherElite
from utils.decorators import rishabh

def init(client):
    commands = [
        ".stcr <text>",
        ".quby <text>", ".blob <text>", ".kirby <text>",
        ".doge <text>", ".penguin <text>", ".gandhi <text>",
        ".honk <text>", ".twt <text>", ".glax <text>"
    ]
    desc = "Generate customized meme stickers and use inline fun bots."
    add_handler("meme_fun", commands, desc)

# ======= HELPER FUNCTIONS FOR PIL IMAGE PROCESSING =======

TMP_DIR = "/tmp/cipher_meme"
os.makedirs(TMP_DIR, exist_ok=True)
DEFAULT_FONT_PATH = os.path.join(TMP_DIR, "ArialUnicodeMS.ttf")

def get_default_font():
    if not os.path.exists(DEFAULT_FONT_PATH):
        font_url = "https://github.com/TgCatUB/CatUserbot-Resources/raw/master/Resources/Spotify/ArialUnicodeMS.ttf"
        try:
            urllib.request.urlretrieve(font_url, DEFAULT_FONT_PATH)
        except Exception:
            pass
    return DEFAULT_FONT_PATH

def download_image(url):
    response = requests.get(url)
    img = Image.open(BytesIO(response.content)).convert("RGBA")
    return img

def render_meme_text(img, text, position=(0,0), font_size=50, text_wrap=15, 
                     align="center", fill="white", stroke_fill="black", stroke_width=2):
    font_path = get_default_font()
    
    try:
        font = ImageFont.truetype(font_path, font_size)
    except IOError:
        font = ImageFont.load_default()

    draw = ImageDraw.Draw(img)
    wrapped_lines = textwrap.wrap(text, width=text_wrap)
    wrapped_text = "\n".join(wrapped_lines)
    
    # Starting coordinates
    x, y = position
    
    draw.multiline_text(
        (x, y), wrapped_text, font=font, fill=fill, align=align,
        stroke_width=stroke_width, stroke_fill=stroke_fill
    )
    
    return img

def save_as_webp(img):
    output = BytesIO()
    output.name = "meme.webp"
    img.save(output, format="WEBP")
    output.seek(0)
    return output

async def run_inline_bot(event, bot_username, query):
    catevent = await event.edit("`Contacting bot...`")
    try:
        results = await event.client.inline_query(bot_username, query)
        if not results:
            return await catevent.edit("`No response from bot.`")
        await results[0].click(event.chat_id, reply_to=event.reply_to_msg_id)
        await catevent.delete()
    except Exception as e:
        await catevent.edit(f"**Error:** `{e}`")


# ================== INLINE BOTS ==================

@CipherElite.on(events.NewMessage(pattern=r"\.honk(?:\s+(.+))?"))
@rishabh()
async def honk_cmd(event):
    text = event.pattern_match.group(1)
    if not text and event.is_reply:
        text = (await event.get_reply_message()).message
    if not text:
        return await event.edit("__What is honk supposed to say? Give some text.__")
    await run_inline_bot(event, "@honka_says_bot", text)

@CipherElite.on(events.NewMessage(pattern=r"\.twt(?:\s+(.+))?"))
@rishabh()
async def twt_cmd(event):
    text = event.pattern_match.group(1)
    if not text and event.is_reply:
        text = (await event.get_reply_message()).message
    if not text:
        return await event.edit("__What am I supposed to Tweet? Give some text.__")
    await run_inline_bot(event, "@TwitterStatusBot", text)

@CipherElite.on(events.NewMessage(pattern=r"\.glax(?:\s+(.+))?"))
@rishabh()
async def glax_cmd(event):
    text = event.pattern_match.group(1)
    if not text and event.is_reply:
        text = (await event.get_reply_message()).message
    if not text:
        return await event.edit("__What is glax supposed to scream? Give text.__")
    await run_inline_bot(event, "@GlaxScremBot", text)


# ================== TEXT STICKERS ==================

@CipherElite.on(events.NewMessage(pattern=r"\.stcr(?:\s+(.+))?"))
@rishabh()
async def stcr(event):
    sticktext = event.pattern_match.group(1)
    if not sticktext and event.is_reply:
        sticktext = (await event.get_reply_message()).message
    if not sticktext:
        return await event.edit("`Need text to write..`")
        
    await event.edit("`Creating sticker...`")
    RGB = tuple(random.sample(range(255), 3))
    
    sticktext = "\n".join(textwrap.wrap(sticktext, width=10))
    image = Image.new("RGBA", (512, 512), (255, 255, 255, 0))
    draw = ImageDraw.Draw(image)
    fontsize = 150
    
    # Try fetching a random font URL safely, fallback to default
    try:
        res = requests.get("https://raw.githubusercontent.com/TgCatUB/CatUserbot-Resources/master/Resources/StickerFun/resources.txt", timeout=5)
        font_url = random.choice(res.json().get("fonts", []))
        font_data = requests.get(font_url, timeout=5).content
        font = ImageFont.truetype(BytesIO(font_data), size=fontsize)
    except Exception:
        font = ImageFont.truetype(get_default_font(), size=fontsize)

    # Scaling font down to fit 512x512
    while True:
        try:
            bbox = draw.textbbox((0,0), sticktext, font=font)
            width = bbox[2] - bbox[0]
            height = bbox[3] - bbox[1]
        except AttributeError:
            width, height = draw.textsize(sticktext, font=font)
        
        if width > 500 or height > 500:
            fontsize -= 5
            try:
                font = ImageFont.truetype(BytesIO(font_data), size=fontsize)
            except Exception:
                font = ImageFont.truetype(get_default_font(), size=fontsize)
        else:
            break

    draw.multiline_text(((512 - width) / 2, (512 - height) / 2 - 20), sticktext, font=font, fill=RGB, align="center")
    
    stream = save_as_webp(image)
    await event.client.send_file(event.chat_id, stream, reply_to=event.reply_to_msg_id, force_document=False)
    await event.delete()


@CipherElite.on(events.NewMessage(pattern=r"\.(quby|blob|kirby|doge|penguin|gandhi)(?:\s+(.+))?"))
@rishabh()
async def meme_sticker_handler(event):
    cmd = event.pattern_match.group(1).lower()
    text = event.pattern_match.group(2)
    
    if not text and event.is_reply:
        text = (await event.get_reply_message()).message
    if not text:
        return await event.edit(f"`What is {cmd} supposed to say?`")
        
    await event.edit("`Wait, processing.....`")
    
    # Template configurations
    templates = {
        "quby": {
            "url": "https://graph.org/file/09f4df5a129758a2e1c9c.jpg",
            "pos": (45, 10), "size": 50, "wrap": 15, "fill": "black", "stroke": "white", "stroke_w": 1, "align": "center"
        },
        "blob": {
            "url": "https://graph.org/file/2188367c8c5f43c36aa59.jpg",
            "pos": (150, 480), "size": 60, "wrap": 15, "fill": "black", "stroke": "white", "stroke_w": 0, "align": "center"
        },
        "kirby": {
            "url": "https://graph.org/file/2188367c8c5f43c36aa59.jpg",
            "pos": (150, 480), "size": 60, "wrap": 15, "fill": "black", "stroke": "white", "stroke_w": 0, "align": "center"
        },
        "doge": {
            "url": "https://graph.org/file/6f621b9782d9c925bd6c4.jpg",
            "pos": (20, 20), "size": 60, "wrap": 20, "fill": "black", "stroke": "white", "stroke_w": 2, "align": "left"
        },
        "penguin": {
            "url": "https://graph.org/file/ee1fc91bbaef2cc808c7c.png",
            "pos": (20, 20), "size": 70, "wrap": 20, "fill": "black", "stroke": "white", "stroke_w": 1, "align": "left"
        },
        "gandhi": {
            "url": "https://graph.org/file/3bebc56ee82cce4f300ce.jpg",
            "pos": (470, 20), "size": 70, "wrap": 15, "fill": "white", "stroke": "black", "stroke_w": 1, "align": "center"
        }
    }
    
    opts = templates[cmd]
    
    try:
        img = download_image(opts["url"])
        
        # Adjust some positioning for longer texts
        size = opts["size"] if len(text) < 60 else opts["size"] - 15
        
        final_img = render_meme_text(
            img, text, 
            position=opts["pos"], 
            font_size=size, 
            text_wrap=opts["wrap"],
            align=opts["align"],
            fill=opts["fill"],
            stroke_fill=opts["stroke"],
            stroke_width=opts["stroke_w"]
        )
        
        stream = save_as_webp(final_img)
        await event.client.send_file(event.chat_id, stream, reply_to=event.reply_to_msg_id, force_document=False)
        await event.delete()
        
    except Exception as e:
        await event.edit(f"**Error:** `{e}`")

