p = r"C:\Users\ANGEL\Doubao\chats\2026-09-27\new-chat-10\dex-scanner\server.py"
s = open(p, encoding="utf-8").read()

# 1. MFE/peak initial values
s = s.replace(
  'pos["mfe"] = max(pos.get("mfe", 0), pos["pnl_pct"])',
  'pos["mfe"] = max(pos.get("mfe", pos["pnl_pct"]), pos["pnl_pct"])'
)
s = s.replace(
  '"peak_pct": 0,',
  '"peak_pct": 0,  # set on first update'
)

# 2. fail-closed onchain
s = s.replace(
  'return True, ""  # 查不到就放行，不要亂擋',
  'return False, "鏈上檢查失敗"'
)

# 3. decimals fail-closed
s = s.replace(
  'print(f"[DEC] fail {mint[:8]}: {e}", flush=True)\n        return 6',
  'print(f"[DEC] fail {mint[:8]}: {e}", flush=True)\n        return None'
)

# 4. Trigger dedup: remove append from check_trigger
old = '''    hist = TRIGGER_TRACK.get(addr, [])
    if len(hist) < 8:  # 至少收集 2 分鐘
        return False, "收集走勢中"'''
new = '''    hist = TRIGGER_TRACK.get(addr, [])
    if len(hist) < 8:
        return False, f"收集{len(hist)}點"'''
s = s.replace(old, new)

# 5. log filter - find the actual loop
old2 = '''        for t in tokens:
            addr = t["address"]
            decision = "HELD"'''
new2 = '''        for t in tokens:
            addr = t["address"]
            if t.get("liquidity", 0) < 35000: continue
            decision = "HELD"'''
s = s.replace(old2, new2)

open(p, "w", encoding="utf-8").write(s)
print("DONE")
