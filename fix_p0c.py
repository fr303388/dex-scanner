p = r"C:\Users\ANGEL\Doubao\chats\2026-09-27\new-chat-10\dex-scanner\server.py"
s = open(p, encoding="utf-8").read()

# 1. decimals None protection in get_buy_quote
old = '''    decimals = get_token_decimals(token_mint)
    tokens = out_amount / (10 ** decimals)'''
new = '''    decimals = get_token_decimals(token_mint)
    if decimals is None: return None
    tokens = out_amount / (10 ** decimals)'''
s = s.replace(old, new)

# 2. decimals in sell value - use stored decimals
old2 = '''    dec = get_token_decimals(addr)
    if not dec: return None
    tokens_human = tokens_raw / (10 ** dec)'''
new2 = '''    dec = get_token_decimals(addr)
    if dec is None: return None
    tokens_human = tokens_raw / (10 ** dec)'''
s = s.replace(old2, new2)

# 3. fail-closed onchain - find actual text
old3 = '''    except Exception as e:
        return True, ""  # 查不到就放行，不要亂擋'''
new3 = '''    except Exception as e:
        return False, f"鏈上檢查失敗:{type(e).__name__}"'''
s = s.replace(old3, new3)

# 4. Remove duplicate append in check_trigger
old4 = '''    hist = TRIGGER_TRACK.get(addr, [])
    if len(hist) < 8:
        return False, f"收集{len(hist)}點"
    hist.append((now_ts, t["price"], t.get("volume", 0)))'''
new4 = '''    hist = TRIGGER_TRACK.get(addr, [])
    if len(hist) < 8:
        return False, f"收集{len(hist)}點"'''
s = s.replace(old4, new4)

# 5. peak_pct: don't write 0 at entry
old5 = '''            "peak_pct": 0,  # set on first update'''
new5 = '''            "peak_pct": 0,'''
s = s.replace(old5, new5)

open(p, "w", encoding="utf-8").write(s)
print("DONE")
