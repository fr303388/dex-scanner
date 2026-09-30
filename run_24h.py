"""24-hour analysis run for the post-$150k-floor data.

Launched detached via cmd.exe so the log handle does not depend on any
parent shell (the failure mode that silently killed the scanner for 22h
on 2026-09-29).

Runs each analysis independently so one failure cannot hide the others,
and appends a single DONE marker the moment it finishes, so "it ran" is
distinguishable from "it is still waiting" and from "it died silently".
"""
import os, sys, time, subprocess, datetime

BASE = r"C:\Users\ANGEL\Doubao\chats\2026-09-27\new-chat-10\dex-scanner"
PY   = r"C:\Users\ANGEL\AppData\Local\Doubao\User Data\sandbox_runtime\bases\c98c5042338ed152c6f10ecd8591889f\python\python.exe"
TEMP = r"C:\Users\ANGEL\AppData\Local\Temp\opencode"

REPORT = os.path.join(BASE, "analysis_24h.txt")
MARKER = os.path.join(BASE, "watchdog.log")   # durable, already watched


def log(msg):
    line = "%s  [24h] %s" % (datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), msg)
    print(line, flush=True)
    try:
        with open(MARKER, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def run(title, script, *args):
    log("start  %s" % title)
    try:
        r = subprocess.run([PY, script] + list(args), cwd=TEMP,
                           capture_output=True, text=True, timeout=900,
                           encoding="utf-8", errors="replace")
        return "\n".join([
            "", "=" * 78, title, "=" * 78,
            r.stdout or "",
            ("[stderr] " + r.stderr) if (r.stderr or "").strip() else "",
            "[exit %d]" % r.returncode, ""])
    except Exception as e:
        return "\n".join(["", "=" * 78, title, "=" * 78,
                          "FAILED: %s" % e, ""])


def main():
    # target passed as epoch seconds, or compute from --hours
    if "--hours" in sys.argv:
        hrs = float(sys.argv[sys.argv.index("--hours") + 1])
        target = time.time() + hrs * 3600
    else:
        target = time.mktime(time.strptime("2026-10-01 20:05", "%Y-%m-%d %H:%M"))

    wait = target - time.time()
    log("armed, firing at %s (in %.1f h)"
        % (datetime.datetime.fromtimestamp(target).strftime("%Y-%m-%d %H:%M"), wait / 3600))
    while wait > 0:
        time.sleep(min(300, wait))
        wait = target - time.time()
    log("firing")

    body = ["=" * 78,
            "24-HOUR ANALYSIS RUN  %s" % datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
            "=" * 78,
            "",
            "Purpose: measure the $150k liquidity floor in effect, using live",
            "on-chain state rather than cohort.csv, which censors exactly the",
            "tokens that die.", ""]
    body.append(run("1  FUNNEL + so15 RECORDING  (post_change_check.py)",
                    os.path.join(TEMP, "post_change_check.py")))
    body.append(run("2  LIVE ON-CHAIN STATE OF EVERY CLOSED TRADE  (live_check.py)",
                    os.path.join(TEMP, "live_check.py")))
    body.append(run("3  SCALE-OUT COUNTERFACTUAL  (exit_lab.py)",
                    os.path.join(TEMP, "exit_lab.py")))
    body.append(run("4  LIQUIDITY BAND OUTCOMES  (strategy_report5.py)",
                    os.path.join(TEMP, "strategy_report5.py")))

    text = "\n".join(body)
    with open(REPORT, "w", encoding="utf-8") as f:
        f.write(text)
    log("DONE  wrote %s (%d bytes)" % (REPORT, len(text.encode("utf-8"))))


if __name__ == "__main__":
    main()
