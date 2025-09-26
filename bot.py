# bot.py - إصدار معدل مع إصلاح TikTok
from dotenv import load_dotenv
load_dotenv()

import os, re, tempfile, asyncio, logging, json, requests
from typing import Optional, Tuple
from yt_dlp import YoutubeDL
from telegram import Update, InputFile
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

# ==== الإعدادات ====
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("❌ BOT_TOKEN مفقود في ملف .env")

TELEGRAM_LIMIT = 49 * 1024 * 1024

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MediaDownloader:
    def __init__(self):
        self.supported_platforms = [
            "youtube.com", "youtu.be", "tiktok.com", "instagram.com",
            "x.com", "twitter.com", "facebook.com", "fb.watch",
            "reddit.com", "pinterest.com", "twitch.tv", "dailymotion.com",
            "vimeo.com", "rumble.com", "bilibili.com", "likee.com"
        ]
    
    def is_supported_url(self, url: str) -> bool:
        url_lower = url.lower()
        return any(platform in url_lower for platform in self.supported_platforms)
    
    def get_tiktok_headers(self):
        """إعدادات headers خاصة لـ TikTok"""
        return {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Referer': 'https://www.tiktok.com/',
            'Accept': '*/*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
        }
    
    def download_media(self, url: str, audio_only: bool = False) -> Tuple[Optional[str], str]:
        if not self.is_supported_url(url):
            return None, "الرابط غير مدعوم"
        
        temp_dir = tempfile.mkdtemp(prefix="download_")
        
        try:
            # إعدادات أساسية لـ yt-dlp
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'ignoreerrors': False,
                'nooverwrites': True,
                'restrictfilenames': True,
                'socket_timeout': 30,
                'retries': 3,
                'fragment_retries': 3,
                'extractor_retries': 3,
                'noprogress': True,
                'outtmpl': os.path.join(temp_dir, '%(title).100s.%(ext)s'),
            }
            
            # إعدادات خاصة لـ TikTok
            if 'tiktok.com' in url.lower():
                ydl_opts.update({
                    'extractor_args': {
                        'tiktok': {
                            'app_version': '20.9.3',
                            'manifest_app_version': '209303',
                        }
                    },
                    'http_headers': self.get_tiktok_headers(),
                    'overrides': {
                        'format': 'best[ext=mp4]/best',
                    }
                })
            
            # إعدادات الصوت أو الفيديو
            if audio_only:
                ydl_opts['format'] = 'bestaudio/best'
                ydl_opts['postprocessors'] = [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }]
            else:
                ydl_opts['format'] = 'best[height<=1080]/best[height<=720]/best'
            
            # المحاولة الأولى بـ yt-dlp
            with YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                
                if info:
                    title = info.get('title', 'media')[:100]
                    
                    # البحث عن الملف المحمل
                    for filename in os.listdir(temp_dir):
                        file_path = os.path.join(temp_dir, filename)
                        if os.path.isfile(file_path) and os.path.getsize(file_path) > 0:
                            return file_path, title
            
            # إذا فشل yt-dlp مع TikTok، جرب طريقة بديلة
            if 'tiktok.com' in url.lower():
                return self.download_tiktok_alternative(url, temp_dir, audio_only)
                
            return None, "فشل في التحميل"
                
        except Exception as e:
            logger.error(f"خطأ في التنزيل: {str(e)}")
            # إذا كان TikTok، جرب الطريقة البديلة
            if 'tiktok.com' in url.lower():
                try:
                    return self.download_tiktok_alternative(url, temp_dir, audio_only)
                except Exception as e2:
                    logger.error(f"الطريقة البديلة فشلت أيضًا: {str(e2)}")
            return None, f"خطأ: {str(e)}"
    
    def download_tiktok_alternative(self, url: str, temp_dir: str, audio_only: bool = False) -> Tuple[Optional[str], str]:
        """طريقة بديلة لتحميل TikTok باستخدام API خارجي"""
        try:
            # استخدم API بديل لـ TikTok (مثال)
            api_url = f"https://www.tikwm.com/api/?url={url}"
            response = requests.get(api_url, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('code') == 0:
                    video_url = data['data'].get('play')
                    if video_url:
                        # حمل الفيديو من الرابط المباشر
                        video_response = requests.get(video_url, stream=True, timeout=30)
                        if video_response.status_code == 200:
                            filename = os.path.join(temp_dir, "tiktok_video.mp4")
                            with open(filename, 'wb') as f:
                                for chunk in video_response.iter_content(chunk_size=8192):
                                    f.write(chunk)
                            return filename, "TikTok Video"
            
            return None, "فشل في تحميل TikTok"
            
        except Exception as e:
            logger.error(f"خطأ في الطريقة البديلة: {str(e)}")
            return None, f"خطأ TikTok: {str(e)}"

# ==== الباقي بدون تغيير ====
downloader = MediaDownloader()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = """
🎬 **بوت تحميل مقاطع السوشل ميديا - الإصدار المحسن**

✅ **المشاكل التي تم إصلاحها:**
- TikTok يعمل الآن بشكل أفضل
- دعم للمنصات المختلفة

📥 **كيفية الاستخدام:**
- أرسل رابط المقطع لتحميل الفيديو
- اكتب "صوت" قبل الرابط لتحميل الصوت فقط

📱 **المنصات المدعومة:**
يوتيوب، تيك توك، انستجرام، تويتر، فيسبوك، ريديت، وغيرها
"""
    await update.message.reply_text(help_text)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = (update.message.text or "").strip()
    
    if not user_text:
        await update.message.reply_text("❌ أرسل رابط المقطع")
        return
    
    audio_only = user_text.startswith("صوت")
    if audio_only:
        url_match = re.search(r'(https?://\S+)', user_text)
        if not url_match:
            await update.message.reply_text("❌ أرسل رابط صحيح بعد كلمة 'صوت'")
            return
        url = url_match.group(1)
    else:
        url = user_text
    
    if not re.match(r'^https?://', url, re.IGNORECASE):
        await update.message.reply_text("❌ الرابط يجب أن يبدأ بـ http:// أو https://")
        return
    
    if not downloader.is_supported_url(url):
        await update.message.reply_text("❌ هذا الرابط غير مدعوم حالياً")
        return
    
    wait_msg = await update.message.reply_text("⏳ جاري التحميل...")
    file_path = None
    
    try:
        file_path, title = await asyncio.get_event_loop().run_in_executor(
            None, downloader.download_media, url, audio_only
        )
        
        if not file_path or not os.path.exists(file_path):
            await wait_msg.edit_text("❌ فشل في تحميل المقطع")
            return
        
        file_size = os.path.getsize(file_path)
        if file_size > TELEGRAM_LIMIT:
            await wait_msg.edit_text(f"❌ الملف كبير جداً ({file_size//1024//1024}MB) - الحد الأقصى 50MB")
            return
        
        with open(file_path, 'rb') as file:
            if audio_only:
                await update.message.reply_audio(
                    InputFile(file, filename=os.path.basename(file_path)),
                    title=title[:64],
                    duration=0
                )
            else:
                await update.message.reply_video(
                    InputFile(file, filename=os.path.basename(file_path)),
                    caption=title[:1024],
                    supports_streaming=True
                )
        
        await wait_msg.delete()
        
    except Exception as e:
        logger.error(f"خطأ: {str(e)}")
        await wait_msg.edit_text(f"❌ حصل خطأ: {str(e)[:200]}")
    
    finally:
        if file_path and os.path.exists(file_path):
            try:
                temp_dir = os.path.dirname(file_path)
                os.remove(file_path)
                if os.path.exists(temp_dir):
                    os.rmdir(temp_dir)
            except Exception as e:
                logger.error(f"خطأ في التنظيف: {e}")

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"خطأ: {context.error}")

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_error_handler(error_handler)
    
    print("✅ البوت شغال الآن مع إصلاح TikTok!")
    app.run_polling()

if __name__ == "__main__":
    main()