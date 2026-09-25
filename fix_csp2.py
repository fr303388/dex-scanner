f = r"C:\Users\ANGEL\Doubao\chats\2026-09-12\new-chat\dex_scanner\server.py"
with open(f, "r", encoding="utf-8") as fh:
    c = fh.read()

# Replace index route to add CSP header directly
c = c.replace(
    'def index(): return send_file("dashboard.html")',
    'def index():\n    r = send_file("dashboard.html")\n    r.headers["Content-Security-Policy"] = "unsafe-inline unsafe-eval * data: blob:"\n    return r'
)

with open(f, "w", encoding="utf-8") as fh:
    fh.write(c)
print("done")
