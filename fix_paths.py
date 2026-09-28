import os
p = r"C:\Users\ANGEL\Doubao\chats\2026-09-27\new-chat-10\dex-scanner\server.py"
s = open(p, encoding="utf-8").read()

# Add BASE after imports
old = 'BASE = os.path.dirname(os.path.abspath(__file__))'
if old not in s:
    s = s.replace(
        'DECISION_LOG = os.path.join',
        'BASE = os.path.dirname(os.path.abspath(__file__))\nDECISION_LOG = os.path.join'
    )

# Fix relative paths
s = s.replace('SIM_FILE = "sim_portfolio.json"', 'SIM_FILE = os.path.join(BASE, "sim_portfolio.json")')
s = s.replace('FIRST_SEEN_FILE = "first_seen.json"', 'FIRST_SEEN_FILE = os.path.join(BASE, "first_seen.json")')

open(p, "w", encoding="utf-8").write(s)
print("DONE")
