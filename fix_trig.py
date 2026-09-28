p = r"C:\Users\ANGEL\Doubao\chats\2026-09-27\new-chat-10\dex-scanner\server.py"
s = open(p, encoding="utf-8").read()
old = '''def check_trigger(addr, t, now_ts):
    """排名與觸發分離：score 通過後，等突破或回踩再起才進場"""
    hist = TRIGGER_TRACK.setdefault(addr, [])
    hist.append((now_ts, t["price"], t.get("volume_24h", 0)))
    # 只留最近 30 分鐘（120 個 15 秒點）'''
new = '''def check_trigger(addr, t, now_ts):
    """讀取已收集的歷史，不重複 append"""
    hist = TRIGGER_TRACK.get(addr, [])'''
s = s.replace(old, new)
open(p, "w", encoding="utf-8").write(s)
print("DONE")
