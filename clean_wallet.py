f = r"C:\Users\ANGEL\Doubao\chats\2026-09-12\new-chat\dex_scanner\dashboard.html"
with open(f, "r", encoding="utf-8") as fh:
    lines = fh.readlines()

# Find and remove wallet JS lines (from "async function connect" to the closing "}" before </script>)
out = []
skip = False
for i, line in enumerate(lines):
    if 'async function connect' in line:
        skip = True
        continue
    if skip and line.strip() == '}':
        skip = False
        continue
    if skip:
        continue
    out.append(line)

with open(f, "w", encoding="utf-8") as fh:
    fh.writelines(out)
print("done")
