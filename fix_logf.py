p = r"C:\Users\ANGEL\Doubao\chats\2026-09-27\new-chat-10\dex-scanner\server.py"
s = open(p, encoding="utf-8").read()
old = '''        for t in tokens:
            addr = t["address"]
            if addr in entered:'''
new = '''        for t in tokens:
            addr = t["address"]
            if t.get("liquidity", 0) < 35000: continue
            if addr in entered:'''
s = s.replace(old, new)
open(p, "w", encoding="utf-8").write(s)
print("DONE")
