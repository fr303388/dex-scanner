f = r"C:\Users\ANGEL\Doubao\chats\2026-09-12\new-chat\dex_scanner\server.py"
with open(f, "r", encoding="utf-8") as fh:
    c = fh.read()

c = c.replace(
    "    fresh = [t for t in all_tokens if t[\"symbol\"] not in held_syms and t[\"score\"] >= 4]\n    for t in fresh:",
    "    fresh = [t for t in all_tokens if t[\"symbol\"] not in held_syms and t[\"score\"] >= 4]\n    AUTO_TRADE = False\n    if AUTO_TRADE:\n     for t in fresh:"
)

with open(f, "w", encoding="utf-8") as fh:
    fh.write(c)
print("done")
