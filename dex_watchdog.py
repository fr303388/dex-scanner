"""Watchdog for the dex-scanner background scanner.

Failure mode this exists for (observed 2026-09-29/30):
  the server was launched with `Start-Process -RedirectStandardOutput`,
  which hands the child an anonymous PIPE whose read end is owned by the
  launching PowerShell. When that PowerShell exits, the read end closes and
  every subsequent stdout write raises. The scanner kept trading from CSV
  side-effects but all logging died silently, and the process eventually
  terminated. 22 hours of zero activity, no alarm anywhere.

Detection: server_run.log is written ONLY by the process, roughly every 15s.
If its mtime is older than STALE_SECS, the process is either gone or its
stdout is dead. Either way it needs restarting.

The watchdog is launched the same durable way the server is, so it does not
share the failure mode it is there to catch.
"""
import os, sys, time, subprocess, datetime

BASE = r"C:\Users\ANGEL\Doubao\chats\2026-09-27\new-chat-10\dex-scanner"
PY   = r"C:\Users\ANGEL\AppData\Local\Doubao\User Data\sandbox_runtime\bases\c98c5042338ed152c6f10ecd8591889f\python\python.exe"

STALE_SECS  = 300    # 5 min: log is written every ~15s, so 5 min is 20x margin
GRACE_SECS  = 120    # wait after killing before relaunching
COOLDOWN    = 300    # do not restart more than once per 5 min
HEARTBEAT   = 10     # write a heartbeat line every 10 min (10 cycles)

WATCH_LOG = os.path.join(BASE, "watchdog.log")


def log(msg):
    line = "%s  %s" % (datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), msg)
    print(line, flush=True)
    try:
        with open(WATCH_LOG, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def server_pids():
    """Find python processes running server.py, without needing psutil."""
    out = []
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "(Get-CimInstance Win32_Process -Filter \"Name like '%python%'\" | "
             "Where-Object { $_.CommandLine -like '*server.py*' }).ProcessId"],
            capture_output=True, text=True, timeout=30)
        for line in r.stdout.split():
            if line.strip().isdigit():
                out.append(int(line.strip()))
    except Exception as e:
        log("pid scan failed: %s" % e)
    return out


def check():
    """Return (stale, reason, pids)."""
    pids = server_pids()
    if not pids:
        return True, "process missing", pids
    log_path = os.path.join(BASE, "server_run.log")
    if not os.path.exists(log_path):
        return True, "server_run.log missing", pids
    age = time.time() - os.path.getmtime(log_path)
    if age > STALE_SECS:
        return True, "log %.0fs old (limit %ds)" % (age, STALE_SECS), pids
    return False, "log %.0fs old, %d proc" % (age, len(pids)), pids


def main():
    # --selftest: prove detection works without touching the live server
    if "--selftest" in sys.argv:
        stale, reason, pids = check()
        log("selftest: stale=%s reason=%r pids=%s" % (stale, reason, pids))
        log("selftest: expected stale=False while the server is logging")
        return

    log("watchdog started  (stale threshold %ds, heartbeat every %ds)"
        % (STALE_SECS, HEARTBEAT))
    last_restart = 0.0
    n = 0
    while True:
        time.sleep(60)
        n += 1
        try:
            stale, reason, pids = check()
            # HEARTBEAT: 必須定期寫入，否則「安靜」和「watchdog 自己死了」
            # 無法區分——那等於沒有警報。
            if n % HEARTBEAT == 0:
                log("heartbeat #%d  stale=%s  %s  pids=%s" % (n, stale, reason, pids))
            if not stale:
                continue

            if time.time() - last_restart < COOLDOWN:
                continue
            last_restart = time.time()
            log("STALE: %s  -> restarting" % reason)
            for p in pids:
                try:
                    subprocess.run(["taskkill", "/PID", str(p), "/F"],
                                   capture_output=True, timeout=20)
                    log("  killed pid %d" % p)
                except Exception as e:
                    log("  kill %d failed: %s" % (p, e))
            time.sleep(GRACE_SECS)
            # durable launch: cmd.exe owns the >> redirection, so the log file
            # handle does not depend on this watchdog process staying alive
            subprocess.Popen(
                ["cmd", "/c",
                 '"%s" server.py >> server_run.log 2>&1' % PY],
                cwd=BASE, creationflags=0x00000008 | 0x00000200)  # DETACHED|HIDE
            log("  relaunched; new pids: %s" % server_pids())
        except Exception as e:
            log("watchdog loop error: %s" % e)


if __name__ == "__main__":
    main()
