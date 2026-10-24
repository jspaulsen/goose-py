import json
import pathlib
import sys

import pytest

FAKE_GOOSE = pathlib.Path(__file__).with_name("fake_goose.py")


@pytest.fixture
def fake_goose(tmp_path, monkeypatch):
    """Point GOOSE_BINARY at the fake; return a helper that decodes its output."""
    exe = tmp_path / "goose"
    exe.write_text(f"#!{sys.executable}\n" + FAKE_GOOSE.read_text())
    exe.chmod(0o755)
    monkeypatch.setenv("GOOSE_BINARY", str(exe))
    for var in ("GOOSE_DRIVER", "GOOSE_DBSTRING", "GOOSE_MIGRATION_DIR", "GOOSE_TABLE"):
        monkeypatch.delenv(var, raising=False)
    return lambda result: json.loads(result.stdout)
