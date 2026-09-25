f = r"C:\Users\ANGEL\Doubao\chats\2026-09-12\new-chat\dex_scanner\dashboard.html"
with open(f, "r", encoding="utf-8") as fh:
    c = fh.read()

c = c.replace(
    '''} catch(e){ document.body.insertAdjacentHTML('afterbegin','<div style="background:red;color:white;padding:10px;font-size:12px">JS錯誤: '+e.message+'</div>'); console.error(e); }''',
    '''} catch(e){ console.error(e); }'''
)

with open(f, "w", encoding="utf-8") as fh:
    fh.write(c)
print("done")
