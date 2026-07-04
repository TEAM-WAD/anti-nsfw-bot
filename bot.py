import json
import os
import asyncio
from telethon import TelegramClient, events
from telethon.errors import SessionPasswordNeededError
from telethon.tl.functions.stories import GetStoriesByIDRequest

# 1. تحميل الإعدادات
with open("config.json", "r") as f:
    config = json.load(f)

API_ID = int(config["api_id"])
API_HASH = config["api_hash"]
BOT_TOKEN = config["bot_token"]
PHONE = config["phone"]

# 2. إعداد جلسات العمل
bot = TelegramClient('bot_session', API_ID, API_HASH)
user = TelegramClient('user_session', API_ID, API_HASH)

async def main():
    # الاتصال بسيرفرات تليجرام
    await user.connect()
    
    print("🔄 جاري التحقق من جلسة المساعد...", flush=True)
    
    # تسجيل دخول يدوي ومضمون للآيفون لتجنب تجميد الشاشة
    if not await user.is_user_authorized():
        print("📥 جاري إرسال كود التحقق إلى حسابك على التليجرام...", flush=True)
        try:
            send_code = await user.send_code_request(PHONE)
            auth_hash = send_code.phone_code_hash
            
            # إجبار الترمينال على إظهار الطلب فوراً
            print("\n🔑 افتح تطبيق التليجرام واكتب الكود الذي وصلك هنا فوراً ثم اضغط Enter:", flush=True)
            code = input().strip()
            
            try:
                await user.sign_in(PHONE, code, phone_code_hash=auth_hash)
            except SessionPasswordNeededError:
                print("\n🔒 حسابك محمي بالتحقق بخطوتين، اكتب رمز الأمان (Password) مالتك هنا ثم اضغط Enter:", flush=True)
                password = input().strip()
                await user.sign_in(password=password)
        except Exception as e:
            print(f"❌ خطأ أثناء إرسال الكود: {e}", flush=True)
            return

    print("✅ تم ربط حساب المساعد بنجاح!", flush=True)
    
    print("🔄 جاري تشغيل البوت الموزع (Bot)...", flush=True)
    await bot.start(bot_token=BOT_TOKEN)
    
    print("🚀 بوت تحميل الستوريات شغال الآن بنجاح وبدون أي تعليق!", flush=True)

    @bot.on(events.NewMessage(pattern='/start'))
    async def start(event):
        await event.reply("👋 أهلاً بك! أرسل لي رابط ستوري تليجرام عام (مثال: https://t.me/username/s/1) وراح أحمله وأرسله إلك فوراً.")

    @bot.on(events.NewMessage)
    async def handle_message(event):
        if event.text.startswith('/start'):
            return
        
        url = event.text.strip()
        if "t.me/" in url and "/s/" in url:
            await event.reply("⏳ جاري جلب الستوري، انتظر ثواني...")
            try:
                parts = url.split('/')
                username = parts[-3]
                story_id = int(parts[-1])
                
                peer = await user.get_input_entity(username)
                result = await user(GetStoriesByIDRequest(peer=peer, id=[story_id]))
                
                if result.stories:
                    story = result.stories[0]
                    await event.reply("📥 جاري تحميل الميديا وإرسالها...")
                    
                    media_path = await user.download_media(story.media)
                    await bot.send_file(event.chat_id, media_path, caption="✅ تم تحميل الستوري بنجاح!")
                    
                    if os.path.exists(media_path):
                        os.remove(media_path)
                else:
                    await event.reply("❌ الستوري غير موجود أو الحساب خاص.")
            except Exception as e:
                await event.reply(f"❌ حدث خطأ أثناء المعالجة: {str(e)}")

    await bot.run_until_disconnected()

if __name__ == '__main__':
    import asyncio
    asyncio.run(main())
