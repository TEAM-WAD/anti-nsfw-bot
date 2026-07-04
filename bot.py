import telebot
from telebot import types
import json
import os
from datetime import datetime
from nsfw_detector import predict

# تحميل الإعدادات من ملف Config الشفاف
with open('config.json', 'r', encoding='utf-8') as f:
    config = json.load(f)

TOKEN = config["TOKEN"]
DEVELOPER_ID = int(config["DEVELOPER_ID"])
DEVELOPER_CHANNEL = config["DEVELOPER_CHANNEL"]

bot = telebot.TeleBot(TOKEN)

# تحميل نموذج الذكاء الاصطناعي محلياً
print("⏳ جاري تحميل نموذج الذكاء الاصطناعي للفحص...")
model = predict.load_model('./nsfw_mobilenet2.h5')
print("✅ تم تحميل النموذج بنجاح البوت جاهز للعمل!")

# إنشاء ملفات حفظ البيانات تلقائياً
def init_file(filename, default_value):
    if not os.path.exists(filename):
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(default_value, f, ensure_ascii=False, indent=4)

init_file('users.json', [])
init_file('groups.json', [])
init_file('violators.json', {})
init_file('settings.json', {"force_channel": "", "force_title": "", "admin_step": ""})

def load_data(filename):
    with open(filename, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_data(filename, data):
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

# دالة فحص المحتوى الإباحي بالذكاء الاصطناعي المحلي
def check_nsfw_local(message):
    file_id = None
    if message.photo:
        file_id = message.photo[-1].file_id
    elif message.sticker:
        file_id = message.sticker.file_id
    elif message.video:
        file_id = message.video.file_id
    elif message.document and message.document.mime_type.startswith('video/'):
        file_id = message.document.file_id

    if not file_id:
        return False

    try:
        # تحميل الملف مؤقتاً لفحصه
        file_info = bot.get_file(file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        
        temp_path = f"temp_{file_id}.jpg"
        with open(temp_path, 'wb') as new_file:
            new_file.write(downloaded_file)
        
        # الفحص بواسطة الذكاء الاصطناعي
        results = predict.classify(model, temp_path)
        os.remove(temp_path) # حذف الملف المؤقت فوراً
        
        if temp_path in results:
            predictions = results[temp_path]
            # الحسابات: إذا كانت نسبة الخلاعة (hentai, pornography, sexy) أعلى من 55%
            nsfw_score = predictions.get('porn', 0) + predictions.get('sexy', 0) + predictions.get('hentai', 0)
            if nsfw_score > 0.55:
                return True
    except Exception as e:
        print(f"Error in AI scanning: {e}")
    return False

def is_subscribed(user_id):
    settings = load_data('settings.json')
    channel = settings.get("force_channel")
    if not channel:
        return True
    try:
        member = bot.get_chat_member(channel, user_id)
        if member.status in ['creator', 'administrator', 'member']:
            return True
    except Exception:
        pass
    return False

# الجروبات - التفعيل التلقائي
@bot.message_handler(content_types=['new_chat_members'])
def on_bot_join(message):
    for member in message.new_chat_members:
        if member.id == bot.get_me().id:
            groups = load_data('groups.json')
            if message.chat.id not in groups:
                groups.append(message.chat.id)
                save_data('groups.json', groups)
            
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("📢 قناة المطور", url=DEVELOPER_CHANNEL))
            bot.send_message(message.chat.id, "⚙️ **تم تفعيلي تلقائياً في المجموعة وبدأت بحمايتها عبر الذكاء الاصطناعي!**", reply_markup=markup, parse_mode="Markdown")

# فحص كلمات (بوت / ايدي) والاشتراك الإجباري
@bot.message_handler(func=lambda msg: msg.chat.type in ['group', 'supergroup'] and msg.text in ['بوت', 'ايدي'])
def check_keywords(message):
    if not is_subscribed(message.from_user.id):
        settings = load_data('settings.json')
        ch_url = settings["force_channel"].replace('@', 'https://t.me/')
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton(settings["force_title"], url=ch_url))
        bot.reply_to(message, "🚨 **عذراً عزيزي، لا يمكنك استخدام البوت داخل المجموعة إلا بعد الاشتراك في قناة البوت أولاً!**", reply_markup=markup, parse_mode="Markdown")
        return
    
    if message.text == 'ايدي':
        bot.reply_to(message, f"🆔 أيديك هو: `{message.from_user.id}`", parse_mode="Markdown")
    elif message.text == 'بوت':
        bot.reply_to(message, "🤖 نعم عزيزي، أنا هنا لحماية المجموعة بالذكاء الاصطناعي!")

# فحص وحذف المحتوى والتقييد
@bot.message_handler(content_types=['photo', 'video', 'sticker', 'document'])
def filter_nsfw_content(message):
    if message.chat.type not in ['group', 'supergroup']:
        return

    if check_nsfw_local(message):
        user_id = message.from_user.id
        user_name = message.from_user.first_name
        user_mention = f"[{user_name}](tg://user?id={user_id})"
        chat_id = message.chat.id
        media_type = "ملصق" if message.sticker else "صورة" if message.photo else "فيديو" if message.video else "متحركة GIF"
        
        is_admin = False
        try:
            member = bot.get_chat_member(chat_id, user_id)
            if member.status in ['creator', 'administrator']:
                is_admin = True
        except Exception:
            pass
        
        try: bot.delete_message(chat_id, message.message_id)
        except Exception: pass

        try:
            admins = bot.get_chat_administrators(chat_id)
            admin_mentions = " ".join([f"[👑](tg://user?id={adm.user.id})" for adm in admins if not adm.user.is_bot])
        except Exception:
            admin_mentions = "@admins"

        now = datetime.now().strftime("%Y-%m-%d %H:%M")

        if is_admin:
            alert_msg = f"⚠️ {admin_mentions}\n**انتباه!** المشرف {user_mention} أرسل ({media_type}) اباحي وتم حذفه.\n🚨 **ملاحظة:** لا يمكنني تقييده لأنه مشرف!"
            bot.send_message(chat_id, alert_msg, parse_mode="Markdown")
            log_to_dev(user_name, user_id, now, media_type, chat_id, success=False, reason="مشرف")
        else:
            try:
                bot.restrict_chat_member(chat_id, user_id, until_date=0, can_send_messages=False, can_send_media_messages=False)
                status_text = "تم تقييد المستخدم من إرسال الميديا والكتابة."
                success_log = True
            except Exception:
                status_text = "تعذر تقييده لنقص الصلاحيات."
                success_log = False
                
            alert_msg = f"⚠️ {admin_mentions}\n**تنبيه ذكاء اصطناعي!** تم كشف وحذف محتوى إباحي.\n👤 **المستخدم:** {user_mention}\n🚫 **المحتوى:** {media_type} اباحي.\n🛠️ **الإجراء:** تم حذف الميديا و {status_text}"
            bot.send_message(chat_id, alert_msg, parse_mode="Markdown")
            
            violators = load_data('violators.json')
            violators[str(user_id)] = {"name": user_name, "time": now, "type": media_type}
            save_data('violators.json', violators)
            
            log_to_dev(user_name, user_id, now, media_type, chat_id, success=success_log, reason="مستخدم عادي")

def log_to_dev(name, uid, time, m_type, group_id, success, reason):
    try:
        chat_info = bot.get_chat(group_id)
        group_link = chat_info.invite_link if chat_info.invite_link else f"https://t.me/c/{str(group_id).replace('-100', '')}"
    except Exception:
        group_link = "https://t.me"

    status_str = "قيدته بنجاح" if success else f"ماكدرت اقيده لان ({reason})"
    log_text = f"🚨 **إشعار تم كشف محتوى إباحي:**\n\n👤 **المخرب:** {name} (`{uid}`)\n📅 **الوقت:** {time}\n📦 **السبب:** دز {m_type} اباحي\n🛠️ **الحالة:** {status_str}"
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔗 رابط المجموعة", url=group_link))
    bot.send_message(DEVELOPER_ID, log_text, reply_markup=markup, parse_mode="Markdown")

# لوحة التحكم بالخاص
@bot.message_handler(commands=['start'])
def on_start_private(message):
    if message.chat.type != 'private': return
    users = load_data('users.json')
    if message.chat.id not in users:
        users.append(message.chat.id)
        save_data('users.json', users)
    bot.reply_to(message, "👋 أهلاً بك في بوت الحماية الشاملة للمجموعات بالذكاء الاصطناعي المحلي.")

@bot.message_handler(commands=['admin'])
def admin_panel(message):
    if message.chat.id != DEVELOPER_ID: return
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("📊 الإحصائيات", callback_data="admin_stats"),
        types.InlineKeyboardButton("🔍 كشف المخربين", callback_data="admin_violators"),
        types.InlineKeyboardButton("📢 إذاعة خاص", callback_data="bc_users"),
        types.InlineKeyboardButton("📢 إذاعة جروبات", callback_data="bc_groups"),
        types.InlineKeyboardButton("➕ تفعيل إشتراك إجباري", callback_data="add_force"),
        types.InlineKeyboardButton("🗑️ حذف الاشتراك الإجباري", callback_data="del_force")
    )
    bot.send_message(DEVELOPER_ID, "🛠️ **مرحباً بك يا مطور في لوحة التحكم الإدارية:**", reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: True)
def handle_admin_callbacks(call):
    if call.message.chat.id != DEVELOPER_ID: return
    settings = load_data('settings.json')
    
    if call.data == "admin_stats":
        users_count = len(load_data('users.json'))
        groups_count = len(load_data('groups.json'))
        bot.answer_callback_query(call.id)
        bot.send_message(DEVELOPER_ID, f"📊 **إحصائيات البوت الحالية:**\n\n👤 عدد مستخدمي الخاص: `{users_count}`\n👥 عدد المجموعات المفعلة: `{groups_count}`", parse_mode="Markdown")
        
    elif call.data == "admin_violators":
        violators = load_data('violators.json')
        bot.answer_callback_query(call.id)
        if not violators:
            bot.send_message(DEVELOPER_ID, "✅ لا يوجد أي مخربين مخزنين حالياً.")
        else:
            txt = "🔍 **قائمة المخربين الذين تم كشفهم:**\n\n"
            for k, v in violators.items():
                txt += f"• أيدي: `{k}` | الاسم: {v['name']} | ميديا: {v['type']} | بوقت: {v['time']}\n"
            bot.send_message(DEVELOPER_ID, txt, parse_mode="Markdown")
            
    elif call.data == "add_force":
        bot.answer_callback_query(call.id)
        settings["admin_step"] = "wait_channel"
        save_data('settings.json', settings)
        bot.send_message(DEVELOPER_ID, "📢 أرسل الآن معرف القناة مع الـ @ (مثال: @Google):")
        
    elif call.data == "del_force":
        bot.answer_callback_query(call.id)
        settings["force_channel"] = ""
        settings["force_title"] = ""
        settings["admin_step"] = ""
        save_data('settings.json', settings)
        bot.send_message(DEVELOPER_ID, "🗑️ تم حذف وتعطيل الاشتراك الإجباري بنجاح.")
        
    elif call.data == "bc_users":
        bot.answer_callback_query(call.id)
        settings["admin_step"] = "wait_bc_users"
        save_data('settings.json', settings)
        bot.send_message(DEVELOPER_ID, "📢 أرسل نص الرسالة التي تريد إذاعتها لمستخدمين الخاص:")
        
    elif call.data == "bc_groups":
        bot.answer_callback_query(call.id)
        settings["admin_step"] = "wait_bc_groups"
        save_data('settings.json', settings)
        bot.send_message(DEVELOPER_ID, "📢 أرسل نص الرسالة التي تريد إذاعتها لكل المجموعات:")

@bot.message_handler(func=lambda msg: msg.chat.type == 'private' and msg.chat.id == DEVELOPER_ID)
def handle_admin_inputs(message):
    settings = load_data('settings.json')
    step = settings.get("admin_step", "")
    
    if step == "wait_channel":
        if not message.text.startswith("@"):
            bot.reply_to(message, "⚠️ يجب أن يبدأ المعرف بـ @")
            return
        try:
            chat = bot.get_chat(message.text)
            settings["force_channel"] = message.text
            settings["force_title"] = chat.title if chat.title else message.text
            settings["admin_step"] = ""
            save_data('settings.json', settings)
            bot.reply_to(message, f"✅ تم تفعيل الاشتراك الإجباري لقناة: **{settings['force_title']}**", parse_mode="Markdown")
        except Exception as e:
            bot.reply_to(message, f"❌ حدث خطأ، تأكد أن البوت مشرف في القناة أولاً.\nالخطأ: {e}")
            
    elif step == "wait_bc_users":
        settings["admin_step"] = ""
        save_data('settings.json', settings)
        users = load_data('users.json')
        bot.reply_to(message, "⏳ يتم البدء بالإذاعة للخاص...")
        success = 0
        for u in users:
            try: bot.send_message(u, message.text); success += 1
            except Exception: pass
        bot.send_message(DEVELOPER_ID, f"📢 تمت الإذاعة بنجاح لـ {success} مستخدم من أصل {len(users)}")
        
    elif step == "wait_bc_groups":
        settings["admin_step"] = ""
        save_data('settings.json', settings)
        groups = load_data('groups.json')
        bot.reply_to(message, "⏳ يتم البدء بالإذاعة للجروبات...")
        success = 0
        for g in groups:
            try: bot.send_message(g, message.text); success += 1
            except Exception: pass
        bot.send_message(DEVELOPER_ID, f"📢 تمت الإذاعة بنجاح لـ {success} جروب من أصل {len(groups)}")

bot.infinity_polling()
