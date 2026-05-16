import asyncio
import random
import time

from telethon import events
from telethon.errors.rpcerrorlist import MessageNotModifiedError
from telethon.tl.functions.users import GetUsersRequest
from telethon.tl.types import UserStatusOnline, UserStatusRecently

from utils.utils import CipherElite
from utils.decorators import rishabh
from plugins.bot import add_handler

def init(client):
    commands = [
        ".animate <text> - Simulate typing animation",
        ".spinner [sec]  - Show spinner animation",
        ".loveu          - Rainbow heart animation",
        ".matrix [sec]   - Matrix rain in text",
        ".hearts <text>  - Bubble hearts around your text",
        ".countdown <n>  - Count down from n to 0",
        ".wave <text>    - Text wave effect",
        ".scan <@user/reply> - Hacker-style identity scan"
    ]
    add_handler("animation", commands, "Animation Plugin")

async def safe_edit(msg, text):
    try:
        await msg.edit(text)
    except MessageNotModifiedError:
        pass


@CipherElite.on(events.NewMessage(pattern=r"^\.animate\s+([\s\S]+)$", outgoing=True))
@rishabh()
async def animate_text(event):
    # Grab everything after ".animate "
    text = event.pattern_match.group(1).strip()
    if not text:
        return await event.reply("❗️ Usage: `.animate <text>`")

    # Send a visible placeholder so we can edit it
    msg = await event.reply("⏳")

    # Type out one char at a time
    for i in range(1, len(text) + 1):
        new = text[:i]
        try:
            await msg.edit(new)
        except MessageNotModifiedError:
            # Happens if new == old; just ignore and continue
            pass
        # small random delay for a “human” feel
        await asyncio.sleep(0.05 + random.random() * 0.1)

    # Pause on the full text for a moment
    await asyncio.sleep(0.5)

@CipherElite.on(events.NewMessage(pattern=r"^\.spinner(?:\s+(\d+))?$", outgoing=True))
@rishabh()
async def spinner(event):
    sec = event.pattern_match.group(1)
    total = int(sec) if sec and sec.isdigit() else 5
    frames = ["|", "/", "—", "\\"]
    msg = await event.reply("⏳ Starting spinner…")

    start = asyncio.get_event_loop().time()
    idx = 0
    while asyncio.get_event_loop().time() - start < total:
        frame = frames[idx % len(frames)]
        try:
            await msg.edit(f"{frame} spinning…")
        except MessageNotModifiedError:
            pass
        idx += 1
        await asyncio.sleep(0.2)

    await msg.edit("✅ Done!")


@CipherElite.on(events.NewMessage(pattern=r"^\.loveu$", outgoing=True))
@rishabh()
async def loveu(event):
    hearts = ["❤️", "🧡", "💛", "💚", "💙", "💜", "🖤", "💖", "💗", "💓"]
    msg = await event.reply(hearts[0])
    # cycle rainbow hearts then final message
    for i in range(len(hearts) * 3):
        await safe_edit(msg, hearts[i % len(hearts)])
        await asyncio.sleep(0.3)
    await safe_edit(msg, "I ❤️ U")

@CipherElite.on(events.NewMessage(pattern=r"^\.matrix(?:\s+(\d+))?$", outgoing=True))
@rishabh()
async def matrix(event):
    sec = event.pattern_match.group(1)
    total = int(sec) if sec and sec.isdigit() else 5
    width, height = 20, 6
    msg = await event.reply("Loading Matrix…")
    start = time.time()
    while time.time() - start < total:
        frame = ""
        for _ in range(height):
            line = "".join(random.choice(["0", "1", " "]) for _ in range(width))
            frame += line + "\n"
        await safe_edit(msg, f"```{frame}```")
        await asyncio.sleep(0.5)
    await safe_edit(msg, "🔚 Matrix end")

@CipherElite.on(events.NewMessage(pattern=r"^\.hearts\s+([\s\S]+)$", outgoing=True))
@rishabh()
async def hearts(event):
    text = event.pattern_match.group(1).strip()
    if not text:
        return await event.reply("❗️ Usage: `.hearts <text>`")
    msg = await event.reply(f"💖 {text} 💖")
    frames = [
        f"💘 {text} 💘",
        f"💕 {text} 💕",
        f"💞 {text} 💞",
        f"💓 {text} 💓",
    ]
    for i in range(len(frames) * 2):
        await safe_edit(msg, frames[i % len(frames)])
        await asyncio.sleep(0.6)
    await safe_edit(msg, f"💖 {text} 💖")

@CipherElite.on(events.NewMessage(pattern=r"^\.countdown\s+(\d+)$", outgoing=True))
@rishabh()
async def countdown(event):
    start_n = int(event.pattern_match.group(1))
    msg = await event.reply(str(start_n))
    for n in range(start_n - 1, -1, -1):
        await asyncio.sleep(1.0)
        await safe_edit(msg, str(n))
    await asyncio.sleep(0.5)
    await safe_edit(msg, "🎉 Boom!")

@CipherElite.on(events.NewMessage(pattern=r"^\.wave\s+([\s\S]+)$", outgoing=True))
@rishabh()
async def wave(event):
    text = event.pattern_match.group(1).strip()
    if not text:
        return await event.reply("❗️ Usage: `.wave <text>`")
    msg = await event.reply(text)
    width = len(text) + 4
    direction = 1
    pos = 0
    # two full back-and-forth cycles
    for _ in range(width * 2):
        gap = " " * pos
        await safe_edit(msg, gap + text)
        if pos == width or pos == 0:
            direction *= -1
        pos += direction
        await asyncio.sleep(0.1)
    await safe_edit(msg, text)


@CipherElite.on(events.NewMessage(pattern=r"^\.scan(?:\s+(.+))?$", outgoing=True))
@rishabh()
async def scan_user(event):
    target = (event.pattern_match.group(1) or "").strip()

    if not target and not event.is_reply:
        return await event.reply("❌ **Usage:** `.scan @username` or reply to someone.")

    # Resolve the target user
    try:
        if event.is_reply and not target:
            reply = await event.get_reply_message()
            uid = reply.sender_id
        else:
            uid = target.lstrip("@")
        result = await event.client(GetUsersRequest(id=[uid]))
        if not result:
            return await event.reply("❌ **Target not found.**")
        user = result[0]
    except Exception as e:
        return await event.reply(f"❌ **Error:** `{e}`")

    # Prepare user data
    first = user.first_name or ""
    last = user.last_name or ""
    real_name = f"{first} {last}".strip() or "CLASSIFIED"
    username = f"@{user.username}" if user.username else "HIDDEN"
    user_id = user.id
    is_bot = "YES ⚠️" if user.bot else "NO"
    is_premium = "YES ⭐" if getattr(user, 'premium', False) else "NO"
    is_verified = "YES ✅" if getattr(user, 'verified', False) else "NO"
    is_scam = "YES 🚨" if getattr(user, 'scam', False) else "NO"
    is_fake = "YES 💀" if getattr(user, 'fake', False) else "NO"
    is_restricted = "YES 🔒" if getattr(user, 'restricted', False) else "NO"

    status = user.status
    if isinstance(status, UserStatusOnline):
        status_str = "🟢 ONLINE NOW"
    elif isinstance(status, UserStatusRecently):
        status_str = "🟡 Recently Online"
    else:
        status_str = "🔴 Offline"

    # Threat level based on flags
    threat = 0
    if user.bot: threat += 2
    if getattr(user, 'scam', False): threat += 5
    if getattr(user, 'fake', False): threat += 5
    if getattr(user, 'restricted', False): threat += 3
    if getattr(user, 'premium', False): threat -= 1
    if getattr(user, 'verified', False): threat -= 2
    threat = max(0, min(threat, 10))
    threat_bar = "█" * threat + "░" * (10 - threat)
    if threat >= 7:
        threat_label = "🔴 CRITICAL"
    elif threat >= 4:
        threat_label = "🟡 MODERATE"
    elif threat >= 1:
        threat_label = "🟢 LOW"
    else:
        threat_label = "⚪ CLEAN"

    msg = await event.edit("⏳")

    # ── PHASE 1: Boot sequence ──────────────────────────────────────────
    frames_boot = [
        "```\n⟨ PARADOX SYSTEM ⟩\n\n[          ] 0%\n\nBooting scanner...\n```",
        "```\n⟨ PARADOX SYSTEM ⟩\n\n[██        ] 10%\n\nInitializing modules...\n```",
        "```\n⟨ PARADOX SYSTEM ⟩\n\n[████      ] 25%\n\nLoading target database...\n```",
    ]
    for f in frames_boot:
        await safe_edit(msg, f)
        await asyncio.sleep(0.5)

    # ── PHASE 2: Target lock ────────────────────────────────────────────
    frames_lock = [
        f"```\n⟨ PARADOX SYSTEM ⟩\n\n[██████    ] 40%\n\n🔎 Locating target: {username}\n   Searching Telegram servers...\n```",
        f"```\n⟨ PARADOX SYSTEM ⟩\n\n[███████   ] 55%\n\n🎯 TARGET LOCKED\n   ID: {user_id}\n   Extracting identity...\n```",
    ]
    for f in frames_lock:
        await safe_edit(msg, f)
        await asyncio.sleep(0.6)

    # ── PHASE 3: Data extraction ────────────────────────────────────────
    frames_extract = [
        f"```\n⟨ PARADOX SYSTEM ⟩\n\n[████████  ] 70%\n\n📡 Intercepting data packets...\n   ▓▓▓░░░░░ Decoding...\n```",
        f"```\n⟨ PARADOX SYSTEM ⟩\n\n[█████████ ] 85%\n\n🔓 Decrypting identity matrix...\n   ▓▓▓▓▓▓░░ Almost there...\n```",
        f"```\n⟨ PARADOX SYSTEM ⟩\n\n[██████████] 100%\n\n✅ SCAN COMPLETE\n   Generating report...\n```",
    ]
    for f in frames_extract:
        await safe_edit(msg, f)
        await asyncio.sleep(0.5)

    await asyncio.sleep(0.3)

    # ── PHASE 4: Final report ───────────────────────────────────────────
    report = (
        f"⟨ **PARADOX SCANNER** ⟩\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"✅ **SCAN COMPLETE** — Target Acquired\n\n"
        f"📛 **Real Name:** `{real_name}`\n"
        f"🆔 **Username:** `{username}`\n"
        f"🔢 **User ID:** `{user_id}`\n"
        f"📡 **Status:** {status_str}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🤖 **Bot:** `{is_bot}`\n"
        f"⭐ **Premium:** `{is_premium}`\n"
        f"✅ **Verified:** `{is_verified}`\n"
        f"🔒 **Restricted:** `{is_restricted}`\n"
        f"⚠️ **Scam:** `{is_scam}`\n"
        f"💀 **Fake:** `{is_fake}`\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🛡 **Threat Level:** [{threat_bar}] {threat_label}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"⟨ PARADOX v2.0 ⟩"
    )
    await safe_edit(msg, report)
