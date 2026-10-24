import pytest

from goose_py import GooseNotFoundError
from goose_py._binary import find_binary


def _make_exe(path):
    path.write_text("#!/bin/sh\n")
    path.chmod(0o755)
    return path


def test_goose_binary_env_wins(tmp_path, monkeypatch):
    exe = _make_exe(tmp_path / "mygoose")
    monkeypatch.setenv("GOOSE_BINARY", str(exe))
    assert find_binary() == str(exe)


def test_goose_binary_env_missing_file_raises(monkeypatch):
    monkeypatch.setenv("GOOSE_BINARY", "/nonexistent/goose")
    with pytest.raises(GooseNotFoundError, match="GOOSE_BINARY"):
        find_binary()


def test_falls_back_to_path(tmp_path, monkeypatch):
    exe = _make_exe(tmp_path / "goose")
    monkeypatch.delenv("GOOSE_BINARY", raising=False)
    monkeypatch.setenv("PATH", str(tmp_path))
    assert find_binary() == str(exe)


def test_not_found_anywhere(tmp_path, monkeypatch):
    monkeypatch.delenv("GOOSE_BINARY", raising=False)
    monkeypatch.setenv("PATH", str(tmp_path))
    with pytest.raises(GooseNotFoundError, match="install goose"):
        find_binary()


def test_relative_goose_binary_is_made_absolute(tmp_path, monkeypatch):
    _make_exe(tmp_path / "mygoose")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("GOOSE_BINARY", "mygoose")
    assert find_binary() == str(tmp_path / "mygoose")
