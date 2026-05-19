import asyncio
import os
from telethon import events
from plugins.bot import add_handler
from utils.utils import CipherElite
from utils.decorators import rishabh

def init(client):
    commands = [
        ".nuke - Deploy a tactical text nuke",
        ".magic - Do some text magic",
        ".monkey - Monkey peeking behind hands",
        ".hax - Super secret hacker terminal",
        ".police - Wee woo wee woo",
        ".loading - The most realistic loading bar",
        ".hackuser <reply/username> - Ultimate hacking animation and info dump"
    ]
    description = "A collection of the funniest and best text animations."
    add_handler("text_animation", commands, description)


@CipherElite.on(events.NewMessage(pattern=r"\.nuke$"))
@rishabh()
async def nuke_anim(event):
    animation = [
        "**TACTICAL NUKE INCOMING!** 🚨",
        "**TARGET ACQUIRED** 🎯",
        "**INITIATING LAUNCH SEQUENCE...** 🚀",
        "**3...**",
        "**2...**",
        "**1...**",
        "🚀💥💨",
        "💥💥 BOOM 💥💥",
        "🔥 Everything is fine... 🔥",
        "💀 You have officially been nuked. Have a nice day! 💀"
    ]
    for frame in animation:
        await event.edit(frame)
        await asyncio.sleep(1)


@CipherElite.on(events.NewMessage(pattern=r"\.magic$"))
@rishabh()
async def magic_anim(event):
    animation = [
        "Abracadabra... 🪄",
        "Alakazam! ✨",
        "Pulling a rabbit out of the hat... 🎩",
        "🎩\n🐰",
        "Wait, that's not a rabbit...",
        "🎩\n🦍",
        "Uh oh. RUN! 🏃‍♂️💨🦍"
    ]
    for frame in animation:
        await event.edit(frame)
        await asyncio.sleep(1)


@CipherElite.on(events.NewMessage(pattern=r"\.monkey$"))
@rishabh()
async def monkey_anim(event):
    animation = [
        "🙈",
        "🙉",
        "🙊",
        "🙈 Where did you go?",
        "🙉 I hear you!",
        "🙊 Oh, there you are!",
        "🐒 *throws a banana* 🍌",
        "🍌 SPLAT!"
    ]
    for frame in animation:
        await event.edit(frame)
        await asyncio.sleep(0.8)


@CipherElite.on(events.NewMessage(pattern=r"\.hax$"))
@rishabh()
async def hax_anim(event):
    animation = [
        "💻 `Connecting to NASA database...`",
        "💻 `Bypassing mainframe and security firewalls...`",
        "💻 `Accessing top secret files... [||||||....] 60%`",
        "💻 `Accessing top secret files... [|||||||||.] 90%`",
        "💻 `Accessing top secret files... [||||||||||] 100%`",
        "⚠ `WARNING: INTRUSION DETECTED` ⚠",
        "🚨 `FBI is tracking your location...` 🚨",
        "🏃‍♂️ `Time to throw the laptop in the river!` 🌊💻"
    ]
    for frame in animation:
        await event.edit(frame)
        await asyncio.sleep(1.2)


@CipherElite.on(events.NewMessage(pattern=r"\.police$"))
@rishabh()
async def police_anim(event):
    animation = [
        "🚓 💨",
        "WEE WOO WEE WOO 🚨🚓",
        "🚨🚓 WEE WOO WEE WOO",
        "WEE WOO WEE WOO 🚨🚓",
        "🚨🚓 WEE WOO WEE WOO",
        "👮‍♂️ STOP RIGHT THERE!",
        "👮‍♂️ YOU ARE ARRESTED FOR BEING TOO AWESOME! 😎✨"
    ]
    for frame in animation:
        await event.edit(frame)
        await asyncio.sleep(0.6)


@CipherElite.on(events.NewMessage(pattern=r"\.loading$"))
@rishabh()
async def loading_anim(event):
    animation = [
        "`Loading awesomeness...`\n[----------] 0%",
        "`Loading awesomeness...`\n[||--------] 20%",
        "`Loading awesomeness...`\n[||||------] 40%",
        "`Loading awesomeness...`\n[||||||----] 60%",
        "`Loading awesomeness...`\n[||||||||--] 80%",
        "`Loading awesomeness...`\n[|||||||||.] 99%",
        "`Loading awesomeness...`\n[|||||||||.] 99.9%",
        "`ERROR 404: Awesomeness overflow.` 💥💥"
    ]
    for frame in animation:
        await event.edit(frame)
        await asyncio.sleep(1)


@CipherElite.on(events.NewMessage(pattern=r"\.hackuser(?:\s+([\s\S]+))?$"))
@rishabh()
async def hackuser_anim(event):
    reply = await event.get_reply_message()
    input_str = event.pattern_match.group(1)
    
    if reply:
        target = reply.sender_id
    elif input_str:
        target = input_str
    else:
        return await event.edit("`Whom should I hack? Reply to a user or mention their username.`")
        
    try:
        user = await event.client.get_entity(target)
    except Exception as e:
        return await event.edit(f"`Could not find the target:` {str(e)}")

    animation = [
        "`[+] Connecting to Telegram servers...`",
        "`[+] Bypassing user security...`",
        f"`[+] Targeting {user.first_name}...`",
        "`[+] Brute-forcing account password...`",
        "`[+] Password breached: *******`",
        "`[+] Accessing personal chats...`",
        "`[+] Downloading 'Homework' folder... [||||||....] 60%`",
        "`[+] Exfiltrating profile assets...`",
        "`[+] Injection complete! Extracting data...`"
    ]
    
    cat = event
    for frame in animation:
        try:
            cat = await cat.edit(frame)
            await asyncio.sleep(1.2)
        except Exception:
            pass
            
    info = f"**🔥 HACKED {user.first_name} SUCCESSFULLY! 🔥**\n\n"
    info += f"👤 **Name:** `{user.first_name}`\n"
    if hasattr(user, 'last_name') and user.last_name:
        info += f"📝 **Last Name:** `{user.last_name}`\n"
    if hasattr(user, 'username') and user.username:
        info += f"🔗 **Username:** `@{user.username}`\n"
    info += f"🆔 **ID:** `{user.id}`\n"
    if hasattr(user, 'bot'):
        info += f"🤖 **Is Bot:** `{user.bot}`\n"
    if hasattr(user, 'scam'):
        info += f"🤡 **Is Scam:** `{user.scam}`\n"
    
    info += "\n`All data successfully uploaded to the dark web.` 🕶"

    await cat.edit("`Fetching extracted profile data...`")
    profile_photo = await event.client.download_profile_photo(user)
    
    if profile_photo:
        await event.client.send_file(event.chat_id, profile_photo, caption=info)
        os.remove(profile_photo)
        await cat.delete()
    else:
        await cat.edit(info)

