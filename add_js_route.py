f = r"C:\Users\ANGEL\Doubao\chats\2026-09-12\new-chat\dex_scanner\server.py"
with open(f, "r", encoding="utf-8") as fh:
    c = fh.read()

# Add route for app.js
if '/app.js' not in c:
    c = c.replace(
        '@app.route("/alert.mp3")',
        '''@app.route("/app.js")
def app_js(): return send_file("app.js", mimetype="application/javascript")
@app.route("/alert.mp3")'''
    )

with open(f, "w", encoding="utf-8") as fh:
    fh.write(c)
print("done")
