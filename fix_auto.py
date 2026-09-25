f = r"C:\Users\ANGEL\Doubao\chats\2026-09-12\new-chat\dex_scanner\server.py"
with open(f, "r", encoding="utf-8") as fh:
    lines = fh.readlines()

out = []
skip = False
for i, line in enumerate(lines):
    if "fresh = [t for t in all_tokens" in line:
        out.append(line)
        out.append("    AUTO_TRADE = False\n")
        skip = True
        continue
    if skip and line.strip().startswith("for t in fresh"):
        out.append("    if AUTO_TRADE:\n")
        out.append("    " + line)
        skip = False
        continue
    out.append(line)

with open(f, "w", encoding="utf-8") as fh:
    fh.writelines(out)
print("done")
