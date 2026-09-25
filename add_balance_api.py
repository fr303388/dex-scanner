f = r"C:\Users\ANGEL\Doubao\chats\2026-09-12\new-chat\dex_scanner\server.py"
with open(f, "r", encoding="utf-8") as fh:
    c = fh.read()

# Add balance endpoint before the notify_toggle route
old = '@app.route("/api/notify_toggle", methods=["POST"])'
new = '''@app.route("/api/balance/<pubkey>")
def api_balance(pubkey):
    try:
        import requests as req
        r = req.post("https://api.mainnet-beta.solana.com",
            json={"jsonrpc":"2.0","id":1,"method":"getBalance","params":[pubkey]}, timeout=10)
        sol = r.json()["result"]["value"] / 1e9
        return jsonify({"ok": True, "sol": sol})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})

@app.route("/api/notify_toggle", methods=["POST"])'''

c = c.replace(old, new, 1)

with open(f, "w", encoding="utf-8") as fh:
    fh.write(c)
print("done")
