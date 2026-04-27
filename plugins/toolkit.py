# =============================================================================
#  CipherElite Userbot Plugin
#
#  Plugin Name:    toolkit
#  Author:         CipherElite Dev (@rishabhops)
#  Repository:     https://github.com/rishabhops/CipherElite
#
#  License:        MIT
#
#  IMPORTANT:
#    â€¢ If you copy, fork, or include this plugin in your own bot,
#      you MUST keep this header intact.
#    â€¢ You MUST give proper credit to the CipherElite Userbot author:
#        â€“ GitHub:    https://github.com/rishabhops/CipherElite
#        â€“ Telegram:  @thanosceo
#
#  Thank you for respecting open-source software!
# =============================================================================

import base64
import datetime
import math
import os
import time
from telethon import events
from utils.utils import CipherElite
from utils.decorators import rishabh
from plugins.bot import add_handler

def init(client_instance):
    """
    Required initialization function that registers commands and descriptions
    """
    commands = [
        ".base64enc <text/reply> - Encode text to base64 string",
        ".base64dec <text/reply> - Decode base64 string to text", 
        ".calc <expression> - Calculate mathematical expressions",
        ".calculate <expression> - Calculate mathematical expressions (alias)",
        ".math <operation> <number> - Perform basic math operations",
        ".unpack <reply to file> - Extract text content from file",
        ".pack <reply to text> [filename] - Save text content as file",
        ".calendar [month/year] - Generate calendar image for specified month/year"
    ]
    description = "ðŸ”§ PARADOX Tools - Advanced utility tools for encoding, calculations, file operations and calendar generation"
    add_handler("toolkit", commands, description)

async def register_commands():
    """
    Main function where command handlers are defined
    """
    
    # Available math operations
    math_cmds = ["sin", "cos", "tan", "square", "cube", "sqroot", "factorial", "power"]
    
    @CipherElite.on(events.NewMessage(pattern=r"\.base64enc\s*(.*)"))
    @rishabh()
    async def base64_encode(event):
        try:
            text_input = event.pattern_match.group(1).strip()
            
            # Get text from command or reply
            if text_input:
                text = text_input
            elif event.reply_to_msg_id:
                reply_message = await event.get_reply_message()
                text = reply_message.text or reply_message.caption or ""
            else:
                await event.reply("ðŸŽ­ **PARADOX Base64 Encoder**\n\n"
                                "âŒ **Error:** Please provide text to encode!\n\n"
                                "**Usage:** `.base64enc Hello World`\n"
                                "**Or reply** to a message with `.base64enc`")
                return
            
            if not text:
                await event.reply("âŒ **PARADOX Error:** No text found to encode!")
                return
            
            status_msg = await event.reply("ðŸŽ­ **PARADOX Encoder**\n\n"
                                         "ðŸ”„ **Processing:** Encoding to Base64...\n"
                                         "âš¡ **Engine:** Advanced Encryption Module")
            
            try:
                encoded = base64.b64encode(text.encode()).decode()
                
                await status_msg.edit(f"ðŸŽ­ **PARADOX Base64 Encoded**\n\n"
                                     f"ðŸ“ **Original Text:** `{text[:50]}{'...' if len(text) > 50 else ''}`\n\n"
                                     f"ðŸ” **Encoded Result:**\n`{encoded}`\n\n"
                                     f"âœ… **Status:** Successfully encoded\n"
                                     f"ðŸ¤– **Powered by PARADOX**")
            except Exception as e:
                await status_msg.edit(f"ðŸŽ­ **PARADOX Encoder Error**\n\n"
                                     f"âŒ **Error:** {str(e)}\n"
                                     f"ðŸ’¡ **Try again with valid text**")
                
        except Exception as e:
            await event.reply(f"ðŸŽ­ **PARADOX System Error**\n\n"
                            f"âŒ **Error:** {str(e)}")
    
    @CipherElite.on(events.NewMessage(pattern=r"\.base64dec\s*(.*)"))
    @rishabh()
    async def base64_decode(event):
        try:
            text_input = event.pattern_match.group(1).strip()
            
            # Get text from command or reply
            if text_input:
                text = text_input
            elif event.reply_to_msg_id:
                reply_message = await event.get_reply_message()
                text = reply_message.text or reply_message.caption or ""
            else:
                await event.reply("ðŸŽ­ **PARADOX Base64 Decoder**\n\n"
                                "âŒ **Error:** Please provide base64 text to decode!\n\n"
                                "**Usage:** `.base64dec SGVsbG8gV29ybGQ=`\n"
                                "**Or reply** to a message with `.base64dec`")
                return
            
            if not text:
                await event.reply("âŒ **PARADOX Error:** No text found to decode!")
                return
            
            status_msg = await event.reply("ðŸŽ­ **PARADOX Decoder**\n\n"
                                         "ðŸ”„ **Processing:** Decoding from Base64...\n"
                                         "âš¡ **Engine:** Advanced Decryption Module")
            
            try:
                decoded = base64.b64decode(text.encode()).decode()
                
                await status_msg.edit(f"ðŸŽ­ **PARADOX Base64 Decoded**\n\n"
                                     f"ðŸ” **Encoded Text:** `{text[:50]}{'...' if len(text) > 50 else ''}`\n\n"
                                     f"ðŸ“ **Decoded Result:**\n`{decoded}`\n\n"
                                     f"âœ… **Status:** Successfully decoded\n"
                                     f"ðŸ¤– **Powered by PARADOX**")
            except Exception as e:
                await status_msg.edit(f"ðŸŽ­ **PARADOX Decoder Error**\n\n"
                                     f"âŒ **Error:** Invalid Base64 string\n"
                                     f"ðŸ’¡ **Make sure the text is properly encoded**")
                
        except Exception as e:
            await event.reply(f"ðŸŽ­ **PARADOX System Error**\n\n"
                            f"âŒ **Error:** {str(e)}")
    
    @CipherElite.on(events.NewMessage(pattern=r"\.(calc|calculate)\s+(.+)"))
    @rishabh()
    async def calculator(event):
        try:
            expression = event.pattern_match.group(2).strip()
            
            if not expression:
                await event.reply("ðŸŽ­ **PARADOX Calculator**\n\n"
                                "âŒ **Error:** Please provide an expression to calculate!\n\n"
                                "**Usage:** `.calc 2 + 2 * 5`\n"
                                "**Example:** `.calculate (10 + 5) / 3`")
                return
            
            status_msg = await event.reply("ðŸŽ­ **PARADOX Calculator**\n\n"
                                         f"ðŸ”¢ **Expression:** `{expression}`\n"
                                         f"ðŸ”„ **Status:** Calculating...\n"
                                         f"âš¡ **Engine:** Advanced Math Processor")
            
            try:
                # Secure evaluation (basic protection)
                allowed_chars = set('0123456789+-*/.() ')
                if not all(c in allowed_chars for c in expression.replace(' ', '')):
                    await status_msg.edit("ðŸŽ­ **PARADOX Calculator Error**\n\n"
                                         "âŒ **Error:** Invalid characters in expression\n"
                                         "ðŸ’¡ **Only numbers and +, -, *, /, (, ) are allowed**")
                    return
                
                result = eval(expression)
                
                await status_msg.edit(f"ðŸŽ­ **PARADOX Calculator Result**\n\n"
                                     f"ðŸ”¢ **Expression:** `{expression}`\n\n"
                                     f"ðŸŽ¯ **Result:** `{result}`\n\n"
                                     f"âœ… **Status:** Calculation completed\n"
                                     f"ðŸ¤– **Powered by PARADOX**")
                                     
            except ZeroDivisionError:
                await status_msg.edit("ðŸŽ­ **PARADOX Calculator Error**\n\n"
                                     "âŒ **Error:** Division by zero\n"
                                     "ðŸ’¡ **Cannot divide by zero**")
            except Exception as e:
                await status_msg.edit("ðŸŽ­ **PARADOX Calculator Error**\n\n"
                                     f"âŒ **Error:** Invalid expression\n"
                                     f"ðŸ’¡ **Check your syntax and try again**")
                
        except Exception as e:
            await event.reply(f"ðŸŽ­ **PARADOX System Error**\n\n"
                            f"âŒ **Error:** {str(e)}")
    
    @CipherElite.on(events.NewMessage(pattern=r"\.math\s+(\w+)\s+(.+)"))
    @rishabh()
    async def math_operations(event):
        try:
            cmd = event.pattern_match.group(1).lower()
            query = event.pattern_match.group(2).strip()
            
            if cmd not in math_cmds:
                await event.reply(f"ðŸŽ­ **PARADOX Math Engine**\n\n"
                                f"âŒ **Unknown operation:** `{cmd}`\n\n"
                                f"**Available operations:**\n"
                                f"`{'`, `'.join(math_cmds)}`\n\n"
                                f"**Usage:** `.math sin 90`")
                return
            
            status_msg = await event.reply("ðŸŽ­ **PARADOX Math Engine**\n\n"
                                         f"ðŸ§® **Operation:** {cmd.upper()}\n"
                                         f"ðŸ”¢ **Input:** {query}\n"
                                         f"ðŸ”„ **Status:** Calculating...\n"
                                         f"âš¡ **Engine:** Advanced Mathematical Processor")
            
            try:
                number = float(query)
                
                if cmd == "sin":
                    result = math.sin(math.radians(number))
                elif cmd == "cos":
                    result = math.cos(math.radians(number))
                elif cmd == "tan":
                    result = math.tan(math.radians(number))
                elif cmd == "square":
                    result = number * number
                elif cmd == "cube":
                    result = number * number * number
                elif cmd == "sqroot":
                    if number < 0:
                        await status_msg.edit("ðŸŽ­ **PARADOX Math Error**\n\n"
                                             "âŒ **Error:** Cannot calculate square root of negative number")
                        return
                    result = math.sqrt(number)
                elif cmd == "factorial":
                    if number < 0 or number != int(number):
                        await status_msg.edit("ðŸŽ­ **PARADOX Math Error**\n\n"
                                             "âŒ **Error:** Factorial only works with non-negative integers")
                        return
                    result = math.factorial(int(number))
                elif cmd == "power":
                    result = math.pow(number, 2)
                
                await status_msg.edit(f"ðŸŽ­ **PARADOX Math Result**\n\n"
                                     f"ðŸ§® **Operation:** {cmd.upper()}\n"
                                     f"ðŸ”¢ **Input:** `{query}`\n\n"
                                     f"ðŸŽ¯ **Result:** `{result}`\n\n"
                                     f"âœ… **Status:** Calculation completed\n"
                                     f"ðŸ¤– **Powered by PARADOX**")
                                     
            except ValueError:
                await status_msg.edit("ðŸŽ­ **PARADOX Math Error**\n\n"
                                     "âŒ **Error:** Invalid number format\n"
                                     "ðŸ’¡ **Please provide a valid number**")
            except Exception as e:
                await status_msg.edit(f"ðŸŽ­ **PARADOX Math Error**\n\n"
                                     f"âŒ **Error:** {str(e)}")
                
        except Exception as e:
            await event.reply(f"ðŸŽ­ **PARADOX System Error**\n\n"
                            f"âŒ **Error:** {str(e)}")
    
    @CipherElite.on(events.NewMessage(pattern=r"\.unpack"))
    @rishabh()
    async def unpack_file(event):
        try:
            if not event.reply_to_msg_id:
                await event.reply("ðŸŽ­ **PARADOX File Unpacker**\n\n"
                                "âŒ **Error:** Please reply to a file!\n\n"
                                "**Usage:** Reply to any text file with `.unpack`\n"
                                "**Supported:** .txt, .py, .js, .json, .xml, etc.")
                return
            
            reply_message = await event.get_reply_message()
            
            if not reply_message.document:
                await event.reply("âŒ **PARADOX Error:** Please reply to a file document!")
                return
            
            status_msg = await event.reply("ðŸŽ­ **PARADOX File Unpacker**\n\n"
                                         "ðŸ“ **Processing:** Downloading file...\n"
                                         "ðŸ”„ **Status:** Extracting content\n"
                                         "âš¡ **Engine:** Advanced File Processor")
            
            # Download file to temporary location
            temp_dir = "temp_paradox"
            os.makedirs(temp_dir, exist_ok=True)
            filename = await reply_message.download_media(file=temp_dir)
            
            try:
                with open(filename, "rb") as f:
                    data = f.read()
                
                # Try to decode as text
                try:
                    text_content = data.decode('utf-8')
                except UnicodeDecodeError:
                    try:
                        text_content = data.decode('latin-1')
                    except:
                        await status_msg.edit("ðŸŽ­ **PARADOX File Unpacker Error**\n\n"
                                             "âŒ **Error:** File is not a text file\n"
                                             "ðŸ’¡ **Only text files can be unpacked**")
                        return
                
                # Limit message length for Telegram
                max_length = 4000
                if len(text_content) > max_length:
                    text_content = text_content[:max_length] + "\n\n... (Content truncated due to length limit)"
                
                await status_msg.edit(f"ðŸŽ­ **PARADOX File Unpacked**\n\n"
                                     f"ðŸ“ **File:** {reply_message.document.attributes[0].file_name if reply_message.document.attributes else 'Unknown'}\n"
                                     f"ðŸ“Š **Size:** {len(data)} bytes\n\n"
                                     f"ðŸ“„ **Content:**\n``````\n\n"
                                     f"ðŸ¤– **Powered by PARADOX**")
                
            except Exception as e:
                await status_msg.edit(f"ðŸŽ­ **PARADOX File Unpacker Error**\n\n"
                                     f"âŒ **Error:** Could not read file content\n"
                                     f"ðŸ’¡ **Make sure it's a valid text file**")
            finally:
                # Cleanup
                if os.path.exists(filename):
                    os.remove(filename)
                
        except Exception as e:
            await event.reply(f"ðŸŽ­ **PARADOX System Error**\n\n"
                            f"âŒ **Error:** {str(e)}")
    
    @CipherElite.on(events.NewMessage(pattern=r"\.pack\s*(.*)"))
    @rishabh()
    async def pack_text(event):
        try:
            filename_input = event.pattern_match.group(1).strip()
            
            if not event.reply_to_msg_id:
                await event.reply("ðŸŽ­ **PARADOX Text Packer**\n\n"
                                "âŒ **Error:** Please reply to a text message!\n\n"
                                "**Usage:** Reply to any text with `.pack [filename]`\n"
                                "**Example:** `.pack my_script.py`")
                return
            
            reply_message = await event.get_reply_message()
            
            if not reply_message.text:
                await event.reply("âŒ **PARADOX Error:** Replied message contains no text!")
                return
            
            # Generate filename
            if filename_input:
                filename = filename_input
            else:
                filename = f"paradox_pack_{int(time.time())}.txt"
            
            status_msg = await event.reply("ðŸŽ­ **PARADOX Text Packer**\n\n"
                                         f"ðŸ“ **Creating:** {filename}\n"
                                         f"ðŸ”„ **Status:** Packing text content...\n"
                                         f"âš¡ **Engine:** Advanced File Generator")
            
            try:
                # Create temporary file
                temp_dir = "temp_paradox"
                os.makedirs(temp_dir, exist_ok=True)
                temp_filepath = os.path.join(temp_dir, filename)
                
                with open(temp_filepath, "w", encoding="utf-8") as f:
                    f.write(reply_message.text)
                
                # Send file
                await event.client.send_file(
                    event.chat_id,
                    temp_filepath,
                    caption=f"ðŸŽ­ **PARADOX Text Packed**\n\n"
                           f"ðŸ“ **Filename:** `{filename}`\n"
                           f"ðŸ“Š **Size:** {len(reply_message.text)} characters\n"
                           f"âœ… **Status:** Successfully packed\n"
                           f"ðŸ¤– **Powered by PARADOX**",
                    reply_to=event.reply_to_msg_id
                )
                
                await status_msg.delete()
                
                # Cleanup
                os.remove(temp_filepath)
                
            except Exception as e:
                await status_msg.edit(f"ðŸŽ­ **PARADOX Text Packer Error**\n\n"
                                     f"âŒ **Error:** Could not create file\n"
                                     f"ðŸ’¡ **Please try again**")
                
        except Exception as e:
            await event.reply(f"ðŸŽ­ **PARADOX System Error**\n\n"
                            f"âŒ **Error:** {str(e)}")
    
    @CipherElite.on(events.NewMessage(pattern=r"\.calendar\s*(.*)"))
    @rishabh()
    async def generate_calendar(event):
        try:
            query_input = event.pattern_match.group(1).strip()
            
            if not query_input:
                # Use current month and year
                now = datetime.datetime.now()
                year = now.year
                month = now.month
            else:
                if "/" in query_input:
                    try:
                        month_str, year_str = query_input.split("/")
                        month = int(month_str)
                        year = int(year_str)
                        
                        if month < 1 or month > 12:
                            await event.reply("ðŸŽ­ **PARADOX Calendar Error**\n\n"
                                            "âŒ **Error:** Invalid month! Use 1-12\n\n"
                                            "**Usage:** `.calendar 12/2024`")
                            return
                    except ValueError:
                        await event.reply("ðŸŽ­ **PARADOX Calendar**\n\n"
                                        "âŒ **Error:** Invalid format!\n\n"
                                        "**Usage:** `.calendar 12/2024`\n"
                                        "**Example:** `.calendar 1/2025`")
                        return
                else:
                    await event.reply("ðŸŽ­ **PARADOX Calendar**\n\n"
                                    "âŒ **Error:** Invalid format!\n\n"
                                    "**Usage:** `.calendar 12/2024`\n"
                                    "**Or use:** `.calendar` for current month")
                    return
            
            status_msg = await event.reply("ðŸŽ­ **PARADOX Calendar Generator**\n\n"
                                         f"ðŸ“… **Generating:** {month}/{year}\n"
                                         f"ðŸ”„ **Status:** Creating calendar...\n"
                                         f"âš¡ **Engine:** Advanced Calendar System")
            
            try:
                # Simple text calendar (since we don't have the image creation function)
                import calendar
                cal = calendar.month(year, month)
                month_name = calendar.month_name[month]
                
                calendar_text = f"ðŸŽ­ **PARADOX Calendar**\n\n"
                calendar_text += f"ðŸ“… **{month_name} {year}**\n\n"
                calendar_text += f"``````\n\n"
                calendar_text += f"âœ… **Generated successfully**\n"
                calendar_text += f"ðŸ¤– **Powered by PARADOX**"
                
                await status_msg.edit(calendar_text)
                
            except Exception as e:
                await status_msg.edit(f"ðŸŽ­ **PARADOX Calendar Error**\n\n"
                                     f"âŒ **Error:** Could not generate calendar\n"
                                     f"ðŸ’¡ **Please check the month/year values**")
                
        except Exception as e:
            await event.reply(f"ðŸŽ­ **PARADOX System Error**\n\n"
                            f"âŒ **Error:** {str(e)}")

