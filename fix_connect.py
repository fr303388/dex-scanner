f = r"C:\Users\ANGEL\Doubao\chats\2026-09-12\new-chat\dex_scanner\app.js"
with open(f, "r", encoding="utf-8") as fh:
    c = fh.read()

# Clear disconnect flag on manual connect
c = c.replace(
    "async function connectPhantom() {",
    "async function connectPhantom() {\n  sessionStorage.removeItem('wallet_disconnected');"
)

with open(f, "w", encoding="utf-8") as fh:
    fh.write(c)
print("done")
