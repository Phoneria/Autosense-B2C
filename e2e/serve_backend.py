"""Disposable browser-test accounts/outbox; production and development data are untouched."""
import os
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
TEST_DATA = ROOT / ".local/e2e"
# This fixed directory contains only data created by this test launcher.
if TEST_DATA.exists():
    shutil.rmtree(TEST_DATA)
TEST_DATA.mkdir(parents=True, mode=0o700)
env = os.environ.copy()
# Ignore production connection configuration inherited from the parent shell.
for key in ("B2C_DATABASE_URL", "B2C_REDIS_URL"):
    env.pop(key, None)
env.update({
    "B2C_ACCOUNT_DB": str(TEST_DATA / "accounts.sqlite3"),
    "B2C_MAIL_DIR": str(TEST_DATA / "mail"),
    "B2C_EMAIL_BACKEND": "accounts.mail.PrivateFileBackend",
    "B2C_FRONTEND_URL": "http://127.0.0.1:5176",
    "B2C_ALLOWED_HOSTS": "127.0.0.1,localhost,testserver",
    "B2C_DEBUG": "true",
})
python = str(ROOT / ".venv/bin/python")
subprocess.run([python, "manage.py", "migrate", "--noinput"], cwd=ROOT / "backend", env=env, check=True)
os.chdir(ROOT / "backend")
os.execve(python, [python, "manage.py", "runserver", "127.0.0.1:8010", "--noreload"], env)
