f = r"C:\Users\ANGEL\Doubao\chats\2026-09-12\new-chat\dex_scanner\server.py"
with open(f, "r", encoding="utf-8") as fh:
    c = fh.read()

# Add -99 tracking (rug = price crashed to near 0)
old = '''            if "停損" in sell_reason:
                pf["stats"]["rugs"] += 1
                pf["stats"]["losses"] += 1
                pf["stats"]["loss_amount"] += pos["pnl"]'''

new = '''            if "停損" in sell_reason:
                pf["stats"]["rugs"] += 1
                pf["stats"]["losses"] += 1
                pf["stats"]["loss_amount"] += pos["pnl"]
                if pos["pnl_pct"] <= -90:
                    pf["stats"]["deep_rugs"] = pf["stats"].get("deep_rugs", 0) + 1'''

c = c.replace(old, new)

with open(f, "w", encoding="utf-8") as fh:
    fh.write(c)
print("server done")

# Update UI
f2 = r"C:\Users\ANGEL\Doubao\chats\2026-09-12\new-chat\dex_scanner\dashboard.html"
with open(f2, "r", encoding="utf-8") as fh:
    d = fh.read()

d = d.replace(
    '<span>被rug <b id="stRugs" style="color:#f85149">0</b></span>',
    '<span>被rug <b id="stRugs" style="color:#f85149">0</b></span>\n    <span>-99% <b id="stDeepRugs" style="color:#f85149">0</b></span>'
)

d = d.replace(
    'document.getElementById(\'stRugs\').textContent = st.rugs||0;',
    'document.getElementById(\'stRugs\').textContent = st.rugs||0;\n    document.getElementById(\'stDeepRugs\').textContent = st.deep_rugs||0;'
)

with open(f2, "w", encoding="utf-8") as fh:
    fh.write(d)
print("ui done")
