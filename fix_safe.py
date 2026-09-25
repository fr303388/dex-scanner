f = r"C:\Users\ANGEL\Doubao\chats\2026-09-12\new-chat\dex_scanner\dashboard.html"
with open(f, "r", encoding="utf-8") as fh:
    c = fh.read()

# Add safe defaults at start of load() after const pf = d.portfolio
c = c.replace(
    "const pf = d.portfolio;",
    "const pf = d.portfolio || {};\n    pf.total_invested = pf.total_invested || 0;\n    pf.total_value = pf.total_value || 0;\n    pf.total_pnl = pf.total_pnl || 0;\n    pf.total_pnl_pct = pf.total_pnl_pct || 0;\n    pf.total_equity = pf.total_equity || 0;\n    pf.all_time_pnl = pf.all_time_pnl || 0;\n    pf.all_time_pnl_pct = pf.all_time_pnl_pct || 0;\n    pf.positions = pf.positions || [];\n    pf.trades = pf.trades || [];"
)

# Also add fallback for p.buy_price and p.pnl in positions
c = c.replace(
    "p.buy_price.toFixed(8)",
    "(p.buy_price||0).toFixed(8)"
)
c = c.replace(
    "p.pnl.toFixed(2)",
    "(p.pnl||0).toFixed(2)"
)

with open(f, "w", encoding="utf-8") as fh:
    fh.write(c)
print("done")
