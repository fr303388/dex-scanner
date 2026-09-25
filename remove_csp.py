f = r"C:\Users\ANGEL\Doubao\chats\2026-09-12\new-chat\dex_scanner\server.py"
with open(f, "r", encoding="utf-8") as fh:
    c = fh.read()

# Remove CSP header from index route
c = c.replace('''    return Response(html, mimetype="text/html", headers={
        "Content-Security-Policy": "unsafe-inline unsafe-eval * data: blob:",
        "Access-Control-Allow-Origin": "*"
    })''', '    return Response(html, mimetype="text/html")')

# Also remove after_request CSP
import re
c = re.sub(r'@app\.after_request.*?return r\n\n', '', c, flags=re.DOTALL)

with open(f, "w", encoding="utf-8") as fh:
    fh.write(c)
print("done")
