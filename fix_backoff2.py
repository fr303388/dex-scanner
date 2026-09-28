p = r"C:\Users\ANGEL\Doubao\chats\2026-09-27\new-chat-10\dex-scanner\server.py"
s = open(p, encoding="utf-8").read()
s = s.replace(
  'if "error" in j:\n            return None, "RPC不可用"',
  'if "error" in j:\n            ONCHAIN_FAIL[addr] = time.time() + 300\n            return None, "RPC不可用"'
)
open(p, "w", encoding="utf-8").write(s)
print("DONE")
