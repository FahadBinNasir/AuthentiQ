"""Start the local AuthentiQ API and a Cloudflare quick tunnel together."""

from __future__ import annotations

import os
import re
import signal
import subprocess
import sys
import threading


PORT = int(os.getenv("PORT", "8000"))


def stream_cloudflare(process: subprocess.Popen[str]) -> None:
    assert process.stdout is not None
    for line in process.stdout:
        print(f"[cloudflare] {line}", end="")
        # Only accept the URL from Cloudflare's success line. Error messages
        # also mention api.trycloudflare.com, which is not the tunnel URL.
        if "Visit it at" not in line:
            continue
        match = re.search(r"https://[a-z0-9-]+\.trycloudflare\.com", line)
        if match:
            print(f"\nAuthentiQ public API URL: {match.group(0)}")
            print("Set this URL in Vercel as NEXT_PUBLIC_API_URL, then redeploy.\n")


def main() -> None:
    api = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", str(PORT)],
    )
    tunnel: subprocess.Popen[str] | None = None

    try:
        tunnel = subprocess.Popen(
            ["cloudflared", "tunnel", "--url", f"http://127.0.0.1:{PORT}"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        threading.Thread(target=stream_cloudflare, args=(tunnel,), daemon=True).start()
        print(f"AuthentiQ API starting on http://127.0.0.1:{PORT}")
        print("Press Ctrl+C to stop the API and tunnel.")
        api.wait()
    except FileNotFoundError as exc:
        print(f"Missing command: {exc.filename}", file=sys.stderr)
        print("Install cloudflared or activate the backend virtual environment.", file=sys.stderr)
        raise SystemExit(1)
    except KeyboardInterrupt:
        print("\nStopping AuthentiQ...")
    finally:
        for process in (tunnel, api):
            if process and process.poll() is None:
                process.send_signal(signal.SIGTERM)
        for process in (tunnel, api):
            if process:
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()


if __name__ == "__main__":
    main()
