f = r"C:\Users\ANGEL\Doubao\chats\2026-09-12\new-chat\dex_scanner\dashboard.html"
with open(f, "r", encoding="utf-8") as fh:
    c = fh.read()

# Fix line 111: total_pnl_pct
c = c.replace(
    "pf.total_pnl_pct + '%)'",
    "(pf.total_pnl_pct||0) + '%)'"
)

# Fix line 127: p.pnl_pct
c = c.replace(
    "${p.pnl_pct>=0?'+':''}${p.pnl_pct}%",
    "${(p.pnl_pct||0)>=0?'+':''}${(p.pnl_pct||0)}%"
)

with open(f, "w", encoding="utf-8") as fh:
    fh.write(c)
print("done")
