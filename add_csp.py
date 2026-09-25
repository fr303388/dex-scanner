f = r"C:\Users\ANGEL\Doubao\chats\2026-09-12\new-chat\dex_scanner\server.py"
with open(f, "r", encoding="utf-8") as fh:
    c = fh.read()

old = '@app.route("/api/dex")'
new = '''@app.after_request
def add_header(r):
    r.headers["Content-Security-Policy"] = "default-src 'self' 'unsafe-inline' 'unsafe-eval' data: blob: https:; img-src 'self' data: https:; script-src 'self' 'unsafe-inline' 'unsafe-eval'; style-src 'self' 'unsafe-inline'"
    return r

@app.route("/api/dex")'''

c = c.replace(old, new, 1)
with open(f, "w", encoding="utf-8") as fh:
    fh.write(c)
print("done")
