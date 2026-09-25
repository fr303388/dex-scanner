f = r"C:\Users\ANGEL\Doubao\chats\2026-09-12\new-chat\dex_scanner\dashboard.html"
with open(f, "r", encoding="utf-8") as fh:
    c = fh.read()

# Add win rate to HTML
c = c.replace(
    '<span>MEME幣 <b id="stCoins" style="color:#58a6ff">0</b></span>',
    '<span>MEME幣 <b id="stCoins" style="color:#58a6ff">0</b></span>\n    <span>勝率 <b id="stWinRate" style="color:#d29922">0%</b></span>'
)

# Add JS
c = c.replace(
    "document.getElementById('stCoins').textContent = st.unique_bought||0;",
    "document.getElementById('stCoins').textContent = st.unique_bought||0;\n    const wr = (st.wins||0)+(st.losses||0)>0 ? Math.round((st.wins||0)/((st.wins||0)+(st.losses||0))*100) : 0;\n    document.getElementById('stWinRate').textContent = wr+'%';"
)

with open(f, "w", encoding="utf-8") as fh:
    fh.write(c)
print("done")
