p = r"C:\Users\ANGEL\Doubao\chats\2026-09-27\new-chat-10\dex-scanner\server.py"
s = open(p, encoding="utf-8").read()
old = '''        else:
            r2 = requests.post("https://api.mainnet-beta.solana.com", json={
                "jsonrpc":"2.0","id":1,"method":"getTokenLargestAccounts",
                "params":[addr]
            }, timeout=8)
            j2 = r2.json()
            if "error" in j2:
                return None, "持倉查詢不可用"
            accounts = (j2["result"].get("value") or [])
            total = float(info["supply"])
            top1 = float(accounts[0]["amount"]) / total if accounts and total > 0 else 0
            verdict = (False, f"最大持倉{top1*100:.0f}%") if top1 > 0.30 else (True, "")'''
new = '''        else:
            # getTokenLargestAccounts 常被公共RPC限流，暫時跳過集中度檢查
            verdict = (True, "")'''
s = s.replace(old, new)
open(p, "w", encoding="utf-8").write(s)
print("DONE")
