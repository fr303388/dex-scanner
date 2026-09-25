f = r"C:\Users\ANGEL\Doubao\chats\2026-09-12\new-chat\dex_scanner\server.py"
with open(f, "r", encoding="utf-8") as fh:
    c = fh.read()

# Replace the broken auto-buy block with a simple disabled version
old = '''    fresh = [t for t in all_tokens if t["symbol"] not in held_syms and t["score"] >= 4]
    AUTO_TRADE = False
    if AUTO_TRADE:
     for t in fresh:
        if len(kept) >= 10: break'''

new = '''    fresh = [t for t in all_tokens if t["symbol"] not in held_syms and t["score"] >= 4]
    # AUTO_TRADE = False  # disabled until wallet connected
    for t in []:  # disabled
        if len(kept) >= 10: break'''

c = c.replace(old, new)

with open(f, "w", encoding="utf-8") as fh:
    fh.write(c)
print("done")
