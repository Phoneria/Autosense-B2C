#!/usr/bin/env python3
"""Launch only this project's backend and frontend, cleaning up child processes."""
import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PYTHON = ROOT / ".venv/bin/python"
BACKEND_PORT = int(os.getenv("B2C_BACKEND_PORT", "8010"))
FRONTEND_PORT = int(os.getenv("B2C_FRONTEND_PORT", "5176"))
API_TARGET = os.getenv("B2C_API_TARGET", f"http://127.0.0.1:{BACKEND_PORT}")


def main():
    for port in (BACKEND_PORT, FRONTEND_PORT):
        with socket.socket() as sock:
            if sock.connect_ex(("127.0.0.1", port)) == 0:
                sys.exit(f"{port} portu kullanımda. Mevcut B2C sürecini kapatıp yeniden deneyin.")
    if not PYTHON.exists() or not (ROOT / "frontend/node_modules").exists():
        sys.exit("Önce ./setup.sh çalıştırın.")
    required = [("B2C_REFERENCE_DB", "listings.sqlite3"), ("B2C_BASELINE_DB", "paket_fiyatlari.db"), ("B2C_GALLERY_DB", "galeri.db")]
    if any(not Path(os.getenv(env, str(ROOT / "data" / name))).exists() for env, name in required):
        sys.exit("Referans verileri eksik. README'deki veri aktarımı adımını tamamlayın.")
    (ROOT / ".local").mkdir(exist_ok=True)
    subprocess.run([str(PYTHON), "backend/manage.py", "migrate", "--noinput"], cwd=ROOT, check=True)
    children = []

    def stop(*_):
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    try:
        children.append(subprocess.Popen([str(PYTHON), "backend/manage.py", "runserver", f"127.0.0.1:{BACKEND_PORT}", "--noreload"], cwd=ROOT, start_new_session=True))
        children.append(subprocess.Popen(["npm", "run", "dev", "--", "--host", "127.0.0.1", "--port", str(FRONTEND_PORT), "--strictPort"], cwd=ROOT / "frontend", start_new_session=True, env={**os.environ, "B2C_API_TARGET": API_TARGET, "B2C_FRONTEND_PORT": str(FRONTEND_PORT)}))
        print(f"\nB2C: http://localhost:{FRONTEND_PORT}\nTest e-postaları: .local/mail/ (yalnızca bu bilgisayarda)\nÇıkış: Ctrl+C\n", flush=True)
        while all(child.poll() is None for child in children):
            time.sleep(0.4)
    except KeyboardInterrupt:
        pass
    finally:
        for child in children:
            if child.poll() is None:
                os.killpg(child.pid, signal.SIGTERM)
        for child in children:
            try:
                child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(child.pid, signal.SIGKILL)


if __name__ == "__main__":
    main()
