p = r"C:\Users\ANGEL\Doubao\chats\2026-09-27\new-chat-10\dex-scanner\server.py"
lines = open(p, encoding="utf-8").readlines()
# Replace lines 278-307 (0-indexed 277-306)
new = '''    if addr in ONCHAIN_CACHE:
        return ONCHAIN_CACHE[addr]
    try:
        r = requests.post("https://api.mainnet-beta.solana.com", json={
            "jsonrpc":"2.0","id":1,"method":"getAccountInfo",
            "params":[addr,{"encoding":"jsonParsed"}]
        }, timeout=8)
        j = r.json()
        if "error" in j:
            return None, "RPC不可用"
        info = j["result"]["value"]["data"]["parsed"]["info"]
        if info.get("mintAuthority"):
            verdict = (False, "mint權限未撤")
        elif info.get("freezeAuthority"):
            verdict = (False, "freeze權限未撤")
        else:
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
            verdict = (False, f"最大持倉{top1*100:.0f}%") if top1 > 0.30 else (True, "")
        ONCHAIN_CACHE[addr] = verdict
        return verdict
    except Exception as e:
        return None, f"RPC:{type(e).__name__}"
'''
out = lines[:277] + [new] + lines[307:]
open(p, "w", encoding="utf-8").write("".join(out))
print("DONE")
