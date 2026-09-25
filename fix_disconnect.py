f = r"C:\Users\ANGEL\Doubao\chats\2026-09-12\new-chat\dex_scanner\app.js"
with open(f, "r", encoding="utf-8") as fh:
    c = fh.read()

# Track explicit disconnect
c = c.replace(
    "async function disconnectWallet() {",
    "async function disconnectWallet() {\n  sessionStorage.setItem('wallet_disconnected','1');"
)

# Only auto-reconnect if not explicitly disconnected
c = c.replace(
    "// 自動重連 Phantom\n(async function autoReconnect() {\n  try {\n    if (window.solana && window.solana.isPhantom) {",
    "// 自動重連 Phantom（除非使用者手動斷開）\n(async function autoReconnect() {\n  try {\n    if (sessionStorage.getItem('wallet_disconnected') === '1') return;\n    if (window.solana && window.solana.isPhantom) {"
)

with open(f, "w", encoding="utf-8") as fh:
    fh.write(c)
print("done")
