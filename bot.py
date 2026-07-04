import json
import os
import asyncio
from telethon import TelegramClient, events
from telethon.tl.functions.stories import GetStoriesByIDRequest

# 1. تحميل الإعدادات
with open("config.json", "r") as f:
    config = json.load(f)

API_ID = int(config["api_id"])
API_HASH = config["api_hash"]
BOT_TOKEN = config["bot_token"]

# 2. إعداد جلسات العمل (البوت والمساعد)
bot = TelegramClient('bot_session', API_ID, API_HASH)
user = TelegramClient('user_session', API_ID, API_HASH)

async def main():
    # تشغيل حساب المساعد (سيطلب رقمك والكود بالترمينال أول مرة فقط)
    print("🔄 جاري ربط حساب المساعد الفاحص (User)...")
    await user.start()
    
    # تشغيل البوت الرسمي
    print("🔄 جاري تشغيل البوت الموزع (Bot)...")
    await bot.start(bot_token=BOT_TOKEN)
    
    print("🚀 البوت شغال الآن بنجاح وجاهز لتحميل الستوريات!")

    @bot.on(events.NewMessage(pattern='/start'))
    async def start(event):
        await event.reply("👋 أهلاً بك! أرسل لي رابط ستوري تليجرام عام (مثال: https://t.me/username/s/1) وراح أحمله وأرسله إلك فوراً.")

    @bot.on(events.NewMessage)
    async def handle_message(event):
        if event.text.startswith('/start'):
            return
        
        url = event.text.strip()
        # التأكد أن الرابط المرسل هو رابط ستوري
        if "t.me/" in url and "/s/" in url:
            await event.reply("⏳ جاري جلب الستوري، انتظر ثواني...")
            try:
                # تحليل الرابط لاستخراج اسم المستخدم وايدي الستوري
                parts = url.split('/')
                username = parts[-3]
                story_id = int(parts[-1])
                
                # جلب معلومات الحساب والستوري عبر حساب المساعد
                peer = await user.get_input_entity(username)
                result = await user(GetStoriesByIDRequest(peer=peer, id=[story_id]))
                
                if result.stories:
                    story = result.stories[0]
                    await event.reply("📥 جاري تحميل الميديا وإرسالها...")
                    
                    # تحميل الملف للسيرفر مؤقتاً
                    media_path = await user.download_media(story.media)
                    
                    # إرسال الملف للمستخدم عن طريق البوت
                    await bot.send_file(event.chat_id, media_path, caption="✅ تم تحميل الستوري بنجاح بواسطة البوت!")
                    
                    # حذف الملف المؤقت للحفاظ على مساحة السيرفر
                    if os.path.exists(media_path):
                        os.remove(media_path)
                else:
                    await event.reply("❌ الستوري غير موجود، أو قد يكون الحساب خاصاً لا يمكن للمساعد رؤيته.")
            except Exception as e:
                await event.reply(f"❌ حدث خطأ أثناء المعالجة: {str(e)}")

    await bot.run_until_disconnected()

if __name__ == '__main__':
    import asyncio
    asyncio.run(main())
