# =============================================================================
#  CipherElite Userbot Plugin
#
#  Plugin Name:    Profile
#  Author:         CipherElite Plugins (Ported from CatUB)
#  Description:    Tools to manage your user profile, bio, pic, and stats.
# =============================================================================

import os

from telethon import events, functions
from telethon.errors.rpcerrorlist import UsernameOccupiedError
from telethon.tl.functions.account import UpdateUsernameRequest
from telethon.tl.functions.channels import GetAdminedPublicChannelsRequest
from telethon.tl.functions.photos import DeletePhotosRequest, GetUserPhotosRequest
from telethon.tl.types import Channel, Chat, InputPhoto, User

from plugins.bot import add_handler
from utils.utils import CipherElite
from utils.decorators import rishabh

def init(client):
    commands = [
        ".pbio <bio>", 
        ".pname <firstname> ; <lastname>", 
        ".ppic (reply to image/video)",
        ".pusername <new username>",
        ".count",
        ".delpfp <amount>",
        ".myusernames"
    ]
    desc = "Profile management tools natively ported for CipherElite."
    add_handler("profile", commands, desc)

# ====================== CONSTANTS ==============================
USERNAME_SUCCESS = "```Your username was successfully changed.```"
USERNAME_TAKEN = "```This username is already taken.```"
# ===============================================================

@CipherElite.on(events.NewMessage(pattern=r"\.pbio(?:\s+(.+))?"))
@rishabh()
async def _(event):
    bio = event.pattern_match.group(1)
    if not bio:
        return await event.edit("`Give some text to set as bio`")
    try:
        await event.client(functions.account.UpdateProfileRequest(about=bio))
        await event.edit("`Successfully changed my profile bio`")
    except Exception as e:
        await event.edit(f"**Error:**\n`{e}`")


@CipherElite.on(events.NewMessage(pattern=r"\.pname(?:\s+(.+))?"))
@rishabh()
async def _(event):
    names = event.pattern_match.group(1)
    if not names:
        return await event.edit("`Give some text to set as name`")
    first_name = names
    last_name = ""
    if ";" in names:
        first_name, last_name = names.split(";", 1)
    try:
        await event.client(
            functions.account.UpdateProfileRequest(
                first_name=first_name.strip(), last_name=last_name.strip()
            )
        )
        await event.edit("`My name was changed successfully`")
    except Exception as e:
        await event.edit(f"**Error:**\n`{e}`")


@CipherElite.on(events.NewMessage(pattern=r"\.ppic$"))
@rishabh()
async def _(event):
    reply_message = await event.get_reply_message()
    if not reply_message or not reply_message.media:
        return await event.edit("`Reply to an image or video to set it as profile picture.`")
        
    catevent = await event.edit("`Downloading Profile Picture to my local ...`")
    
    # Using tmp directory for downloading media
    tmp_dir = "/tmp/cipher_downloads"
    os.makedirs(tmp_dir, exist_ok=True)
    
    photo = None
    try:
        photo = await event.client.download_media(reply_message, tmp_dir)
    except Exception as e:
        return await catevent.edit(str(e))
        
    if photo:
        await catevent.edit("`Now, Uploading to Telegram ...`")
        try:
            if photo.lower().endswith(".mp4"):
                size = os.stat(photo).st_size
                if size > 2097152:
                    await catevent.edit("`Size must be less than 2 mb`")
                    os.remove(photo)
                    return
                catvideo = await event.client.upload_file(photo)
                await event.client(
                    functions.photos.UploadProfilePhotoRequest(
                        video=catvideo, video_start_ts=0.01
                    )
                )
            else:
                catpic = await event.client.upload_file(photo)
                await event.client(
                    functions.photos.UploadProfilePhotoRequest(
                        file=catpic
                    )
                )
            await catevent.edit("`My profile picture was successfully changed`")
        except Exception as e:
            await catevent.edit(f"**Error:**\n`{e}`")
            
    try:
        if photo and os.path.exists(photo):
            os.remove(photo)
    except Exception:
        pass


@CipherElite.on(events.NewMessage(pattern=r"\.pusername(?:\s+(.+))?"))
@rishabh()
async def update_username(event):
    newusername = event.pattern_match.group(1)
    if not newusername:
        return await event.edit("`Please provide a username.`")
    try:
        await event.client(UpdateUsernameRequest(newusername))
        await event.edit(USERNAME_SUCCESS)
    except UsernameOccupiedError:
        await event.edit(USERNAME_TAKEN)
    except Exception as e:
        await event.edit(f"**Error:**\n`{e}`")


@CipherElite.on(events.NewMessage(pattern=r"\.count$"))
@rishabh()
async def count(event):
    catevent = await event.edit("`Processing..`")
    u = 0
    g = 0
    c = 0
    bc = 0
    b = 0
    result = ""
    dialogs = await event.client.get_dialogs(limit=None, ignore_migrated=True)
    for d in dialogs:
        currrent_entity = d.entity
        if isinstance(currrent_entity, User):
            if currrent_entity.bot:
                b += 1
            else:
                u += 1
        elif isinstance(currrent_entity, Chat):
            g += 1
        elif isinstance(currrent_entity, Channel):
            if currrent_entity.broadcast:
                bc += 1
            else:
                c += 1

    result += f"**📊 Your Telethon Profile Stats**\n\n"
    result += f"`Users:`\t**{u}**\n"
    result += f"`Groups:`\t**{g}**\n"
    result += f"`Super Groups:`\t**{c}**\n"
    result += f"`Channels:`\t**{bc}**\n"
    result += f"`Bots:`\t**{b}**"

    await catevent.edit(result)


@CipherElite.on(events.NewMessage(pattern=r"\.delpfp(?:\s+(.+))?"))
@rishabh()
async def remove_profilepic(event):
    arg = event.pattern_match.group(1)
    if arg and arg.lower() == "all":
        lim = 0
    elif arg and arg.isdigit():
        lim = int(arg)
    else:
        lim = 1
        
    pfplist = await event.client(
        GetUserPhotosRequest(user_id=event.sender_id, offset=0, max_id=0, limit=lim)
    )
    
    if not pfplist.photos:
        return await event.edit("`No profile pictures found to delete.`")
        
    input_photos = [
        InputPhoto(
            id=sep.id,
            access_hash=sep.access_hash,
            file_reference=sep.file_reference,
        )
        for sep in pfplist.photos
    ]
    await event.client(DeletePhotosRequest(id=input_photos))
    await event.edit(f"`Successfully deleted {len(input_photos)} profile picture(s).`")


@CipherElite.on(events.NewMessage(pattern=r"\.myusernames$"))
@rishabh()
async def myusernames(event):
    await event.edit("`Fetching your reserved usernames...`")
    result = await event.client(GetAdminedPublicChannelsRequest())
    if not result.chats:
        return await event.edit("`You don't have any reserved public usernames.`")
        
    output_str = "**Your current reserved usernames:**\n\n" + "".join(
        f" • {channel_obj.title} - @{channel_obj.username} \n"
        for channel_obj in result.chats
    )
    await event.edit(output_str)
