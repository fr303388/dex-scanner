f = r"C:\Users\ANGEL\Doubao\chats\2026-09-12\new-chat\dex_scanner\dashboard.html"
with open(f, "r", encoding="utf-8") as fh:
    c = fh.read()

# Remove wallet buttons HTML
import re
c = re.sub(r'<div style="display:flex;gap:8px;align-items:center;margin-bottom:12px;flex-wrap:wrap">.*?</div>\s*</div>', '', c, flags=re.DOTALL)

# Remove wallet JS
c = re.sub(r'// ===== 錢包連接 =====.*?\n\}\n', '', c, flags=re.DOTALL)

with open(f, "w", encoding="utf-8") as fh:
    fh.write(c)
print("done")
