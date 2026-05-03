import os
from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS
from telethon import events
from utils.utils import CipherElite
from plugins.bot import add_handler
from utils.decorators import rishabh

def get_exif_data(image_path):
    exif_data = {}
    try:
        image = Image.open(image_path)
        info = image._getexif()
        if info:
            for tag, value in info.items():
                decoded = TAGS.get(tag, tag)
                if decoded == "GPSInfo":
                    gps_data = {}
                    for t in value:
                        sub_decoded = GPSTAGS.get(t, t)
                        gps_data[sub_decoded] = value[t]
                    exif_data[decoded] = gps_data
                else:
                    # Clean up weird bytes/unprintable data
                    if isinstance(value, bytes):
                        try:
                            value = value.decode('utf-8').strip('\x00')
                        except UnicodeDecodeError:
                            value = "<Binary Data>"
                    elif isinstance(value, str):
                        value = value.strip('\x00')
                    exif_data[decoded] = value
    except Exception as e:
        print(f"EXIF parsing error: {e}")
    return exif_data

def get_lat_lon(exif_data):
    lat = None
    lon = None
    if "GPSInfo" in exif_data:
        gps_info = exif_data["GPSInfo"]
        gps_lat = gps_info.get("GPSLatitude")
        gps_lat_ref = gps_info.get("GPSLatitudeRef")
        gps_lon = gps_info.get("GPSLongitude")
        gps_lon_ref = gps_info.get("GPSLongitudeRef")
        
        if gps_lat and gps_lat_ref and gps_lon and gps_lon_ref:
            try:
                lat_d = float(gps_lat[0])
                lat_m = float(gps_lat[1])
                lat_s = float(gps_lat[2])
                lat = lat_d + (lat_m / 60.0) + (lat_s / 3600.0)
                
                lon_d = float(gps_lon[0])
                lon_m = float(gps_lon[1])
                lon_s = float(gps_lon[2])
                lon = lon_d + (lon_m / 60.0) + (lon_s / 3600.0)
                
                if gps_lat_ref != "N":
                    lat = -lat
                if gps_lon_ref != "E":
                    lon = -lon
            except Exception:
                pass
    return lat, lon

def init(client_instance):
    commands = [
        ".exif - Extract hidden EXIF metadata and GPS coordinates from an image file"
    ]
    description = (
        "📍 **OSINT GPS & EXIF Extractor**\n"
        "Extracts hidden metadata embedded inside uncompressed photos.\n"
        "Can reveal Camera Model, Original Date, and exact GPS location.\n\n"
        "⚠️ *Note: Telegram automatically removes EXIF data from photos sent with compression. You must reply to an image sent as a Document/File.*"
    )
    add_handler("osint", commands, description)

@CipherElite.on(events.NewMessage(pattern=r"^\.exif$", outgoing=True))
@rishabh()
async def extract_exif(event):
    reply_msg = await event.get_reply_message()
    if not reply_msg or not reply_msg.media:
        return await event.reply("❌ **Error:** Please reply to an image/document to extract EXIF data!")
        
    # Check if it's compressed (Telegram wipes EXIF on compressed photos)
    is_compressed_photo = False
    if hasattr(reply_msg.media, 'photo'):
        is_compressed_photo = True
        
    status_msg = await event.reply("🔍 **Scanning image for embedded metadata...**")
    
    try:
        downloaded_file = await reply_msg.download_media()
        if not downloaded_file:
            return await status_msg.edit("❌ **Failed to download the media.**")
            
        exif_data = get_exif_data(downloaded_file)
        
        if not exif_data:
            warn_msg = "⚠️ **No EXIF Metadata Found!**\n\n"
            if is_compressed_photo:
                warn_msg += "Telegram automatically deletes EXIF data from normal photos. To extract data, the sender must send the photo as an **Uncompressed Document/File**."
            else:
                warn_msg += "This image file does not contain any embedded metadata (it may have been stripped or wasn't taken with a camera/smartphone)."
            
            os.remove(downloaded_file)
            return await status_msg.edit(warn_msg)
            
        # Parse standard metadata
        make = exif_data.get('Make', 'Unknown')
        model = exif_data.get('Model', 'Unknown')
        datetime_orig = exif_data.get('DateTimeOriginal', exif_data.get('DateTime', 'Unknown'))
        software = exif_data.get('Software', 'Unknown')
        
        lat, lon = get_lat_lon(exif_data)
        
        # Build the final text
        result = "📍 **OSINT Image Analysis Complete**\n\n"
        result += f"📱 **Camera Make:** `{make}`\n"
        result += f"📷 **Camera Model:** `{model}`\n"
        result += f"📅 **Date Taken:** `{datetime_orig}`\n"
        if software != 'Unknown':
            result += f"💻 **Software/Editor:** `{software}`\n"
            
        result += "\n🌍 **GPS Location Data:**\n"
        if lat and lon:
            maps_url = f"https://www.google.com/maps?q={lat},{lon}"
            result += f"Latitude: `{lat:.6f}`\n"
            result += f"Longitude: `{lon:.6f}`\n\n"
            result += f"🗺️ [**Open Location in Google Maps**]({maps_url})"
        else:
            result += "❌ *No GPS coordinates found in this image.*"
            
        await status_msg.edit(result, link_preview=False)
        os.remove(downloaded_file)
        
    except Exception as e:
        await status_msg.edit(f"❌ **Error during extraction:** `{str(e)}`")
        if 'downloaded_file' in locals() and downloaded_file and os.path.exists(downloaded_file):
            os.remove(downloaded_file)
