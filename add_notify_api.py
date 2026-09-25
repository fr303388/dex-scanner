f = r"C:\Users\ANGEL\Doubao\chats\2026-09-12\new-chat\dex_scanner\server.py"
with open(f, "r", encoding="utf-8") as fh:
    c = fh.read()

# Add global flag after imports
c = c.replace(
    'app = Flask(__name__)',
    'app = Flask(__name__)\nMEME_NOTIFY_ENABLED = True'
)

# Add endpoint before the last route
c = c.replace(
    '@app.route("/")',
    '''@app.route("/api/notify_toggle", methods=["POST"])
def api_notify_toggle():
    global MEME_NOTIFY_ENABLED
    from flask import request
    MEME_NOTIFY_ENABLED = request.json.get("enabled", True)
    return jsonify({"ok": True, "enabled": MEME_NOTIFY_ENABLED})

@app.route("/")'''
)

# Add check before sending telegram
c = c.replace(
    '                requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage",',
    '                if MEME_NOTIFY_ENABLED:\n                  requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage",'
)

with open(f, "w", encoding="utf-8") as fh:
    fh.write(c)
print("done")
