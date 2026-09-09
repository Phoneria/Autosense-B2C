"""Reference databases are never initialized or written by this application."""
import sqlite3
from pathlib import Path

from django.conf import settings


def readonly_connection(path):
    path = Path(path).resolve(strict=True)
    conn = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA query_only=ON")
    return conn


def get_connection(db_path=None):
    return readonly_connection(db_path or settings.B2C_BASELINE_DB)
