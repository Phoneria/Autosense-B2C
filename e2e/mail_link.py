"""Read a link or verification code from the private test outbox, decoding the actual sent MIME message."""
import email
from email import policy
from pathlib import Path
import re
import sys

recipient, route = sys.argv[1:]
mail_dir = Path(__file__).resolve().parents[1] / ".local/e2e/mail"
for path in sorted(mail_dir.glob("*"), key=lambda item: item.stat().st_mtime, reverse=True):
    message = email.message_from_bytes(path.read_bytes(), policy=policy.default)
    if recipient.lower() not in str(message.get("To", "")).lower():
        continue
    for part in message.walk():
        if part.get_content_type() != "text/plain":
            continue
        body = part.get_content()
        pattern = r"^\s*(\d{6})\s*$" if route == "code" else r"http://127\.0\.0\.1:5176/" + re.escape(route) + r"/[^\s<>]+"
        match = re.search(pattern, body, re.MULTILINE)
        if match:
            print(match.group(1) if route == "code" else match.group(0))
            sys.exit(0)
sys.exit(1)
