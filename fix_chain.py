p = r"C:\Users\ANGEL\Doubao\chats\2026-09-27\new-chat-10\dex-scanner\server.py"
lines = open(p, encoding="utf-8").readlines()
# Line 298 (0-indexed 297): return True, ""
lines[297] = '        return False, "持倉集中度資料缺失"\n'
# Line 300 (0-indexed 299): return True, ""
lines[299] = '        return False, f"鏈上檢查失敗:{type(e).__name__}"\n'
open(p, "w", encoding="utf-8").write("".join(lines))
print("DONE")
