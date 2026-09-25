f = r"C:\Users\ANGEL\Doubao\chats\2026-09-12\new-chat\dex_scanner\dashboard.html"
with open(f, "r", encoding="utf-8") as fh:
    c = fh.read()

c = c.replace(
    '<span>被rug(-99%) <b id="stRugs" style="color:#f85149">0</b></span>',
    '<span>被rug(-99%) <b id="stRugs" style="color:#f85149">0</b></span>\n    <span>MEME幣 <b id="stCoins" style="color:#58a6ff">0</b></span>'
)

c = c.replace(
    "document.getElementById('stRugs').textContent = st.rugs||0;",
    "document.getElementById('stRugs').textContent = st.rugs||0;\n    document.getElementById('stCoins').textContent = st.unique_bought||0;"
)

with open(f, "w", encoding="utf-8") as fh:
    fh.write(c)
print("done")
