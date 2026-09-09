import sqlite3
from pathlib import Path

import pytest
from django.conf import settings

from accounts.models import User
from search.models import Listing
from search.pricing.reference import readonly_connection
from search.routers import ReferenceRouter


def test_reference_connection_cannot_write_or_create(tmp_path):
    path = tmp_path / "ref.db"
    with sqlite3.connect(path) as conn:
        conn.execute("create table reference(value integer)")
        conn.execute("insert into reference values(1)")
    conn = readonly_connection(path)
    try:
        assert conn.execute("select value from reference").fetchone()[0] == 1
        with pytest.raises(sqlite3.OperationalError):
            conn.execute("insert into reference values(2)")
        with pytest.raises(sqlite3.OperationalError):
            conn.execute("create table accidental(value integer)")
    finally:
        conn.close()
    with pytest.raises(FileNotFoundError):
        readonly_connection(tmp_path / "missing.db")
    assert not (tmp_path / "missing.db").exists()


def test_routing_isolates_accounts_and_reference_data():
    router = ReferenceRouter()
    assert router.db_for_read(User) == "default"
    assert router.db_for_write(User) == "default"
    assert router.db_for_read(Listing) == "reference"
    with pytest.raises(PermissionError):
        router.db_for_write(Listing)
    for app in ["accounts", "account", "sessions", "search"]:
        assert router.allow_migrate("reference", app) is False
    assert router.allow_migrate("default", "search") is False
    assert router.allow_migrate("default", "accounts") is True


def test_copied_listing_snapshot_has_no_account_tables():
    # A real-data smoke check; deploys must provide a snapshot before running tests.
    path = Path(settings.PROJECT_DIR) / "data/listings.sqlite3"
    if not path.exists():
        pytest.skip("Reference snapshot is not present in this checkout")
    with readonly_connection(path) as conn:
        tables = {r[0] for r in conn.execute("select name from sqlite_master where type='table'")}
        assert tables == {"search_listing"}
        assert conn.execute("select count(*) from search_listing").fetchone()[0] > 0
