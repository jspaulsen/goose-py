"""Runs the real goose binary against a temporary SQLite database."""

import os
import shutil
import sqlite3

import pytest

from goose_py import Goose, GooseCommandError

pytestmark = pytest.mark.skipif(
    shutil.which("goose") is None and "GOOSE_BINARY" not in os.environ,
    reason="goose not installed",
)


@pytest.fixture
def migrations(tmp_path):
    migs = tmp_path / "m"
    migs.mkdir()
    (migs / "001_init.sql").write_text(
        "-- +goose Up\nCREATE TABLE t(id int);\n-- +goose Down\nDROP TABLE t;\n"
    )
    return migs


def _tables(db):
    with sqlite3.connect(db) as conn:
        return {r[0] for r in conn.execute("select name from sqlite_master")}


def test_up_against_sqlite(tmp_path, migrations):
    db = tmp_path / "x.db"
    Goose("sqlite3", str(db), migrations).up()
    assert {"t", "goose_db_version"} <= _tables(db)


def test_bad_migration_dir_raises(tmp_path):
    with pytest.raises(GooseCommandError, match="does not exist"):
        Goose("sqlite3", str(tmp_path / "x.db"), tmp_path / "nope").up()
