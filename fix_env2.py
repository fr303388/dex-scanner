f = r"C:\Users\ANGEL\Doubao\chats\2026-09-12\new-chat\dex_scanner\server.py"
with open(f, "r", encoding="utf-8") as fh:
    c = fh.read()

c = c.replace(
    '''        lines_env = r'C:\\Users\\ANGEL\\Doubao\\chats\\2026-09-12\\new-chat\\stonkfly\\.env'
        TOKEN = CHAT_ID = ""
        if lines_env.exists():
            for line in lines_env.read_text().splitlines():''',
    '''        TOKEN = CHAT_ID = ""
        envf = r'C:\\Users\\ANGEL\\Doubao\\chats\\2026-09-12\\new-chat\\stonkfly\\.env'
        import os
        if os.path.exists(envf):
            for line in open(envf, encoding="utf-8").read().splitlines():'''
)

with open(f, "w", encoding="utf-8") as fh:
    fh.write(c)
print("done")
