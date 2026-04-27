import asyncio
from telethon import events
from utils.utils import CipherElite
from utils.decorators import rishabh
from plugins.bot import add_handler

def init(client_instance):
    commands = [
        ".spam [count] [message] - Spam message multiple times with PARADOX power",
        ".dspam [count] [delay] [message] - Spam with custom delay between messages",
        ".mspam [count] [reply to media] - Spam media/files multiple times", 
        ".stopspam - Stop all active spam tasks in current chat",
        ".listspam - Show all active spam operations across chats"
    ]
    
    description = "ðŸ’¥ PARADOX Spam Engine - Advanced message spamming with military precision"
    
    # Debug: Print what we're registering
    print("ðŸŽ­ REGISTERING SPAM COMMANDS:")
    for i, cmd in enumerate(commands):
        print(f"  {i+1}: {cmd}")
    
    add_handler("spam", commands, description)

async def register_commands():
    """
    PARADOX spam system with advanced task management
    """
    
    # Global spam task tracker
    cipher_spam_tasks = {}
    
    class CipherEliteSpamEngine:
        def __init__(self):
            self.active_operations = {}
            self.spam_stats = {
                'total_sent': 0,
                'active_tasks': 0,
                'completed_operations': 0
            }
        
        async def execute_spam_operation(self, client, chat_id, message_content=None, 
                                       count=1, reply_to=None, delay=0, media_msg=None, 
                                       stop_event=None, operation_type="text"):
            """Execute spam operation with PARADOX precision"""
            sent_count = 0
            
            for i in range(count):
                if stop_event and stop_event.is_set():
                    break
                
                try:
                    if operation_type == "media" and media_msg:
                        # Forward media message
                        await client.forward_messages(chat_id, media_msg)
                    else:
                        # Send text message
                        await client.send_message(
                            chat_id,
                            message_content,
                            reply_to=reply_to
                        )
                    
                    sent_count += 1
                    self.spam_stats['total_sent'] += 1
                    
                    # Add delay if specified
                    if delay > 0:
                        await asyncio.sleep(delay)
                    else:
                        # Minimal delay to prevent rate limiting
                        await asyncio.sleep(0.1)
                        
                except Exception as e:
                    print(f"âŒ PARADOX Spam Error: {e}")
                    continue
            
            # Cleanup task
            try:
                if stop_event:
                    stop_event.set()
                task_list = cipher_spam_tasks.get(chat_id, [])
                if stop_event in task_list:
                    task_list.remove(stop_event)
                if not task_list:
                    cipher_spam_tasks.pop(chat_id, None)
                    
                self.spam_stats['completed_operations'] += 1
                    
            except Exception:
                pass
            
            return sent_count
    
    # Initialize spam engine
    spam_engine = CipherEliteSpamEngine()
    
    @CipherElite.on(events.NewMessage(pattern=r"\.spam\s+(\d+)\s+(.+)"))
    @rishabh()
    async def cipher_elite_spam(event):
        try:
            count = int(event.pattern_match.group(1))
            message_content = event.pattern_match.group(2).strip()
            
            if count <= 0 or count > 500:
                await event.reply("ðŸŽ­ **PARADOX Spam Engine**\n\n"
                                "âŒ **Invalid count!** Use 1-500\n"
                                "ðŸ’¡ **Usage:** `.spam 10 Hello World`")
                return
            
            if not message_content:
                await event.reply("âŒ **PARADOX Error:** Please provide message content!")
                return
            
            chat_id = event.chat_id
            reply_to = event.reply_to_msg_id
            
            # Create stop event for this operation
            stop_event = asyncio.Event()
            
            # Add to active tasks
            if chat_id in cipher_spam_tasks:
                cipher_spam_tasks[chat_id].append(stop_event)
            else:
                cipher_spam_tasks[chat_id] = [stop_event]
            
            # Show operation status
            status_msg = await event.reply(f"ðŸŽ­ **PARADOX Spam Engine**\n\n"
                                         f"ðŸ’¥ **Operation:** TEXT SPAM\n"
                                         f"ðŸŽ¯ **Target:** Current Chat\n"
                                         f"ðŸ“Š **Count:** {count} messages\n"
                                         f"âš¡ **Status:** Initializing spam protocol...\n"
                                         f"ðŸ”¥ **Message:** `{message_content[:30]}{'...' if len(message_content) > 30 else ''}`")
            
            # Delete command message
            await event.delete()
            
            # Execute spam operation
            sent_count = await spam_engine.execute_spam_operation(
                event.client,
                chat_id,
                message_content=message_content,
                count=count,
                reply_to=reply_to,
                delay=0,
                stop_event=stop_event,
                operation_type="text"
            )
            
            # Update status with results
            await status_msg.edit(f"ðŸŽ­ **PARADOX Spam Complete**\n\n"
                                 f"ðŸ’¥ **Operation:** TEXT SPAM\n"
                                 f"âœ… **Sent:** {sent_count}/{count} messages\n"
                                 f"ðŸŽ¯ **Success Rate:** {int((sent_count/count)*100)}%\n"
                                 f"ðŸ”¥ **Status:** OPERATION COMPLETE\n"
                                 f"ðŸ¤– **Powered by PARADOX**")
            
            # Auto-delete status after 10 seconds
            await asyncio.sleep(10)
            await status_msg.delete()
            
        except ValueError:
            await event.reply("ðŸŽ­ **PARADOX Spam Error**\n\n"
                            "âŒ **Invalid number format!**\n"
                            "ðŸ’¡ **Usage:** `.spam 10 Hello World`")
        except Exception as e:
            await event.reply(f"ðŸŽ­ **PARADOX spam system Error**\n\n"
                            f"âŒ **Error:** {str(e)[:100]}...")
    
    @CipherElite.on(events.NewMessage(pattern=r"\.dspam\s+(\d+)\s+(\d+\.?\d*)\s+(.+)"))
    @rishabh()
    async def cipher_elite_delay_spam(event):
        try:
            count = int(event.pattern_match.group(1))
            delay = float(event.pattern_match.group(2))
            message_content = event.pattern_match.group(3).strip()
            
            if count <= 0 or count > 200:
                await event.reply("ðŸŽ­ **PARADOX Delay Spam Engine**\n\n"
                                "âŒ **Invalid count!** Use 1-200 for delay spam\n"
                                "ðŸ’¡ **Usage:** `.dspam 10 2.5 Hello World`")
                return
            
            if delay < 0 or delay > 60:
                await event.reply("âŒ **Invalid delay!** Use 0-60 seconds")
                return
            
            chat_id = event.chat_id
            reply_to = event.reply_to_msg_id
            
            # Create stop event
            stop_event = asyncio.Event()
            
            if chat_id in cipher_spam_tasks:
                cipher_spam_tasks[chat_id].append(stop_event)
            else:
                cipher_spam_tasks[chat_id] = [stop_event]
            
            # Calculate estimated completion time
            estimated_time = int(count * (delay + 0.1))
            
            status_msg = await event.reply(f"ðŸŽ­ **PARADOX Delay Spam Engine**\n\n"
                                         f"ðŸ’¥ **Operation:** DELAY SPAM\n"
                                         f"ðŸ“Š **Count:** {count} messages\n"
                                         f"â±ï¸ **Delay:** {delay}s between messages\n"
                                         f"ðŸ• **Estimated Time:** ~{estimated_time}s\n"
                                         f"âš¡ **Status:** Precision timing protocol active...")
            
            await event.delete()
            
            # Execute delay spam
            sent_count = await spam_engine.execute_spam_operation(
                event.client,
                chat_id,
                message_content=message_content,
                count=count,
                reply_to=reply_to,
                delay=delay,
                stop_event=stop_event,
                operation_type="text"
            )
            
            await status_msg.edit(f"ðŸŽ­ **PARADOX Delay Spam Complete**\n\n"
                                 f"ðŸ’¥ **Operation:** DELAY SPAM\n"
                                 f"âœ… **Sent:** {sent_count}/{count} messages\n"
                                 f"â±ï¸ **Delay Used:** {delay}s\n"
                                 f"ðŸŽ¯ **Success Rate:** {int((sent_count/count)*100)}%\n"
                                 f"ðŸ”¥ **Status:** PRECISION OPERATION COMPLETE\n"
                                 f"ðŸ¤– **Powered by PARADOX**")
            
            await asyncio.sleep(10)
            await status_msg.delete()
            
        except ValueError:
            await event.reply("ðŸŽ­ **PARADOX Delay Spam Error**\n\n"
                            "âŒ **Invalid format!**\n"
                            "ðŸ’¡ **Usage:** `.dspam 10 2.5 Hello World`\n"
                            "ðŸ“ **Format:** count delay(seconds) message")
        except Exception as e:
            await event.reply(f"ðŸŽ­ **PARADOX System Error**\n\n"
                            f"âŒ **Error:** {str(e)[:100]}...")
    
    @CipherElite.on(events.NewMessage(pattern=r"\.mspam\s+(\d+)"))
    @rishabh()
    async def cipher_elite_media_spam(event):
        try:
            count = int(event.pattern_match.group(1))
            
            if not event.reply_to_msg_id:
                await event.reply("ðŸŽ­ **PARADOX Media Spam Engine**\n\n"
                                "âŒ **Error:** Please reply to a media message!\n\n"
                                "ðŸ’¡ **Usage:** Reply to any image/video/file with `.mspam 10`\n"
                                "ðŸŽ¯ **Supported:** Images, Videos, Documents, Stickers")
                return
            
            if count <= 0 or count > 100:
                await event.reply("âŒ **Invalid count!** Use 1-100 for media spam")
                return
            
            reply_message = await event.get_reply_message()
            
            if not reply_message.media:
                await event.reply("âŒ **No media found in replied message!**")
                return
            
            chat_id = event.chat_id
            
            # Create stop event
            stop_event = asyncio.Event()
            
            if chat_id in cipher_spam_tasks:
                cipher_spam_tasks[chat_id].append(stop_event)
            else:
                cipher_spam_tasks[chat_id] = [stop_event]
            
            # Determine media type
            media_type = "Unknown"
            if reply_message.photo:
                media_type = "Image"
            elif reply_message.video:
                media_type = "Video"
            elif reply_message.document:
                media_type = "Document"
            elif reply_message.sticker:
                media_type = "Sticker"
            
            status_msg = await event.reply(f"ðŸŽ­ **PARADOX Media Spam Engine**\n\n"
                                         f"ðŸ’¥ **Operation:** MEDIA SPAM\n"
                                         f"ðŸ“¸ **Media Type:** {media_type}\n"
                                         f"ðŸ“Š **Count:** {count} times\n"
                                         f"âš¡ **Status:** Media replication protocol active...")
            
            await event.delete()
            
            # Execute media spam
            sent_count = await spam_engine.execute_spam_operation(
                event.client,
                chat_id,
                count=count,
                media_msg=reply_message,
                stop_event=stop_event,
                operation_type="media"
            )
            
            await status_msg.edit(f"ðŸŽ­ **PARADOX Media Spam Complete**\n\n"
                                 f"ðŸ’¥ **Operation:** MEDIA SPAM\n"
                                 f"ðŸ“¸ **Type:** {media_type}\n"
                                 f"âœ… **Sent:** {sent_count}/{count} media files\n"
                                 f"ðŸŽ¯ **Success Rate:** {int((sent_count/count)*100)}%\n"
                                 f"ðŸ”¥ **Status:** MEDIA REPLICATION COMPLETE\n"
                                 f"ðŸ¤– **Powered by PARADOX**")
            
            await asyncio.sleep(10)
            await status_msg.delete()
            
        except ValueError:
            await event.reply("âŒ **Invalid number format!**")
        except Exception as e:
            await event.reply(f"ðŸŽ­ **PARADOX Media Spam Error**\n\n"
                            f"âŒ **Error:** {str(e)[:100]}...")
    
    @CipherElite.on(events.NewMessage(pattern=r"\.stopspam"))
    @rishabh()
    async def cipher_elite_stop_spam(event):
        try:
            chat_id = event.chat_id
            
            if chat_id not in cipher_spam_tasks or not cipher_spam_tasks[chat_id]:
                await event.reply("ðŸŽ­ **PARADOX Spam Control**\n\n"
                                "âŒ **No active spam operations in this chat**\n"
                                "ðŸ’¡ **All operations already completed or stopped**")
                return
            
            # Stop all operations in this chat
            active_count = len(cipher_spam_tasks[chat_id])
            
            for stop_event in cipher_spam_tasks[chat_id]:
                stop_event.set()
            
            # Clear the task list
            cipher_spam_tasks.pop(chat_id, None)
            
            chat_name = "Current Chat"
            try:
                chat = await event.get_chat()
                chat_name = getattr(chat, 'title', getattr(chat, 'first_name', 'Current Chat'))
            except:
                pass
            
            status_msg = await event.reply(f"ðŸŽ­ **PARADOX Operation Terminated**\n\n"
                                         f"ðŸ›‘ **Action:** EMERGENCY STOP\n"
                                         f"ðŸŽ¯ **Target:** {chat_name}\n"
                                         f"ðŸ“Š **Stopped:** {active_count} active operation(s)\n"
                                         f"âœ… **Status:** ALL SPAM OPERATIONS TERMINATED\n\n"
                                         f"ðŸ¤– **PARADOX Security Protocol**")
            
            await asyncio.sleep(5)
            await status_msg.delete()
            await event.delete()
            
        except Exception as e:
            await event.reply(f"âŒ **Stop spam error:** {str(e)}")
    
    @CipherElite.on(events.NewMessage(pattern=r"\.listspam"))
    @rishabh()
    async def cipher_elite_list_spam(event):
        try:
            if not cipher_spam_tasks:
                await event.reply("ðŸŽ­ **PARADOX Spam Monitor**\n\n"
                                "âœ… **No active spam operations detected**\n"
                                "ðŸ›¡ï¸ **All systems clear**\n"
                                "ðŸ“Š **Status:** IDLE MODE")
                return
            
            list_msg = f"ðŸŽ­ **PARADOX Active Operations**\n\n"
            list_msg += f"ðŸ“Š **Global Spam Statistics:**\n"
            list_msg += f"âš¡ **Total Sent:** {spam_engine.spam_stats['total_sent']} messages\n"
            list_msg += f"ðŸ”„ **Completed Ops:** {spam_engine.spam_stats['completed_operations']}\n\n"
            list_msg += f"ðŸŽ¯ **Active Operations by Chat:**\n"
            
            for chat_id, task_list in cipher_spam_tasks.items():
                if task_list:  # Only show chats with active tasks
                    try:
                        chat = await event.client.get_entity(chat_id)
                        chat_name = getattr(chat, 'title', getattr(chat, 'first_name', f'Chat {chat_id}'))
                    except:
                        chat_name = f"Chat ID: {chat_id}"
                    
                    list_msg += f"ðŸ”¸ **{chat_name}**\n"
                    list_msg += f"   ðŸ“ **Chat ID:** `{chat_id}`\n"
                    list_msg += f"   âš¡ **Active Tasks:** {len(task_list)}\n\n"
            
            list_msg += f"ðŸ¤– **PARADOX Monitoring System**"
            
            await event.reply(list_msg)
            
        except Exception as e:
            await event.reply(f"âŒ **List spam error:** {str(e)}")
    
    @CipherElite.on(events.NewMessage(pattern=r"\.spamstats"))
    @rishabh()
    async def cipher_elite_spam_stats(event):
        try:
            active_chats = len(cipher_spam_tasks)
            total_active_tasks = sum(len(tasks) for tasks in cipher_spam_tasks.values())
            
            stats_msg = f"ðŸŽ­ **PARADOX Spam Engine Statistics**\n\n"
            stats_msg += f"ðŸ“Š **Performance Metrics:**\n"
            stats_msg += f"âš¡ **Total Messages Sent:** {spam_engine.spam_stats['total_sent']:,}\n"
            stats_msg += f"ðŸ”„ **Completed Operations:** {spam_engine.spam_stats['completed_operations']}\n"
            stats_msg += f"ðŸŽ¯ **Active Chats:** {active_chats}\n"
            stats_msg += f"ðŸ“ˆ **Active Tasks:** {total_active_tasks}\n\n"
            
            if active_chats > 0:
                stats_msg += f"ðŸ”¥ **Status:** HIGH ACTIVITY\n"
            else:
                stats_msg += f"âœ… **Status:** STANDBY MODE\n"
            
            stats_msg += f"ðŸ¤– **PARADOX Analytics**"
            
            await event.reply(stats_msg)
            
        except Exception as e:
            await event.reply(f"âŒ **Stats error:** {str(e)}")


