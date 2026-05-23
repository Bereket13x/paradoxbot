# =============================================================================
#  PARADOX Userbot Plugin
#
#  Plugin Name:    downloader
#  Description:    Download direct links and upload to Telegram
#  Commands:
#    .dl <url> [-doc] [-name filename]
# =============================================================================

import os
import time
import tempfile
import aiohttp
from urllib.parse import urlparse, unquote

from telethon import events
from utils.utils import CipherElite
from utils.decorators import rishabh
from plugins.bot import add_handler

# ── Plugin registration ────────────────────────────────────────────────────── #

def init(client_instance):
    commands = [
        ".dl <url> - Download and upload from a direct link",
        ".dl <url> -doc - Force upload as an uncompressed document",
        ".dl <url> -name <filename> - Rename the file before uploading"
    ]
    description = "📥 Universal Downloader — Download direct links and upload to Telegram"
    add_handler("dl", commands, description)

# ── Helpers ────────────────────────────────────────────────────────────────── #

def _get_filename(url: str, headers: dict) -> str:
    """Attempt to extract filename from headers or URL."""
    # Try Content-Disposition
    cd = headers.get('Content-Disposition')
    if cd:
        if 'filename=' in cd:
            # Crude extraction; handles filename="foo.ext" or filename=foo.ext
            name = cd.split('filename=')[1].split(';')[0].strip('"\'')
            if name:
                return name
            
    # Try URL path
    parsed = urlparse(url)
    name = unquote(os.path.basename(parsed.path))
    if name:
        return name
        
    return 'downloaded_file.bin'

def _format_bytes(size: int) -> str:
    """Format bytes to a human readable string."""
    if size < 1024:
        return f"{size} B"
    elif size < 1024**2:
        return f"{size / 1024:.2f} KB"
    elif size < 1024**3:
        return f"{size / 1024**2:.2f} MB"
    else:
        return f"{size / 1024**3:.2f} GB"

# ── Command handlers ───────────────────────────────────────────────────────── #

async def register_commands():

    @CipherElite.on(events.NewMessage(outgoing=True, pattern=r"\.dl(?:\s+(.+))?$"))
    @rishabh()
    async def universal_downloader(event):
        """Download from URL and upload to Telegram."""
        raw = (event.pattern_match.group(1) or "").strip()
        if not raw:
            return await event.reply(
                "❌ **Usage:** `.dl <url> [-doc] [-name newname.ext]`\n\n"
                "**Examples:**\n"
                "• `.dl https://example.com/video.mp4`\n"
                "• `.dl https://example.com/video.mp4 -doc`\n"
                "• `.dl https://example.com/video.mp4 -name my_video.mp4`"
            )
            
        args = raw.split()
        
        # Parse flags
        force_doc = False
        custom_name = None
        
        if "-doc" in args:
            force_doc = True
            args.remove("-doc")
            
        if "-name" in args:
            idx = args.index("-name")
            if idx + 1 < len(args):
                custom_name = args[idx + 1]
                args.pop(idx + 1)
            args.remove("-name")
            
        if not args:
            return await event.reply("❌ **Please provide a URL.**")
            
        url = args[0]
        if not url.startswith("http"):
            url = "http://" + url
            
        status = await event.reply(f"📥 **Analyzing link...**\n`{url}`")
        
        tmp_dir = tempfile.mkdtemp()
        downloaded_file = None
        
        try:
            # We use aiohttp for async streaming download
            async with aiohttp.ClientSession() as session:
                # 1. HEAD request to check size and get filename
                try:
                    async with session.head(url, allow_redirects=True) as resp:
                        content_length = resp.headers.get('Content-Length')
                        final_url = str(resp.url)
                        headers = resp.headers
                except Exception:
                    # Some servers block HEAD requests, fallback to GET stream
                    content_length = None
                    final_url = url
                    headers = {}
                
                # Telegram size limit is 2GB for premium/userbots
                if content_length and int(content_length) > 2 * 1024**3:
                    return await status.edit(f"❌ **File too large for Telegram ({_format_bytes(int(content_length))}). Maximum allowed is 2 GB.**")
                    
                filename = custom_name or _get_filename(final_url, headers)
                downloaded_file = os.path.join(tmp_dir, filename)
                
                # 2. GET request to download in chunks
                last_edit_time = time.time()
                await status.edit(f"📥 **Downloading:** `{filename}`\n⏳ _Please wait..._")
                
                async with session.get(url, allow_redirects=True) as resp:
                    if resp.status >= 400:
                        return await status.edit(f"❌ **Download failed: HTTP {resp.status}**")
                        
                    total_size = int(resp.headers.get('Content-Length', 0))
                    downloaded = 0
                    
                    with open(downloaded_file, 'wb') as f:
                        async for chunk in resp.content.iter_chunked(1024 * 1024): # 1MB chunks
                            if not chunk:
                                break
                            f.write(chunk)
                            downloaded += len(chunk)
                            
                            # Update progress every ~3 seconds to avoid flood waits
                            now = time.time()
                            if total_size > 0 and now - last_edit_time > 3:
                                percent = (downloaded / total_size) * 100
                                try:
                                    await status.edit(
                                        f"📥 **Downloading:** `{filename}`\n"
                                        f"📊 **Progress:** {percent:.1f}%\n"
                                        f"💾 **Downloaded:** {_format_bytes(downloaded)} / {_format_bytes(total_size)}"
                                    )
                                    last_edit_time = now
                                except Exception:
                                    pass
                                    
            # Check final size
            file_size = os.path.getsize(downloaded_file)
            if file_size > 2 * 1024**3:
                return await status.edit(f"❌ **Downloaded file is too large for Telegram ({_format_bytes(file_size)}).**")
                
            await status.edit(f"📤 **Uploading to Telegram:** `{filename}`\n⏳ _Please wait..._")
            
            # 3. Upload with progress callback
            last_upload_time = time.time()
            
            async def upload_progress(current, total):
                nonlocal last_upload_time
                now = time.time()
                # Update every 3 seconds
                if now - last_upload_time > 3:
                    percent = (current / total) * 100
                    try:
                        await status.edit(
                            f"📤 **Uploading:** `{filename}`\n"
                            f"📊 **Progress:** {percent:.1f}%\n"
                            f"💾 **Uploaded:** {_format_bytes(current)} / {_format_bytes(total)}"
                        )
                        last_upload_time = now
                    except Exception:
                        pass

            # Send the file
            caption = f"✅ **Downloaded:** `{filename}`\n🔗 [Source Link]({url})"
            
            await event.client.send_file(
                event.chat_id,
                downloaded_file,
                caption=caption,
                force_document=force_doc,
                progress_callback=upload_progress,
                supports_streaming=True # Good for videos
            )
            
            await status.edit(f"✅ **Successfully downloaded and uploaded!**\n📁 `{filename}`")
            
        except Exception as e:
            await status.edit(f"❌ **Error:** `{str(e)[:300]}`")
            
        finally:
            # 4. Cleanup temp files
            if downloaded_file and os.path.exists(downloaded_file):
                try:
                    os.remove(downloaded_file)
                except Exception:
                    pass
            try:
                os.rmdir(tmp_dir)
            except Exception:
                pass
