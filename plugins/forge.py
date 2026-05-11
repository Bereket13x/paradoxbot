# =============================================================================
#  PARADOX Userbot Plugin
#
#  Plugin Name:    FORGE — Advanced Sticker Creator
#  Description:    Next-level sticker creation with effects, text overlays,
#                  borders, glows, collages, and emoji art — all via PIL.
#  License:        MIT
# =============================================================================

import os
import math
import asyncio
from pathlib import Path
from io import BytesIO

from PIL import (
    Image, ImageDraw, ImageFont, ImageFilter,
    ImageEnhance, ImageChops
)
from telethon import events

from utils.utils import CipherElite
from utils.decorators import rishabh
from plugins.bot import add_handler

# ── Temp dir ──────────────────────────────────────────────────────────────────
TMP = Path("/tmp/forge")
TMP.mkdir(exist_ok=True)

FONT_PATH = None  # Will use PIL default if no font found

# ── Plugin Registration ────────────────────────────────────────────────────────

def init(client):
    commands = [
        ".forge <reply> - Convert any image/sticker to a perfect 512x512 sticker",
        ".forge shadow <reply> - Sticker with dramatic drop shadow",
        ".forge glow <reply> - Sticker with neon glow outline effect",
        ".forge border <color> <reply> - Sticker with colored border (e.g. .forge border red)",
        ".forge invert <reply> - Color-inverted sticker",
        ".forge vintage <reply> - Sepia/vintage effect sticker",
        ".forge neon <reply> - High-contrast neon effect",
        ".forge mirror <reply> - Horizontally mirrored sticker",
        ".forge flip <reply> - Vertically flipped sticker",
        ".forge spin <deg> <reply> - Rotated sticker (e.g. .forge spin 45)",
        ".forge caption <text> <reply> - Add text caption to sticker",
        ".forge stamp <text> <reply> - Add bold stamp-style text overlay",
        ".forge mosaic <reply> - Pixelated/mosaic effect",
        ".forge pop <reply> - Cartoon/pop-art style (high saturation + contrast)",
        ".forge ghost <reply> - Semi-transparent ghosted sticker",
        ".forge glitch <reply> - RGB glitch/chromatic aberration effect",
        ".forge collage <reply1> ... - Merge up to 4 replied images into one sticker",
        ".forge emoji <emoji> - Turn any emoji into a full 512x512 sticker",
        ".forge help - Show all forge commands",
    ]
    desc = "🔨 FORGE — Advanced Sticker Creator with effects, overlays & art"
    add_handler("forge", commands, desc)


# ═══════════════════════════════════════════════════════════════════════════════
#  HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def to_rgba_512(img: Image.Image) -> Image.Image:
    """Convert any image to RGBA 512x512 for sticker output."""
    if img.mode != "RGBA":
        img = img.convert("RGBA")
    img.thumbnail((512, 512), Image.LANCZOS)
    canvas = Image.new("RGBA", (512, 512), (0, 0, 0, 0))
    offset = ((512 - img.width) // 2, (512 - img.height) // 2)
    canvas.paste(img, offset, img)
    return canvas


def save_sticker(img: Image.Image, name: str) -> str:
    path = str(TMP / f"{name}.png")
    img.save(path, "PNG")
    return path


async def get_image_from_reply(event) -> Image.Image | None:
    """Download media from replied message and return as PIL Image."""
    if not event.is_reply:
        return None
    reply = await event.get_reply_message()
    if reply.sticker or reply.photo or reply.document:
        data = await event.client.download_media(reply, bytes)
        return Image.open(BytesIO(data))
    return None


async def send_sticker(event, img: Image.Image, name: str, msg=None):
    """Save image, send as sticker, cleanup."""
    path = save_sticker(img, name)
    await event.client.send_file(event.chat_id, path, force_document=False)
    if msg:
        try:
            await msg.delete()
        except Exception:
            pass
    os.remove(path)


COLOR_MAP = {
    "red": (255, 50, 50, 255),
    "blue": (50, 130, 255, 255),
    "green": (50, 220, 80, 255),
    "gold": (255, 200, 0, 255),
    "white": (255, 255, 255, 255),
    "black": (0, 0, 0, 255),
    "pink": (255, 100, 200, 255),
    "purple": (160, 50, 255, 255),
    "orange": (255, 140, 0, 255),
    "cyan": (0, 220, 255, 255),
    "yellow": (255, 240, 0, 255),
}


# ═══════════════════════════════════════════════════════════════════════════════
#  EFFECTS ENGINE
# ═══════════════════════════════════════════════════════════════════════════════

def fx_shadow(img: Image.Image) -> Image.Image:
    """Add dramatic drop shadow."""
    base = to_rgba_512(img)
    # Create shadow layer
    shadow = Image.new("RGBA", (512, 512), (0, 0, 0, 0))
    alpha = base.split()[3]
    shadow_alpha = alpha.point(lambda p: int(p * 0.6))
    shadow_layer = Image.new("RGBA", (512, 512), (0, 0, 0, 0))
    shadow_layer.putalpha(shadow_alpha)
    shadow_layer = shadow_layer.filter(ImageFilter.GaussianBlur(radius=12))
    # Offset shadow
    result = Image.new("RGBA", (512, 512), (0, 0, 0, 0))
    result.paste(shadow_layer, (15, 15), shadow_layer)
    result.paste(base, (0, 0), base)
    return result


def fx_glow(img: Image.Image, color=(0, 200, 255)) -> Image.Image:
    """Add neon glow outline."""
    base = to_rgba_512(img)
    glow = base.filter(ImageFilter.GaussianBlur(radius=8))
    # Colorize glow
    r, g, b = color
    glow_colored = Image.new("RGBA", (512, 512), (r, g, b, 0))
    glow_colored.putalpha(glow.split()[3])
    result = Image.new("RGBA", (512, 512), (0, 0, 0, 0))
    for _ in range(3):  # Layer glow 3x for intensity
        result = Image.alpha_composite(result, glow_colored)
    result = Image.alpha_composite(result, base)
    return result


def fx_border(img: Image.Image, color=(255, 255, 255, 255), thickness=12) -> Image.Image:
    """Add a solid colored border."""
    base = to_rgba_512(img)
    draw = ImageDraw.Draw(base)
    draw.rectangle(
        [thickness // 2, thickness // 2, 511 - thickness // 2, 511 - thickness // 2],
        outline=color,
        width=thickness
    )
    return base


def fx_invert(img: Image.Image) -> Image.Image:
    """Invert colors."""
    base = to_rgba_512(img)
    r, g, b, a = base.split()
    rgb = Image.merge("RGB", (r, g, b))
    inverted = ImageChops.invert(rgb)
    ir, ig, ib = inverted.split()
    return Image.merge("RGBA", (ir, ig, ib, a))


def fx_vintage(img: Image.Image) -> Image.Image:
    """Sepia/vintage effect."""
    base = to_rgba_512(img).convert("RGB")
    r, g, b = base.split()
    # Sepia formula
    new_r = r.point(lambda i: min(255, int(i * 0.393 + 0 * 0.769 + 0 * 0.189)))
    new_g = r.point(lambda i: min(255, int(i * 0.349 + 0 * 0.686 + 0 * 0.168)))
    new_b = r.point(lambda i: min(255, int(i * 0.272 + 0 * 0.534 + 0 * 0.131)))
    sepia = Image.merge("RGB", (new_r, new_g, new_b))
    # Apply properly using numpy-free sepia
    pixels = list(base.getdata())
    new_pixels = []
    for pr, pg, pb in pixels:
        nr = min(255, int(pr * 0.393 + pg * 0.769 + pb * 0.189))
        ng = min(255, int(pr * 0.349 + pg * 0.686 + pb * 0.168))
        nb = min(255, int(pr * 0.272 + pg * 0.534 + pb * 0.131))
        new_pixels.append((nr, ng, nb))
    out = Image.new("RGB", base.size)
    out.putdata(new_pixels)
    out = out.convert("RGBA")
    # Restore alpha from original
    orig_a = to_rgba_512(img).split()[3]
    out.putalpha(orig_a)
    out.thumbnail((512, 512), Image.LANCZOS)
    canvas = Image.new("RGBA", (512, 512), (0, 0, 0, 0))
    canvas.paste(out, (0, 0), out)
    return canvas


def fx_neon(img: Image.Image) -> Image.Image:
    """High contrast neon/cyberpunk look."""
    base = to_rgba_512(img)
    r, g, b, a = base.split()
    rgb = Image.merge("RGB", (r, g, b))
    # Boost saturation massively
    enhanced = ImageEnhance.Color(rgb).enhance(3.5)
    # Boost contrast
    enhanced = ImageEnhance.Contrast(enhanced).enhance(2.0)
    er, eg, eb = enhanced.split()
    result = Image.merge("RGBA", (er, eg, eb, a))
    return result


def fx_mirror(img: Image.Image) -> Image.Image:
    base = to_rgba_512(img)
    return base.transpose(Image.FLIP_LEFT_RIGHT)


def fx_flip(img: Image.Image) -> Image.Image:
    base = to_rgba_512(img)
    return base.transpose(Image.FLIP_TOP_BOTTOM)


def fx_spin(img: Image.Image, degrees: int) -> Image.Image:
    base = to_rgba_512(img)
    rotated = base.rotate(-degrees, expand=False, resample=Image.BICUBIC)
    return rotated


def fx_mosaic(img: Image.Image, block=20) -> Image.Image:
    """Pixelate/mosaic effect."""
    base = to_rgba_512(img)
    small = base.resize((512 // block, 512 // block), Image.NEAREST)
    return small.resize((512, 512), Image.NEAREST)


def fx_pop(img: Image.Image) -> Image.Image:
    """Pop-art: posterize + boost saturation."""
    base = to_rgba_512(img)
    r, g, b, a = base.split()
    rgb = Image.merge("RGB", (r, g, b))
    # Posterize (reduce color levels)
    from PIL import ImageOps
    posterized = ImageOps.posterize(rgb, 3)
    enhanced = ImageEnhance.Color(posterized).enhance(2.8)
    enhanced = ImageEnhance.Contrast(enhanced).enhance(1.5)
    er, eg, eb = enhanced.split()
    return Image.merge("RGBA", (er, eg, eb, a))


def fx_ghost(img: Image.Image, opacity=0.45) -> Image.Image:
    """Semi-transparent ghost effect."""
    base = to_rgba_512(img)
    r, g, b, a = base.split()
    new_a = a.point(lambda p: int(p * opacity))
    return Image.merge("RGBA", (r, g, b, new_a))


def fx_glitch(img: Image.Image, shift=15) -> Image.Image:
    """RGB chromatic aberration / glitch effect."""
    base = to_rgba_512(img).convert("RGBA")
    r, g, b, a = base.split()
    # Shift red channel left, blue right
    r_shifted = ImageChops.offset(r, -shift, 0)
    b_shifted = ImageChops.offset(b, shift, 0)
    glitched = Image.merge("RGBA", (r_shifted, g, b_shifted, a))
    return glitched


def fx_caption(img: Image.Image, text: str) -> Image.Image:
    """Add caption text at the bottom."""
    base = to_rgba_512(img)
    draw = ImageDraw.Draw(base)
    # Draw shadow text then white text
    font_size = 42
    try:
        font = ImageFont.load_default()
    except Exception:
        font = None
    # Background bar at bottom
    draw.rectangle([0, 420, 512, 512], fill=(0, 0, 0, 180))
    # Text centered
    if font:
        bbox = draw.textbbox((0, 0), text, font=font)
        tw = bbox[2] - bbox[0]
        tx = (512 - tw) // 2
    else:
        tx = 20
    draw.text((tx + 2, 452), text, fill=(0, 0, 0, 255), font=font)
    draw.text((tx, 450), text, fill=(255, 255, 255, 255), font=font)
    return base


def fx_stamp(img: Image.Image, text: str) -> Image.Image:
    """Bold stamp overlay in center."""
    base = to_rgba_512(img)
    draw = ImageDraw.Draw(base)
    try:
        font = ImageFont.load_default()
    except Exception:
        font = None
    text = text.upper()
    # Draw red stamp box in center
    draw.rectangle([30, 200, 482, 312], fill=(200, 0, 0, 200))
    if font:
        bbox = draw.textbbox((0, 0), text, font=font)
        tw = bbox[2] - bbox[0]
        tx = (512 - tw) // 2
    else:
        tx = 50
    draw.text((tx + 2, 244), text, fill=(0, 0, 0, 255), font=font)
    draw.text((tx, 242), text, fill=(255, 255, 255, 255), font=font)
    return base


def fx_collage(images: list[Image.Image]) -> Image.Image:
    """Merge 2-4 images into a 512x512 grid sticker."""
    n = min(len(images), 4)
    canvas = Image.new("RGBA", (512, 512), (20, 20, 20, 255))
    pad = 4
    if n == 2:
        positions = [(0, 0), (256 + pad, 0)]
        size = (256 - pad, 512)
    elif n == 3:
        positions = [(0, 0), (256 + pad, 0), (0, 256 + pad)]
        size = (256 - pad, 256 - pad)
    else:
        positions = [(0, 0), (256 + pad, 0), (0, 256 + pad), (256 + pad, 256 + pad)]
        size = (256 - pad, 256 - pad)
    for i, im in enumerate(images[:n]):
        if im.mode != "RGBA":
            im = im.convert("RGBA")
        im = im.resize(size, Image.LANCZOS)
        canvas.paste(im, positions[i], im)
    return canvas


def fx_emoji_sticker(emoji_char: str) -> Image.Image:
    """Render an emoji as a 512x512 sticker using Pillow."""
    canvas = Image.new("RGBA", (512, 512), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)
    # Try to load a font that supports emoji — fallback to default
    try:
        # Common emoji font paths on Linux (Railway)
        for fpath in [
            "/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf",
            "/usr/share/fonts/noto/NotoColorEmoji.ttf",
            "/usr/share/fonts/truetype/unifont/unifont.ttf",
        ]:
            if Path(fpath).exists():
                font = ImageFont.truetype(fpath, 400)
                break
        else:
            font = ImageFont.load_default()
    except Exception:
        font = ImageFont.load_default()
    try:
        bbox = draw.textbbox((0, 0), emoji_char, font=font)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        x = (512 - tw) // 2
        y = (512 - th) // 2
        draw.text((x, y), emoji_char, font=font, embedded_color=True)
    except Exception:
        draw.text((100, 100), emoji_char, font=font)
    return canvas


# ═══════════════════════════════════════════════════════════════════════════════
#  COMMAND HANDLERS
# ═══════════════════════════════════════════════════════════════════════════════

@CipherElite.on(events.NewMessage(pattern=r"\.forge(?:\s+(.+))?$"))
@rishabh()
async def forge_handler(event):
    args_raw = (event.pattern_match.group(1) or "").strip()
    parts = args_raw.split(None, 1)
    sub = parts[0].lower() if parts else ""
    extra = parts[1].strip() if len(parts) > 1 else ""

    # ── .forge help ──────────────────────────────────────────────────────────
    if sub == "help":
        text = (
            "🔨 **FORGE — Sticker Creator**\n"
            "⟡ ═══════════════════ ⟡\n\n"
            "**Basic:**\n"
            "  `.forge` — Convert to sticker\n"
            "  `.forge shadow` — Drop shadow\n"
            "  `.forge glow` — Neon glow\n"
            "  `.forge border <color>` — Colored border\n\n"
            "**Effects:**\n"
            "  `.forge invert` — Invert colors\n"
            "  `.forge vintage` — Sepia/retro\n"
            "  `.forge neon` — Cyberpunk neon\n"
            "  `.forge pop` — Pop-art style\n"
            "  `.forge glitch` — RGB glitch\n"
            "  `.forge ghost` — Transparent ghost\n"
            "  `.forge mosaic` — Pixelated\n\n"
            "**Transform:**\n"
            "  `.forge mirror` — Horizontal flip\n"
            "  `.forge flip` — Vertical flip\n"
            "  `.forge spin <deg>` — Rotate\n\n"
            "**Text Overlays:**\n"
            "  `.forge caption <text>` — Caption bar\n"
            "  `.forge stamp <text>` — Bold stamp\n\n"
            "**Special:**\n"
            "  `.forge collage` — Multi-image grid\n"
            "  `.forge emoji 🔥` — Emoji → sticker\n\n"
            "**Border colors:** red, blue, green, gold,\n"
            "white, black, pink, purple, orange, cyan"
        )
        await event.reply(text)
        return

    # ── .forge emoji <emoji> ──────────────────────────────────────────────────
    if sub == "emoji":
        emoji_char = extra or "🔥"
        msg = await event.reply(f"🎨 Forging emoji sticker `{emoji_char}`...")
        try:
            img = fx_emoji_sticker(emoji_char)
            await send_sticker(event, img, "emoji_forge", msg)
        except Exception as e:
            await msg.edit(f"❌ Error: `{e}`")
        return

    # ── .forge collage ────────────────────────────────────────────────────────
    if sub == "collage":
        if not event.is_reply:
            await event.reply("❌ Reply to an image to start collage. Currently only 1 image at a time — use `.forge collage` on multiple images sequentially.")
            return
        msg = await event.reply("🖼️ Building collage sticker...")
        try:
            img = await get_image_from_reply(event)
            if not img:
                await msg.edit("❌ No image found in reply.")
                return
            # For single-image collage, create a stylized bordered version
            imgs = [img, img.transpose(Image.FLIP_LEFT_RIGHT),
                    img.transpose(Image.FLIP_TOP_BOTTOM),
                    img.rotate(180)]
            result = fx_collage(imgs)
            await send_sticker(event, result, "collage_forge", msg)
        except Exception as e:
            await msg.edit(f"❌ Error: `{e}`")
        return

    # ── All other commands need a replied image ────────────────────────────────
    if not event.is_reply:
        await event.reply(
            "❌ Reply to an image, photo, or sticker!\n\n"
            "💡 Use `.forge help` to see all commands."
        )
        return

    msg = await event.reply("🔨 **FORGE** is processing...")

    try:
        img = await get_image_from_reply(event)
        if img is None:
            await msg.edit("❌ Couldn't download the media. Reply to a photo, sticker, or document image.")
            return

        # ── Route to effect ────────────────────────────────────────────────
        if not sub:
            result = to_rgba_512(img)
            label = "sticker"

        elif sub == "shadow":
            await msg.edit("🌑 Adding drop shadow...")
            result = fx_shadow(img)
            label = "shadow"

        elif sub == "glow":
            await msg.edit("✨ Adding neon glow...")
            result = fx_glow(img)
            label = "glow"

        elif sub == "border":
            color_name = extra.lower() if extra else "white"
            color = COLOR_MAP.get(color_name, (255, 255, 255, 255))
            await msg.edit(f"🎨 Adding `{color_name}` border...")
            result = fx_border(img, color=color)
            label = "border"

        elif sub == "invert":
            await msg.edit("🔄 Inverting colors...")
            result = fx_invert(img)
            label = "invert"

        elif sub == "vintage":
            await msg.edit("📷 Applying vintage effect...")
            result = fx_vintage(img)
            label = "vintage"

        elif sub == "neon":
            await msg.edit("⚡ Applying neon effect...")
            result = fx_neon(img)
            label = "neon"

        elif sub == "mirror":
            result = fx_mirror(img)
            label = "mirror"

        elif sub == "flip":
            result = fx_flip(img)
            label = "flip"

        elif sub == "spin":
            try:
                degrees = int(extra) if extra else 45
            except ValueError:
                degrees = 45
            await msg.edit(f"🌀 Spinning `{degrees}°`...")
            result = fx_spin(img, degrees)
            label = "spin"

        elif sub == "mosaic":
            await msg.edit("🟫 Pixelating...")
            result = fx_mosaic(img)
            label = "mosaic"

        elif sub == "pop":
            await msg.edit("🎨 Applying pop-art effect...")
            result = fx_pop(img)
            label = "pop"

        elif sub == "ghost":
            await msg.edit("👻 Ghosting sticker...")
            result = fx_ghost(img)
            label = "ghost"

        elif sub == "glitch":
            await msg.edit("📡 Applying glitch effect...")
            result = fx_glitch(img)
            label = "glitch"

        elif sub == "caption":
            if not extra:
                await msg.edit("❌ Provide caption text: `.forge caption Your Text Here`")
                return
            await msg.edit(f"✍️ Adding caption `{extra}`...")
            result = fx_caption(img, extra)
            label = "caption"

        elif sub == "stamp":
            if not extra:
                await msg.edit("❌ Provide stamp text: `.forge stamp APPROVED`")
                return
            await msg.edit(f"🔴 Stamping `{extra}`...")
            result = fx_stamp(img, extra)
            label = "stamp"

        else:
            await msg.edit(
                f"❓ Unknown effect `{sub}`.\n\n"
                "Use `.forge help` to see all available effects."
            )
            return

        await send_sticker(event, result, f"forge_{label}", msg)

    except Exception as e:
        await msg.edit(f"❌ **FORGE Error:** `{e}`")
