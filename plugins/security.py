# =============================================================================
#  CipherElite Userbot Plugin
#
#  Plugin Name:    Security & Channel Transfer
#  Author:         CipherElite Plugins (PARADOX)
#  Description:    Manage 2-Step Verification and transfer channel ownership.
#
#  ⚠️  SECURITY WARNING:
#      Your 2FA password is passed as plain text in the command.
#      Always delete the message immediately after using these commands!
# =============================================================================

import asyncio

from telethon import events
from telethon.errors import (
    ChatAdminRequiredError,
    FloodWaitError,
    PasswordHashInvalidError,
    RPCError,
    UserNotParticipantError,
)
from telethon.password import compute_check
from telethon.tl.functions.account import GetPasswordRequest
from telethon.tl.functions.channels import EditAdminRequest, EditCreatorRequest
from telethon.tl.types import Channel, ChatAdminRights

from plugins.bot import add_handler
from utils.utils import CipherElite
from utils.decorators import rishabh

# Full admin rights — everything except anonymous posting
_FULL_ADMIN_RIGHTS = ChatAdminRights(
    change_info=True,
    post_messages=True,
    edit_messages=True,
    delete_messages=True,
    ban_users=True,
    invite_users=True,
    pin_messages=True,
    add_admins=False,   # don't give right to add more admins by default
    manage_call=True,
    other=True,
)


# ── Plugin Registration ────────────────────────────────────────────────────────

def init(client):
    commands = [
        ".set2fa <password> [hint]               — Enable / change 2FA password",
        ".change2fa <old> <new> [hint]            — Change existing 2FA password",
        ".remove2fa <current_password>           — Disable 2FA completely",
        ".addadmin @user @channel                — Make user full admin in one channel",
        ".addadminall @user                      — Make user admin in ALL owned channels",
        ".transferchan @chan @user <2fa_pass>    — Transfer one channel",
        ".transferall @user <2fa_pass>           — Transfer ALL owned channels",
    ]
    desc = (
        "🔐 Account Security & Channel Manager — 2FA, admin promotion, "
        "and channel ownership transfer."
    )
    add_handler("security", commands, desc)


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _get_owned_channels(client) -> list[Channel]:
    """Return all broadcast channels where the logged-in user is creator."""
    owned = []
    async for dialog in client.iter_dialogs():
        ent = dialog.entity
        if (
            isinstance(ent, Channel)
            and ent.broadcast          # is a channel (not a supergroup)
            and getattr(ent, "creator", False)
        ):
            owned.append(ent)
    return owned


async def _compute_srp(client, plaintext_password: str):
    """Fetch current password settings and compute the SRP check object."""
    pwd_settings = await client(GetPasswordRequest())
    return compute_check(pwd_settings, plaintext_password)


async def _transfer_channel(client, channel: Channel, target_user, srp_check) -> dict:
    """
    Transfer `channel` ownership to `target_user`.
    Returns {"ok": bool, "name": str, "error": str|None}
    """
    name = getattr(channel, "title", str(channel.id))
    try:
        await client(
            EditCreatorRequest(
                channel=channel,
                user_id=target_user,
                password=srp_check,
            )
        )
        return {"ok": True, "name": name, "error": None}
    except PasswordHashInvalidError:
        return {"ok": False, "name": name, "error": "Wrong 2FA password (hash mismatch)"}
    except ChatAdminRequiredError:
        return {"ok": False, "name": name, "error": "Target must be an admin of the channel first"}
    except FloodWaitError as e:
        await asyncio.sleep(e.seconds + 1)
        return {"ok": False, "name": name, "error": f"FloodWait {e.seconds}s — skipped"}
    except RPCError as e:
        return {"ok": False, "name": name, "error": str(e)}
    except Exception as e:
        return {"ok": False, "name": name, "error": str(e)}


async def _add_admin_to_channel(client, channel: Channel, target_user) -> dict:
    """
    Promote target_user to admin in channel with full rights.
    Returns {"ok": bool, "name": str, "error": str|None}
    On ANY error, returns immediately — caller must decide whether to stop.
    """
    name = getattr(channel, "title", str(channel.id))
    try:
        await client(
            EditAdminRequest(
                channel=channel,
                user_id=target_user,
                admin_rights=_FULL_ADMIN_RIGHTS,
                rank="Admin",
            )
        )
        return {"ok": True, "name": name, "error": None}
    except ChatAdminRequiredError:
        return {"ok": False, "name": name, "error": "You need to be an admin to promote others"}
    except UserNotParticipantError:
        return {"ok": False, "name": name, "error": "User is not a member of this channel"}
    except FloodWaitError as e:
        return {"ok": False, "name": name, "error": f"FloodWait: must wait {e.seconds}s — stopping"}
    except RPCError as e:
        return {"ok": False, "name": name, "error": f"Telegram error: {e}"}
    except Exception as e:
        return {"ok": False, "name": name, "error": str(e)}


# ── Admin Commands ────────────────────────────────────────────────────────────

@CipherElite.on(events.NewMessage(pattern=r"\.addadmin(?:\s+(.+))?$"))
@rishabh()
async def addadmin_cmd(event):
    """
    .addadmin @user @channel
    Adds user as full admin to ONE specific channel.
    Exits immediately on any error.
    """
    raw = (event.pattern_match.group(1) or "").strip()
    parts = raw.split()

    if len(parts) < 2:
        return await event.reply(
            "👑 **Add Admin to Channel**\n\n"
            "**Usage:** `.addadmin @user @channel`\n"
            "**Example:** `.addadmin @friend @mychannel`\n\n"
            "_The user will be given full admin rights (except adding more admins)._"
        )

    user_target  = parts[0].lstrip("@")
    chan_target   = parts[1].lstrip("@")
    client        = event.client
    msg           = await event.reply("🔍 **Resolving entities...**")

    # Resolve user — exit on failure
    try:
        target_user = await client.get_entity(user_target)
    except Exception as e:
        return await msg.edit(f"❌ **Could not find user** `@{user_target}`:\n`{e}`\n\n_Exiting._")

    # Resolve channel — exit on failure
    try:
        channel = await client.get_entity(chan_target)
    except Exception as e:
        return await msg.edit(f"❌ **Could not find channel** `@{chan_target}`:\n`{e}`\n\n_Exiting._")

    if not isinstance(channel, Channel):
        return await msg.edit("❌ That entity is not a Telegram channel.\n\n_Exiting._")

    await msg.edit(f"⏳ **Promoting** `@{user_target}` in `{channel.title}`...")

    result = await _add_admin_to_channel(client, channel, target_user)

    if result["ok"]:
        await msg.edit(
            f"✅ **Admin Promotion Successful!**\n\n"
            f"👤 **User:** `@{user_target}`\n"
            f"📢 **Channel:** `{result['name']}`\n"
            f"👑 **Rank:** Admin (full rights)"
        )
    else:
        await msg.edit(
            f"❌ **Promotion Failed — Exiting**\n\n"
            f"📢 **Channel:** `{result['name']}`\n"
            f"**Reason:** `{result['error']}`"
        )


@CipherElite.on(events.NewMessage(pattern=r"\.addadminall(?:\s+(.+))?$"))
@rishabh()
async def addadminall_cmd(event):
    """
    .addadminall @user
    Promotes user to admin in ALL channels you own.
    Stops immediately if any channel fails — reports exactly where it stopped.
    """
    raw = (event.pattern_match.group(1) or "").strip().lstrip("@")

    if not raw:
        return await event.reply(
            "👑 **Add Admin to ALL Owned Channels**\n\n"
            "**Usage:** `.addadminall @user`\n"
            "**Example:** `.addadminall @friend`\n\n"
            "_Promotes the user to full admin in every channel you own.\n"
            "Stops immediately on the first error._"
        )

    client = event.client
    msg    = await event.reply("🔍 **Scanning your channels...**")

    # Get all owned channels — exit if none found
    owned = await _get_owned_channels(client)
    if not owned:
        return await msg.edit(
            "❌ **No owned channels found.**\n"
            "_You must be the original creator of channels for this to work._\n\n"
            "_Exiting._"
        )

    await msg.edit(
        f"📢 **Found {len(owned)} owned channel(s)**\n\n"
        + "\n".join(f"  • `{c.title}`" for c in owned[:20])
        + (f"\n  _(and {len(owned) - 20} more)_" if len(owned) > 20 else "")
        + f"\n\n🔍 **Resolving user** `@{raw}`..."
    )

    # Resolve user — exit on failure
    try:
        target_user = await client.get_entity(raw)
    except Exception as e:
        return await msg.edit(
            f"❌ **Could not find user** `@{raw}`:\n`{e}`\n\n_Exiting._"
        )

    await msg.edit(
        f"👑 **Promoting** `@{raw}` in {len(owned)} channel(s)...\n"
        f"⚠️ Will stop immediately on any error."
    )

    done    = []   # successfully promoted
    stopped = None  # first failure dict

    for i, channel in enumerate(owned):
        await msg.edit(
            f"👑 **Adding admin** `{i+1}/{len(owned)}`\n"
            f"  ▶ `{channel.title}`"
        )

        result = await _add_admin_to_channel(client, channel, target_user)

        if result["ok"]:
            done.append(result["name"])
            await asyncio.sleep(1.5)   # pace between calls
        else:
            stopped = result            # record the failure
            break                       # EXIT immediately

    # ── Final report ──────────────────────────────────────────────────────────
    lines = ["👑 **Add Admin — Summary**\n"]

    if done:
        lines.append(f"✅ **Successfully promoted in ({len(done)}/{len(owned)}):**")
        for name in done:
            lines.append(f"  ✅ `{name}`")

    if stopped:
        remaining = len(owned) - len(done)
        lines.append(
            f"\n❌ **Stopped at:** `{stopped['name']}`\n"
            f"**Reason:** `{stopped['error']}`\n"
            f"**Skipped:** {remaining - 1} remaining channel(s) were NOT processed."
        )
    else:
        lines.append(f"\n🎉 **All {len(done)} channels updated successfully!**")

    lines.append(f"\n👤 **User:** `@{raw}`")
    await msg.edit("\n".join(lines))


# ── 2FA Commands ──────────────────────────────────────────────────────────────

@CipherElite.on(events.NewMessage(pattern=r"\.set2fa(?:\s+(.+))?$"))
@rishabh()
async def set2fa_cmd(event):
    """
    .set2fa <new_password> [hint]
    If 2FA is already enabled, this CHANGES the password.
    Hint is optional — separate with a space after the password.
    """
    raw = (event.pattern_match.group(1) or "").strip()
    if not raw:
        return await event.reply(
            "🔐 **Set 2-Step Verification**\n\n"
            "**Usage:** `.set2fa <password> [hint]`\n"
            "**Example:** `.set2fa MyStr0ngPass MyHint`\n\n"
            "⚠️ Delete this message after use!"
        )

    parts = raw.split(maxsplit=1)
    new_password = parts[0]
    hint = parts[1] if len(parts) > 1 else ""

    msg = await event.reply("🔐 **Updating 2FA password...**")

    try:
        # Check if 2FA is currently set to determine current_password
        pwd_info = await event.client(GetPasswordRequest())
        has_password = pwd_info.has_password

        if has_password:
            # We can't change without knowing the old password
            await msg.edit(
                "⚠️ **2FA is already enabled.**\n\n"
                "To **change** your existing password use:\n"
                "`.change2fa <old_password> <new_password> [hint]`\n\n"
                "To **remove** 2FA use:\n"
                "`.remove2fa <current_password>`"
            )
            return

        # No password set yet — set fresh
        await event.client.edit_2fa(
            new_password=new_password,
            hint=hint,
        )
        await msg.edit(
            f"✅ **2FA Password Set Successfully!**\n\n"
            f"🔑 **Password:** `{new_password}`\n"
            f"💡 **Hint:** `{hint or 'None'}`\n\n"
            f"⚠️ **Delete this message NOW to keep it secure!**"
        )

    except Exception as e:
        await msg.edit(f"❌ **Failed to set 2FA:**\n`{e}`")


@CipherElite.on(events.NewMessage(pattern=r"\.change2fa(?:\s+(.+))?$"))
@rishabh()
async def change2fa_cmd(event):
    """
    .change2fa <old_password> <new_password> [hint]
    Changes an existing 2FA password.
    """
    raw = (event.pattern_match.group(1) or "").strip()
    parts = raw.split(maxsplit=2)

    if len(parts) < 2:
        return await event.reply(
            "🔐 **Change 2FA Password**\n\n"
            "**Usage:** `.change2fa <old_password> <new_password> [hint]`\n"
            "**Example:** `.change2fa OldPass NewStr0ng MyHint`\n\n"
            "⚠️ Delete this message after use!"
        )

    old_pass = parts[0]
    new_pass = parts[1]
    hint = parts[2] if len(parts) > 2 else ""

    msg = await event.reply("🔐 **Changing 2FA password...**")
    try:
        await event.client.edit_2fa(
            current_password=old_pass,
            new_password=new_pass,
            hint=hint,
        )
        await msg.edit(
            f"✅ **2FA Password Changed!**\n\n"
            f"🔑 **New Password:** `{new_pass}`\n"
            f"💡 **Hint:** `{hint or 'None'}`\n\n"
            f"⚠️ **Delete this message NOW!**"
        )
    except PasswordHashInvalidError:
        await msg.edit("❌ **Wrong current password.** Try again.")
    except Exception as e:
        await msg.edit(f"❌ **Failed to change 2FA:**\n`{e}`")


@CipherElite.on(events.NewMessage(pattern=r"\.remove2fa(?:\s+(.+))?$"))
@rishabh()
async def remove2fa_cmd(event):
    """
    .remove2fa <current_password>
    Disables 2FA completely.
    """
    password = (event.pattern_match.group(1) or "").strip()
    if not password:
        return await event.reply(
            "🔐 **Remove 2FA**\n\n"
            "**Usage:** `.remove2fa <current_password>`\n\n"
            "⚠️ This will completely disable 2-step verification!"
        )

    msg = await event.reply("🔐 **Removing 2FA...**")
    try:
        await event.client.edit_2fa(
            current_password=password,
            new_password=None,
        )
        await msg.edit(
            "✅ **2FA has been disabled.**\n\n"
            "_Your account no longer has a 2-step verification password._\n\n"
            "⚠️ **Delete this message NOW!**"
        )
    except PasswordHashInvalidError:
        await msg.edit("❌ **Wrong password.** 2FA was NOT removed.")
    except Exception as e:
        await msg.edit(f"❌ **Failed to remove 2FA:** `{e}`")


# ── Channel Transfer Commands ─────────────────────────────────────────────────

@CipherElite.on(events.NewMessage(pattern=r"\.transferchan(?:\s+(.+))?$"))
@rishabh()
async def transferchan_cmd(event):
    """
    .transferchan <@channel_or_id> <@target_user> <2fa_password>

    Transfers ownership of ONE specific channel to the target user.
    The target user MUST already be an admin of the channel.
    """
    raw = (event.pattern_match.group(1) or "").strip()
    parts = raw.split()

    if len(parts) < 3:
        return await event.reply(
            "📢 **Transfer Channel Ownership**\n\n"
            "**Usage:** `.transferchan <@channel> <@user> <2fa_password>`\n"
            "**Example:** `.transferchan @mychannel @friend MyPass123`\n\n"
            "⚠️ The target user must be an **admin** of the channel first!\n"
            "⚠️ Delete this message after use!"
        )

    chan_target = parts[0].lstrip("@")
    user_target = parts[1].lstrip("@")
    twofa_pass  = " ".join(parts[2:])  # support spaces in password

    msg = await event.reply(
        f"🔍 **Resolving entities...**\n"
        f"Channel: `{chan_target}` → User: `@{user_target}`"
    )

    client = event.client

    # Resolve channel
    try:
        channel = await client.get_entity(chan_target)
    except Exception as e:
        return await msg.edit(f"❌ **Could not find channel** `{chan_target}`:\n`{e}`")

    if not isinstance(channel, Channel):
        return await msg.edit("❌ That entity is not a channel.")

    if not getattr(channel, "creator", False):
        return await msg.edit(
            "❌ **You are not the creator** of this channel.\n"
            "_Only the original creator can transfer ownership._"
        )

    # Resolve target user
    try:
        target_user = await client.get_entity(user_target)
    except Exception as e:
        return await msg.edit(f"❌ **Could not find user** `@{user_target}`:\n`{e}`")

    # Compute 2FA SRP
    await msg.edit("🔐 **Verifying 2FA password...**")
    try:
        srp = await _compute_srp(client, twofa_pass)
    except PasswordHashInvalidError:
        return await msg.edit("❌ **Wrong 2FA password.**")
    except Exception as e:
        return await msg.edit(f"❌ **2FA error:** `{e}`")

    # Transfer
    await msg.edit(f"📤 **Transferring** `{channel.title}` → `@{user_target}`...")
    result = await _transfer_channel(client, channel, target_user, srp)

    if result["ok"]:
        await msg.edit(
            f"✅ **Channel Transferred!**\n\n"
            f"📢 **Channel:** `{result['name']}`\n"
            f"👤 **New Owner:** `@{user_target}`\n\n"
            f"⚠️ **Delete this message NOW!**"
        )
    else:
        await msg.edit(
            f"❌ **Transfer Failed for** `{result['name']}`\n\n"
            f"**Reason:** `{result['error']}`"
        )


@CipherElite.on(events.NewMessage(pattern=r"\.transferall(?:\s+(.+))?$"))
@rishabh()
async def transferall_cmd(event):
    """
    .transferall <@target_user> <2fa_password>

    Finds ALL channels where you are the creator and transfers them
    all to the specified user one by one.
    The target user MUST already be an admin in each channel.
    """
    raw = (event.pattern_match.group(1) or "").strip()
    parts = raw.split()

    if len(parts) < 2:
        return await event.reply(
            "📢 **Transfer ALL Owned Channels**\n\n"
            "**Usage:** `.transferall <@user> <2fa_password>`\n"
            "**Example:** `.transferall @friend MyPass123`\n\n"
            "⚠️ Target user must be an **admin in every channel** first!\n"
            "⚠️ This will transfer **ALL channels** you own — cannot be undone!\n"
            "⚠️ Delete this message after use!"
        )

    user_target = parts[0].lstrip("@")
    twofa_pass  = " ".join(parts[1:])

    client = event.client
    msg = await event.reply("🔍 **Scanning your channels...**")

    # Find all owned channels
    owned = await _get_owned_channels(client)
    if not owned:
        return await msg.edit("❌ **No owned channels found.**\n_You must be the original creator._")

    await msg.edit(
        f"📢 **Found {len(owned)} owned channel(s)**\n\n"
        + "\n".join(f"  • `{c.title}`" for c in owned[:20])
        + (f"\n  _(and {len(owned)-20} more)_" if len(owned) > 20 else "")
        + "\n\n🔍 **Resolving target user...**"
    )

    # Resolve target user
    try:
        target_user = await client.get_entity(user_target)
    except Exception as e:
        return await msg.edit(f"❌ **Could not find user** `@{user_target}`:\n`{e}`")

    # Verify 2FA once up front
    await msg.edit("🔐 **Verifying 2FA password...**")
    try:
        # We need a fresh SRP check per transfer (one-time use), so just verify once here
        pwd_info = await client(GetPasswordRequest())
        if not pwd_info.has_password:
            return await msg.edit(
                "❌ **2FA is not enabled on your account.**\n"
                "Channel ownership transfer requires 2FA to be active."
            )
        # Test-compute to validate password (will raise if wrong)
        srp_test = compute_check(pwd_info, twofa_pass)
    except Exception as e:
        return await msg.edit(f"❌ **2FA verification failed:** `{e}`")

    await msg.edit(
        f"✅ **2FA verified**\n"
        f"📤 **Transferring {len(owned)} channel(s) to** `@{user_target}`...\n\n"
        f"⏳ Please wait..."
    )

    # Transfer each channel — must recompute SRP each time (one-time tokens)
    results = []
    for i, channel in enumerate(owned):
        await msg.edit(
            f"📤 **Transferring channel {i+1}/{len(owned)}...**\n"
            f"  ▶ `{channel.title}`"
        )
        try:
            # Recompute fresh SRP for each request
            fresh_pwd = await client(GetPasswordRequest())
            srp = compute_check(fresh_pwd, twofa_pass)
            res = await _transfer_channel(client, channel, target_user, srp)
        except Exception as e:
            res = {"ok": False, "name": channel.title, "error": str(e)}
        results.append(res)
        await asyncio.sleep(2)  # pace to avoid flood

    # Build summary
    ok_list   = [r for r in results if r["ok"]]
    fail_list = [r for r in results if not r["ok"]]

    lines = [
        f"📢 **Bulk Transfer Complete!**\n",
        f"✅ **Transferred ({len(ok_list)}/{len(owned)}):**",
    ]
    for r in ok_list:
        lines.append(f"  ✅ `{r['name']}`")
    if fail_list:
        lines.append(f"\n❌ **Failed ({len(fail_list)}):**")
        for r in fail_list:
            lines.append(f"  ❌ `{r['name']}` — _{r['error']}_")

    lines.append(f"\n👤 **New Owner:** `@{user_target}`")
    lines.append(f"\n⚠️ **Delete this message NOW!**")

    await msg.edit("\n".join(lines))
