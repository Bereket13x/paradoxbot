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
import tempfile
TMP = Path(tempfile.gettempdir()) / "forge"
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
        ".forge text <style> <text> - Create stunning text sticker (styles: fire ice gold neon galaxy matrix sunset ocean dark)",
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
    path = str(TMP / f"{name}.webp")
    img.save(path, "WEBP")
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


# ── Text Sticker Styles ────────────────────────────────────────────────────────

TEXT_STYLES = {
    "fire":    {"bg": [(20,0,0), (180,40,0), (255,120,0)], "text": (255,240,180), "shadow": (255,60,0),   "outline": (80,0,0)},
    "ice":     {"bg": [(0,10,40), (0,80,160), (180,230,255)], "text": (220,245,255), "shadow": (0,150,255), "outline": (0,40,100)},
    "gold":    {"bg": [(10,5,0), (60,40,0), (120,80,0)], "text": (255,220,80), "shadow": (200,120,0),   "outline": (80,50,0)},
    "neon":    {"bg": [(0,0,0), (5,0,20), (10,0,40)], "text": (0,255,180), "shadow": (0,200,255),       "outline": (0,80,60)},
    "galaxy":  {"bg": [(5,0,20), (30,0,80), (80,0,140)], "text": (220,180,255), "shadow": (160,80,255), "outline": (30,0,60)},
    "matrix":  {"bg": [(0,0,0), (0,10,0), (0,20,5)], "text": (0,255,70), "shadow": (0,180,40),         "outline": (0,50,10)},
    "sunset":  {"bg": [(20,0,30), (180,40,80), (255,140,60)], "text": (255,240,200), "shadow": (255,100,50), "outline": (80,10,20)},
    "ocean":   {"bg": [(0,10,30), (0,80,120), (0,180,160)], "text": (200,245,255), "shadow": (0,200,220), "outline": (0,40,80)},
    "dark":    {"bg": [(10,10,10), (30,30,30), (50,50,50)], "text": (255,255,255), "shadow": (150,150,150), "outline": (0,0,0)},
}


def _make_gradient_bg(colors: list, size=(512, 512)) -> Image.Image:
    """Create a vertical gradient background from a list of (R,G,B) stops."""
    img = Image.new("RGB", size)
    pixels = img.load()
    w, h = size
    n = len(colors) - 1
    for y in range(h):
        t = y / (h - 1)  # 0.0 → 1.0
        seg = min(int(t * n), n - 1)
        local_t = (t * n) - seg
        c0 = colors[seg]
        c1 = colors[seg + 1]
        r = int(c0[0] + (c1[0] - c0[0]) * local_t)
        g = int(c0[1] + (c1[1] - c0[1]) * local_t)
        b = int(c0[2] + (c1[2] - c0[2]) * local_t)
        for x in range(w):
            pixels[x, y] = (r, g, b)
    return img


def _load_best_font(size: int) -> ImageFont.ImageFont:
    """Try to load a good bold font, fallback to PIL default."""
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
        "/usr/share/fonts/truetype/ubuntu/Ubuntu-Bold.ttf",
        "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf",
        "/usr/share/fonts/truetype/open-sans/OpenSans-Bold.ttf",
    ]
    for path in candidates:
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    try:
        return ImageFont.load_default()
    except Exception:
        return None


def _wrap_text(text: str, font, draw, max_width: int) -> list:
    """Word-wrap text to fit within max_width pixels."""
    words = text.split()
    lines = []
    current = ""
    for word in words:
        test = (current + " " + word).strip()
        try:
            bbox = draw.textbbox((0, 0), test, font=font)
            w = bbox[2] - bbox[0]
        except Exception:
            w = len(test) * 10
        if w <= max_width or not current:
            current = test
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def fx_text_sticker(text: str, style: str = "dark") -> Image.Image:
    """Generate a stunning 512x512 text sticker with the given style."""
    cfg = TEXT_STYLES.get(style.lower(), TEXT_STYLES["dark"])

    # ── Background ──────────────────────────────────────────────────────────
    bg = _make_gradient_bg(cfg["bg"]).convert("RGBA")

    # ── Add subtle noise/texture overlay ────────────────────────────────────
    import random as _rnd
    noise = Image.new("RGBA", (512, 512), (0, 0, 0, 0))
    noise_draw = ImageDraw.Draw(noise)
    for _ in range(600):
        x = _rnd.randint(0, 511)
        y = _rnd.randint(0, 511)
        a = _rnd.randint(10, 40)
        noise_draw.point((x, y), fill=(255, 255, 255, a))
    bg = Image.alpha_composite(bg, noise)

    # ── Galaxy style: add star dots ──────────────────────────────────────────
    if style == "galaxy":
        for _ in range(120):
            x = _rnd.randint(0, 511)
            y = _rnd.randint(0, 511)
            r = _rnd.randint(1, 3)
            a = _rnd.randint(150, 255)
            ImageDraw.Draw(bg).ellipse([x-r, y-r, x+r, y+r], fill=(255, 255, 255, a))

    # ── Matrix style: rain columns in background ─────────────────────────────
    if style == "matrix":
        mat_font = _load_best_font(14)
        mat_draw = ImageDraw.Draw(bg)
        chars = "01アイウエオカキクケコABCDEF"
        for col in range(0, 512, 18):
            for row in range(0, 512, 18):
                ch = _rnd.choice(chars)
                a = _rnd.randint(20, 80)
                mat_draw.text((col, row), ch, font=mat_font, fill=(0, 255, 70, a))

    # ── Decorative top/bottom bars ───────────────────────────────────────────
    bar_color = (*cfg["shadow"][:3], 120)
    bar_draw = ImageDraw.Draw(bg)
    bar_draw.rectangle([0, 0, 512, 8], fill=bar_color)
    bar_draw.rectangle([0, 504, 512, 512], fill=bar_color)
    bar_draw.rectangle([0, 0, 8, 512], fill=bar_color)
    bar_draw.rectangle([504, 0, 512, 512], fill=bar_color)

    # ── Determine font size by text length ──────────────────────────────────
    text_len = len(text)
    if text_len <= 6:
        font_size = 110
    elif text_len <= 12:
        font_size = 85
    elif text_len <= 20:
        font_size = 68
    elif text_len <= 35:
        font_size = 52
    else:
        font_size = 40

    font = _load_best_font(font_size)
    draw = ImageDraw.Draw(bg)

    # ── Word wrap ────────────────────────────────────────────────────────────
    margin = 40
    lines = _wrap_text(text, font, draw, 512 - margin * 2)

    # ── Calculate total text block height ────────────────────────────────────
    line_height = font_size + 10
    total_h = len(lines) * line_height
    start_y = (512 - total_h) // 2

    # ── Render each line with shadow + outline + main text ──────────────────
    for i, line in enumerate(lines):
        try:
            bbox = draw.textbbox((0, 0), line, font=font)
            tw = bbox[2] - bbox[0]
        except Exception:
            tw = len(line) * (font_size // 2)
        tx = (512 - tw) // 2
        ty = start_y + i * line_height

        # Outline (draw text in 8 directions)
        outline_col = (*cfg["outline"][:3], 255)
        for ox, oy in [(-2,-2),(2,-2),(-2,2),(2,2),(-3,0),(3,0),(0,-3),(0,3)]:
            draw.text((tx + ox, ty + oy), line, font=font, fill=outline_col)

        # Shadow (blurred by drawing offset)
        shadow_col = (*cfg["shadow"][:3], 180)
        draw.text((tx + 5, ty + 5), line, font=font, fill=shadow_col)
        draw.text((tx + 4, ty + 4), line, font=font, fill=shadow_col)

        # Main text
        text_col = (*cfg["text"][:3], 255)
        draw.text((tx, ty), line, font=font, fill=text_col)

    return bg


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
            "  `.forge invert` `.forge vintage` `.forge neon`\n"
            "  `.forge pop` `.forge glitch` `.forge ghost` `.forge mosaic`\n\n"
            "**Transform:**\n"
            "  `.forge mirror` `.forge flip` `.forge spin <deg>`\n\n"
            "**Text Overlays:**\n"
            "  `.forge caption <text>` `.forge stamp <text>`\n\n"
            "**✨ Text Stickers (NO image needed):**\n"
            "  `.forge text fire Hello World`\n"
            "  `.forge text ice PARADOX`\n"
            "  `.forge text gold King`\n"
            "  `.forge text neon GLOWING`\n"
            "  `.forge text galaxy Stars`\n"
            "  `.forge text matrix 01010`\n"
            "  `.forge text sunset Vibe`\n"
            "  `.forge text ocean Chill`\n"
            "  `.forge text dark Clean`\n\n"
            "**Special:**\n"
            "  `.forge collage` — Multi-image grid\n"
            "  `.forge emoji 🔥` — Emoji → sticker\n\n"
            "**Border colors:** red blue green gold\n"
            "white black pink purple orange cyan"
        )
        await event.reply(text)
        return

    # ── .forge text <style> <text> ────────────────────────────────────────────
    if sub == "text":
        # Parse: .forge text <style> <the rest is the text>
        # extra = "fire Hello World" or just "Hello World"
        style_parts = extra.split(None, 1) if extra else []
        valid_styles = list(TEXT_STYLES.keys())
        if style_parts and style_parts[0].lower() in valid_styles:
            style_name = style_parts[0].lower()
            user_text = style_parts[1] if len(style_parts) > 1 else "PARADOX"
        else:
            style_name = "dark"
            user_text = extra if extra else "PARADOX"
        if not user_text.strip():
            await event.reply(
                "✍️ **Text Sticker**\n\n"
                "**Usage:** `.forge text <style> <your text>`\n"
                "**Example:** `.forge text fire Hello World`\n\n"
                f"**Styles:** {' · '.join(valid_styles)}"
            )
            return
        msg = await event.reply(f"✨ Forging `{style_name}` text sticker...")
        try:
            img = fx_text_sticker(user_text, style_name)
            await send_sticker(event, img, f"text_{style_name}", msg)
        except Exception as e:
            await msg.edit(f"❌ **Error:** `{e}`")
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
