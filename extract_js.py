f = r"C:\Users\ANGEL\Doubao\chats\2026-09-12\new-chat\dex_scanner\dashboard.html"
with open(f, "r", encoding="utf-8") as fh:
    c = fh.read()

# Extract the second script block (the main load() code)
import re
m = re.search(r'<script>\n(let seenSymbols.*?)\n</script>', c, re.DOTALL)
if m:
    js = m.group(1)
    with open(r"C:\Users\ANGEL\Doubao\chats\2026-09-12\new-chat\dex_scanner\app.js", "w", encoding="utf-8") as fh:
        fh.write(js)
    # Replace inline script with external reference
    c = c.replace('<script>\n' + js + '\n</script>', '<script src="/app.js"></script>')
    with open(f, "w", encoding="utf-8") as fh:
        fh.write(c)
    print("done, js extracted")
else:
    print("no match")
