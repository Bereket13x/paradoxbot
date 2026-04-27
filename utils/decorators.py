from functools import wraps
from telethon.tl.functions.channels import GetParticipantRequest
from telethon.tl.types import ChannelParticipantAdmin, ChannelParticipantCreator
from telethon.errors import UserNotParticipantError, ChatAdminRequiredError
from config.config import Config

# ==========================================
# HELPER FUNCTION
# ==========================================
async def is_owner_or_sudo(event):
    """
    Checks if the user sending the command is the deployer (Owner) 
    or a registered Sudo User.
    """
    sender_id = event.sender_id
    me = await event.client.get_me()
    
    if sender_id == me.id or sender_id in Config.SUDO_USERS:
        return True
    return False

# ==========================================
# 1. ADMIN / OWNER / SUDO DECORATOR
# ==========================================
def authorized_users_only(func=None):
    def decorator(f):
        @wraps(f)
        async def wrapper(event):
            sender_id = event.sender_id
            
            # 🎭 PRIORITY 1: Always allow Owner & Sudo users (no exceptions)
            if await is_owner_or_sudo(event):
                print(f"✅ Owner/Sudo user {sender_id} authorized - bypassing checks")
                return await f(event)
            
            # 🎭 PRIORITY 2: Allow in private chats for non-sudo users
            if event.is_private:
                print(f"✅ Private chat authorized for user {sender_id}")
                return await f(event)
            
            # 🎭 PRIORITY 3: Check admin rights for normal users in groups
            try:
                chat = await event.get_chat()
                
                if hasattr(chat, 'admin_rights') and chat.admin_rights:
                    if chat.admin_rights.delete_messages or chat.admin_rights.ban_users:
                        return await f(event)
                
                if hasattr(chat, 'creator') and chat.creator:
                    return await f(event)
                
                try:
                    participant = await event.client(GetParticipantRequest(
                        channel=chat,
                        participant=sender_id
                    ))
                    if isinstance(participant.participant, (ChannelParticipantAdmin, ChannelParticipantCreator)):
                        return await f(event)
                except (UserNotParticipantError, ChatAdminRequiredError, AttributeError):
                    pass
                
            except Exception as e:
                print(f"❌ Error checking admin rights: {e}")
                pass
            
            # 🎭 Deny access
            await event.reply("🎭 **PARADOX Access Denied**\n\n"
                             "❌ **This command is restricted to admins only!**\n"
                             "🛡️ **Required:** Admin privileges, Sudo access, or Bot Owner")
            return
        return wrapper

    # Magic logic to allow both @authorized_users_only and @authorized_users_only()
    if func is None:
        return decorator
    else:
        return decorator(func)

# ==========================================
# 2. OWNER & SUDO ONLY DECORATOR (Silent Fail)
# ==========================================
def rishabh(func=None):
    def decorator(f):
        @wraps(f)
        async def wrapper(event):
            sender_id = event.sender_id

            if not await is_owner_or_sudo(event):
                print(f"❌ Unauthorized access attempt by {sender_id}")
                return

            print(f"✅ Owner/Sudo user {sender_id} executing command: {f.__name__}")

            # ── Capture reply target BEFORE deleting the command ──────────────
            # If the user was replying to a message, responses will also reply
            # to that same original message. Otherwise sent as a plain message.
            original_reply_to = event.reply_to_msg_id  # None if not a reply

            # ── Delete the command message immediately ─────────────────────────
            try:
                await event.delete()
            except Exception:
                pass  # silently ignore if already deleted / no permission

            # ── Track last response for edit-chain support ─────────────────────
            # Plugins often do: event.edit("step 1") … event.edit("step 2")
            # After the command is deleted, the first edit must send a new message;
            # subsequent ones should edit that same message.
            _state = {"last": None}

            # ── Patch event.reply ──────────────────────────────────────────────
            async def smart_reply(message=None, *args, **kwargs):
                kwargs.pop("reply_to", None)
                if original_reply_to:
                    kwargs["reply_to"] = original_reply_to
                msg = await event.respond(message, *args, **kwargs)
                _state["last"] = msg
                return msg

            # ── Patch event.edit ───────────────────────────────────────────────
            # First call → send new message (original is deleted).
            # Subsequent calls → edit that message (animation/progress updates).
            async def smart_edit(message=None, *args, **kwargs):
                if _state["last"] is not None:
                    try:
                        return await _state["last"].edit(message, *args, **kwargs)
                    except Exception:
                        pass  # fall through to send new if edit fails
                # Send fresh message
                kwargs.pop("reply_to", None)
                if original_reply_to:
                    kwargs["reply_to"] = original_reply_to
                msg = await event.respond(message, *args, **kwargs)
                _state["last"] = msg
                return msg

            event.reply = smart_reply
            event.edit = smart_edit

            # ── Patch event.delete to a no-op ─────────────────────────────────
            # Many plugins call event.delete() themselves as a leftover pattern.
            # Since we already deleted the command above, a second delete would
            # crash. Make it silently do nothing instead.
            async def noop_delete(*args, **kwargs):
                pass

            event.delete = noop_delete

            return await f(event)
        return wrapper

    # Magic logic to allow both @rishabh and @rishabh()
    if func is None:
        return decorator
    else:
        return decorator(func)

# ==========================================
# 3. OWNER & SUDO ONLY DECORATOR (With Alert)
# ==========================================
def rishabh_help(func=None):
    def decorator(f):
        @wraps(f)
        async def wrapper(event):
            
            if not await is_owner_or_sudo(event):
                await event.answer(
                    "🎭 **PARADOX Access Restricted!**\n\n"
                    "⚡ **Unauthorized access denied**", 
                    alert=True
                )
                return
                
            return await f(event)
        return wrapper

    # Magic logic to allow both @rishabh_help and @rishabh_help()
    if func is None:
        return decorator
    else:
        return decorator(func)
