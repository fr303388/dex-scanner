f = r"C:\Users\ANGEL\Doubao\chats\2026-09-12\new-chat\dex_scanner\dashboard.html"
with open(f, "r", encoding="utf-8") as fh:
    c = fh.read()

# Remove Solflare and MetaMask buttons
c = c.replace('  <button onclick="connectSolflare()" style="background:#21262d;border:1px solid #30363d;color:#e6edf3;padding:6px 14px;border-radius:6px;cursor:pointer;font-size:12px">☀️ Solflare</button>\n', '')
c = c.replace('  <button onclick="connectMetaMask()" style="background:#21262d;border:1px solid #30363d;color:#e6edf3;padding:6px 14px;border-radius:6px;cursor:pointer;font-size:12px">🦊 MetaMask</button>\n', '')

with open(f, "w", encoding="utf-8") as fh:
    fh.write(c)

# Also remove from app.js
f2 = r"C:\Users\ANGEL\Doubao\chats\2026-09-12\new-chat\dex_scanner\app.js"
with open(f2, "r", encoding="utf-8") as fh:
    c2 = fh.read()

# Remove connectSolflare and connectMetaMask functions
import re
c2 = re.sub(r'async function connectSolflare\(\).*?\n\}\n', '', c2, flags=re.DOTALL)
c2 = re.sub(r'async function connectMetaMask\(\).*?\n\}\n', '', c2, flags=re.DOTALL)

with open(f2, "w", encoding="utf-8") as fh:
    fh.write(c2)
print("done")
