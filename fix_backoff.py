p = r"C:\Users\ANGEL\Doubao\chats\2026-09-27\new-chat-10\dex-scanner\server.py"
s = open(p, encoding="utf-8").read()

# Add ONCHAIN_FAIL dict
s = s.replace(
  "ONCHAIN_CACHE = {}  # addr -> (ok, reason)",
  "ONCHAIN_CACHE = {}\nONCHAIN_FAIL = {}  # addr -> retry_after_ts"
)

# Add backoff check at start of function
old = '''    if addr in ONCHAIN_CACHE:
        return ONCHAIN_CACHE[addr]
    try:'''
new = '''    if addr in ONCHAIN_CACHE:
        return ONCHAIN_CACHE[addr]
    if ONCHAIN_FAIL.get(addr, 0) > time.time():
        return None, "RPC退避中"
    try:'''
s = s.replace(old, new)

# Set backoff on failure
old2 = '''    except Exception as e:
        return None, f"RPC:{type(e).__name__}"'''
new2 = '''    except Exception as e:
        ONCHAIN_FAIL[addr] = time.time() + 300
        return None, f"RPC:{type(e).__name__}"'''
s = s.replace(old2, new2)

open(p, "w", encoding="utf-8").write(s)
print("DONE")
