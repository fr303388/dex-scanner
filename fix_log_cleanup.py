p = r"C:\Users\ANGEL\Doubao\chats\2026-09-27\new-chat-10\dex-scanner\server.py"
s = open(p, encoding="utf-8").read()

# Fix field name: txns_24h in header
old = '''            w.writerow(["ts","time","address","symbol","score","price","h1","h24",
                        "volume","liquidity","buy_ratio","txns","decision","reason"])'''
new = '''            w.writerow(["ts","time","address","symbol","score","price","h1","h24",
                        "volume","liquidity","buy_ratio","txns_24h","decision","reason"])'''
s = s.replace(old, new)

# Only log tokens that pass liquidity filter (not all 25)
old2 = '''        for t in tokens:
            addr = t["address"]
            decision = "HELD" if addr in held else ("ENTERED" if addr in entered else "REJECTED")
            if addr in sim.get("cooldown", {}): decision = "COOLDOWN"'''
new2 = '''        for t in tokens:
            addr = t["address"]
            if t.get("liquidity", 0) < 35000: continue  # 只記有資格的
            decision = "HELD" if addr in held else ("ENTERED" if addr in entered else "REJECTED")
            if addr in sim.get("cooldown", {}): decision = "COOLDOWN"'''
s = s.replace(old2, new2)

open(p, "w", encoding="utf-8").write(s)
print("DONE")
