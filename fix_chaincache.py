p = r"C:\Users\ANGEL\Doubao\chats\2026-09-27\new-chat-10\dex-scanner\server.py"
s = open(p, encoding="utf-8").read()

# Add ONCHAIN_CACHE after TRIGGER_TRACK
old = 'TRIGGER_TRACK = {}'
new = '''TRIGGER_TRACK = {}
ONCHAIN_CACHE = {}  # addr -> (ok, reason)'''
s = s.replace(old, new)

# Cache in check_onchain_risk
old2 = '''def check_onchain_risk(addr):
    """檢查 mint authority、freeze authority、持倉集中度。回傳 (ok, reason)"""
    try:'''
new2 = '''def check_onchain_risk(addr):
    """檢查 mint/freeze 權限 + 集中度。結果快取（不可變）"""
    if addr in ONCHAIN_CACHE:
        return ONCHAIN_CACHE[addr]
    result = (None, "")
    try:'''
s = s.replace(old2, new2)

# Cache the return values
old3 = '''        return True, ""
    except Exception as e:
        return False, f"鏈上檢查失敗:{type(e).__name__}"'''
new3 = '''        result = (True, "")
    except Exception as e:
        result = (None, f"RPC:{type(e).__name__}")
    ONCHAIN_CACHE[addr] = result
    return result'''
s = s.replace(old3, new3)

# Update caller to handle None
old4 = '''        # 鏈上風險檢查
        ok, risk_reason = check_onchain_risk(addr)
        if not ok:
            rejected.append((t, risk_reason)); continue'''
new4 = '''        # 鏈上風險檢查
        verdict, risk_reason = check_onchain_risk(addr)
        if verdict is None:
            rejected.append((t, "鏈上資料不可用")); continue
        if not verdict:
            rejected.append((t, risk_reason)); continue'''
s = s.replace(old4, new4)

open(p, "w", encoding="utf-8").write(s)
print("DONE")
