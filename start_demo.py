"""Start everything for a demo with one command:  python start_demo.py

1. the device page (Streamlit) on this laptop
2. a free Cloudflare tunnel, which gives the page a public https address
3. writes that address to PAGE_BASE_URL in .env, so the bot's replies link to it
4. the Photon bot

The tunnel address changes every time, which is why step 3 is automatic.
Needs cloudflared (winget install Cloudflare.cloudflared). Ctrl+C stops everything.
Options:  --port 8501   --no-bot (page and tunnel only)
"""
import argparse
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import urllib.request

ROOT = os.path.dirname(os.path.abspath(__file__))
ENV = os.path.join(ROOT, ".env")
CLOUDFLARED = shutil.which("cloudflared") or r"C:\Program Files (x86)\cloudflared\cloudflared.exe"


def wait_for(url: str, seconds: int = 60) -> bool:
    for _ in range(seconds):
        try:
            if urllib.request.urlopen(url, timeout=3).status == 200:
                return True
        except Exception:
            time.sleep(1)
    return False


def set_page_url(url: str) -> None:
    text = open(ENV, encoding="utf8").read() if os.path.exists(ENV) else ""
    line = f"PAGE_BASE_URL={url}"
    text = (re.sub(r"^PAGE_BASE_URL=.*$", line, text, flags=re.M) if re.search(r"^PAGE_BASE_URL=", text, re.M)
            else text.rstrip("\n") + "\n" + line + "\n")
    with open(ENV, "w", encoding="utf8") as f:
        f.write(text)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8501)
    ap.add_argument("--no-bot", action="store_true")
    ap.add_argument("--tunnel", action="store_true", help="serve the page from this laptop even if a hosted page is set")
    args = ap.parse_args()
    procs = []
    # If .env already points at a permanently hosted page (not localhost, not a temporary tunnel),
    # keep it: only the bot needs to run on this laptop.
    current = ""
    if os.path.exists(ENV):
        hit = re.search(r"^PAGE_BASE_URL=(.*)$", open(ENV, encoding="utf8").read(), re.M)
        current = hit.group(1).strip() if hit else ""
    hosted = current.startswith("https://") and "trycloudflare" not in current and "localhost" not in current
    if hosted and not args.tunnel:
        print(f"Page is hosted at {current}. Starting only the bot. (Use --tunnel to serve the page from this laptop.)")
        try:
            subprocess.run([sys.executable, "-m", "bot.photon_bot"], cwd=ROOT)
        except KeyboardInterrupt:
            print("Stopping.")
        return
    try:
        print("1/4 starting the page...")
        procs.append(subprocess.Popen([sys.executable, "-m", "streamlit", "run", "page/app.py", "--server.headless",
                                       "true", "--server.port", str(args.port)], cwd=ROOT,
                                      stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
        if not wait_for(f"http://localhost:{args.port}/_stcore/health"):
            sys.exit("The page did not start. Try: streamlit run page/app.py")

        print("2/4 opening the public tunnel...")
        tunnel = subprocess.Popen([CLOUDFLARED, "tunnel", "--no-autoupdate", "--url", f"http://localhost:{args.port}"],
                                  stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        procs.append(tunnel)
        url = None
        for line in tunnel.stdout:
            hit = re.search(r"https://[a-z0-9-]+\.trycloudflare\.com", line)
            if hit:
                url = hit.group(0)
                break
        # keep reading the tunnel's log, or it fills the pipe and the tunnel freezes
        threading.Thread(target=lambda: [None for _ in tunnel.stdout], daemon=True).start()
        if not url:
            sys.exit("The tunnel did not start. Check the internet connection and try again.")
        # A new address takes a few seconds to exist on the internet. Asking too early makes Windows
        # remember "not found" for a while, so wait first, and only warn if this laptop cannot see it yet.
        time.sleep(15)
        if not wait_for(f"{url}/_stcore/health", 90):
            print("   (this laptop cannot open the address yet; it usually works from a phone within a minute)")

        print(f"3/4 page is online: {url}")
        set_page_url(url)

        if args.no_bot:
            print("Running without the bot. Ctrl+C to stop.")
            tunnel.wait()
        else:
            print("4/4 starting the bot. Ctrl+C to stop everything.\n")
            procs.append(subprocess.Popen([sys.executable, "-m", "bot.photon_bot"], cwd=ROOT))
            procs[-1].wait()
    except KeyboardInterrupt:
        print("\nStopping.")
    finally:
        for p in reversed(procs):
            p.terminate()


if __name__ == "__main__":
    main()
