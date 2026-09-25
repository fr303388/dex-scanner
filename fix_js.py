f = r"C:\Users\ANGEL\Doubao\chats\2026-09-12\new-chat\dex_scanner\dashboard.html"
with open(f, "r", encoding="utf-8") as fh:
    lines = fh.readlines()
for i, line in enumerate(lines):
    if "尚無交易紀錄" in line:
        lines[i] = '    }).join("") : "<div style=\'color:#666\'>尚無交易紀錄</div>";\n'
        print(f"fixed line {i+1}")
with open(f, "w", encoding="utf-8") as fh:
    fh.writelines(lines)
