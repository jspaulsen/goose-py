import json
import pathlib

import pytest

from goose_py import Goose, GooseCommandError, GooseNotFoundError, GooseTimeoutError

DSN = "postgres://u:secret@h/db"


def test_dsn_and_config_go_in_env_not_argv(fake_goose):
    g = Goose("postgres", DSN, pathlib.Path("migs"), table="t")
    out = fake_goose(g.run("up"))
    assert out["env"]["GOOSE_DBSTRING"] == "***"  # fake echoes it; result is redacted
    assert out["env"]["GOOSE_DRIVER"] == "postgres"
    assert out["env"]["GOOSE_MIGRATION_DIR"] == "migs"
    assert out["env"]["GOOSE_TABLE"] == "t"
    assert all("secret" not in a for a in out["argv"])


def test_argv_flags_before_command(fake_goose):
    g = Goose("sqlite3", "x.db", "m", allow_missing=True, no_versioning=True)
    assert fake_goose(g.run("up-to", "5"))["argv"] == [
        "-env=none",
        "-allow-missing",
        "-no-versioning",
        "up-to",
        "5",
    ]


def test_default_argv_disables_dotenv(fake_goose):
    assert fake_goose(Goose("sqlite3", "x.db").run("up"))["argv"] == ["-env=none", "up"]


def test_result_args_exclude_binary(fake_goose):
    assert Goose("sqlite3", "x.db").run("up").args == ("-env=none", "up")


def test_inherited_env_used_when_arg_omitted(fake_goose, monkeypatch):
    monkeypatch.setenv("GOOSE_DRIVER", "sqlite3")
    assert fake_goose(Goose().run("up"))["env"]["GOOSE_DRIVER"] == "sqlite3"


def test_arg_overrides_inherited_env(fake_goose, monkeypatch):
    monkeypatch.setenv("GOOSE_DRIVER", "mysql")
    assert fake_goose(Goose("sqlite3", "x.db").run("up"))["env"]["GOOSE_DRIVER"] == "sqlite3"


def test_extra_env_passed(fake_goose):
    out = fake_goose(Goose("sqlite3", "x.db", env={"EXTRA_A": "1"}).run("up"))
    assert out["env"]["EXTRA_A"] == "1"


def test_nonzero_exit_raises_with_redacted_stderr(fake_goose, monkeypatch):
    monkeypatch.setenv("FAKE_EXIT", "1")
    monkeypatch.setenv("FAKE_STDERR", f"failed to connect to {DSN}")
    with pytest.raises(GooseCommandError) as ei:
        Goose("postgres", DSN).run("up")
    assert "secret" not in str(ei.value)
    assert "***" in str(ei.value)
    assert ei.value.result.returncode == 1
    assert "secret" not in ei.value.result.stderr


def test_inherited_dsn_is_redacted(fake_goose, monkeypatch):
    monkeypatch.setenv("GOOSE_DBSTRING", DSN)
    monkeypatch.setenv("FAKE_EXIT", "1")
    monkeypatch.setenv("FAKE_STDERR", f"bad {DSN}")
    with pytest.raises(GooseCommandError) as ei:
        Goose("postgres").run("up")
    assert "secret" not in str(ei.value)
    assert "secret" not in ei.value.result.stdout


def test_repr_hides_dsn():
    assert "secret" not in repr(Goose("postgres", DSN))


def test_construction_does_not_need_binary(monkeypatch):
    monkeypatch.setenv("GOOSE_BINARY", "/nonexistent/goose")
    Goose("sqlite3", "x.db")


def test_timeout_raises(fake_goose, monkeypatch):
    monkeypatch.setenv("FAKE_SLEEP", "5")
    with pytest.raises(GooseTimeoutError):
        Goose("sqlite3", "x.db", timeout=0.2).run("up")


def test_up(fake_goose):
    assert fake_goose(Goose("sqlite3", "x.db").up())["argv"] == ["-env=none", "up"]


def test_go_quoted_dsn_is_redacted(fake_goose, monkeypatch):
    # goose logs an unknown driver's DSN with Go's %q, which escapes quotes/backslashes.
    dsn = "user=alice password='hun\\'ter2\"x'"
    monkeypatch.setenv("FAKE_EXIT", "1")
    monkeypatch.setenv("FAKE_STDERR", f"-dbstring={json.dumps(dsn)}: unknown dialect")
    with pytest.raises(GooseCommandError) as ei:
        Goose("postgresql", dsn).run("up")
    assert "ter2" not in str(ei.value)
    assert "ter2" not in ei.value.result.stderr


def test_unexecutable_binary_raises_goose_error(tmp_path, monkeypatch):
    exe = tmp_path / "goose"
    exe.write_bytes(b"\x7fELF not really")
    exe.chmod(0o755)
    monkeypatch.setenv("GOOSE_BINARY", str(exe))
    with pytest.raises(GooseNotFoundError, match="could not execute"):
        Goose("sqlite3", "x.db").up()
