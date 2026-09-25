f = r"C:\Users\ANGEL\Doubao\chats\2026-09-12\new-chat\dex_scanner\server.py"
with open(f, "r", encoding="utf-8") as fh:
    c = fh.read()

old = '''@app.route("/api/notify_toggle", methods=["POST"])
def api_notify_toggle():
    global MEME_NOTIFY_ENABLED
    from flask import request
    MEME_NOTIFY_ENABLED = request.json.get("enabled", True)
    return jsonify({"ok": True, "enabled": MEME_NOTIFY_ENABLED})'''

new = '''@app.route("/api/notify_toggle", methods=["POST"])
def api_notify_toggle():
    global MEME_NOTIFY_ENABLED
    from flask import request
    MEME_NOTIFY_ENABLED = request.json.get("enabled", True)
    # 發送確認通知
    try:
        lines_env = Path(__file__).parent / ".env"
        TOKEN = CHAT_ID = ""
        if lines_env.exists():
            for line in lines_env.read_text().splitlines():
                if line.startswith("TELEGRAM_BOT_TOKEN="): TOKEN = line.split("=",1)[1].strip()
                if line.startswith("TELEGRAM_CHAT_ID="): CHAT_ID = line.split("=",1)[1].strip()
        if TOKEN and CHAT_ID:
            msg = "🚀 迷因幣雷達通知已開啟" if MEME_NOTIFY_ENABLED else "🔕 迷因幣雷達通知已關閉"
            requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage",
                data={"chat_id": CHAT_ID, "text": msg}, timeout=10)
    except Exception as e:
        print(f"notify toggle confirm: {e}")
    return jsonify({"ok": True, "enabled": MEME_NOTIFY_ENABLED})'''

c = c.replace(old, new)

with open(f, "w", encoding="utf-8") as fh:
    fh.write(c)
print("done")
