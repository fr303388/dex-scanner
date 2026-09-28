p = r"C:\Users\ANGEL\Doubao\chats\2026-09-27\new-chat-10\dex-scanner\server.py"
s = open(p, encoding="utf-8").read()

# 1. Use stored decimals for sell value
old = '''        dec = get_token_decimals(addr)
        if dec is None:
            dec = pos.get("decimals", 6)
        sq = get_sell_value_usd(addr, pos["tokens"], dec)'''
new = '''        sq = get_sell_value_usd(addr, pos["tokens"], pos.get("decimals", 6))'''
s = s.replace(old, new)

# 2. fail-closed onchain - all return False
s = s.replace('return True, ""  # accounts 為 null', 'return False, "持倉集中度資料缺失"')
s = s.replace('return True, ""  # 查不到就放行', 'return False, "鏈上檢查失敗"')

open(p, "w", encoding="utf-8").write(s)
print("DONE")
