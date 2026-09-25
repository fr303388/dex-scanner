f = r"C:\Users\ANGEL\Doubao\chats\2026-09-12\new-chat\dex_scanner\server.py"
with open(f, "r", encoding="utf-8") as fh:
    c = fh.read()

old = '''@app.route("/")
def index():
    r = send_file("dashboard.html")
    r.headers["Content-Security-Policy"] = "unsafe-inline unsafe-eval * data: blob:"
    return r'''

new = '''@app.route("/")
def index():
    with open("dashboard.html", "r", encoding="utf-8") as f:
        html = f.read()
    return Response(html, mimetype="text/html", headers={
        "Content-Security-Policy": "unsafe-inline unsafe-eval * data: blob:",
        "Access-Control-Allow-Origin": "*"
    })'''

c = c.replace(old, new)

# Add Response import
c = c.replace("from flask import Flask, jsonify, send_file", "from flask import Flask, jsonify, send_file, Response")

with open(f, "w", encoding="utf-8") as fh:
    fh.write(c)
print("done")
