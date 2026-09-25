f = r"C:\Users\ANGEL\Doubao\chats\2026-09-12\new-chat\dex_scanner\server.py"
with open(f, "r", encoding="utf-8") as fh:
    c = fh.read()

# Fix: read from stonkfly .env like the rest of the code
c = c.replace(
    "        lines_env = Path(__file__).parent / \".env\"",
    "        lines_env = r'C:\\Users\\ANGEL\\Doubao\\chats\\2026-09-12\\new-chat\\stonkfly\\.env'"
)

with open(f, "w", encoding="utf-8") as fh:
    fh.write(c)
print("done")
