f = r"C:\Users\ANGEL\Doubao\chats\2026-09-12\new-chat\dex_scanner\server.py"
with open(f, "r", encoding="utf-8") as fh:
    c = fh.read()
c = c.replace("TAKE_PROFIT_PCT = 30.0", "TAKE_PROFIT_PCT = 20.0")
with open(f, "w", encoding="utf-8") as fh:
    fh.write(c)
print("done")
