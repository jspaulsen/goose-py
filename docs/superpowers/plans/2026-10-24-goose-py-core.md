# goose-py Core Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A pure-Python, typed wrapper over a user-installed `goose` binary, good enough to run `up()` at application startup.

**Architecture:** `Goose` builds an argv list plus a child env (`GOOSE_*` vars carry driver/DSN/dir/table) and calls `subprocess.run` once per method. Every result has the DSN redacted before it is returned or attached to an exception. No bundled binary: lookup is `GOOSE_BINARY`, then `goose` on `PATH`.

**Tech Stack:** Python ≥3.12, `uv_build`, pytest (dev group only), no runtime deps.

**Spec:** `spec.md`, treated as suggestions. Decisions in chat override it: no bundled binary, no hatchling, Python 3.12 floor, `status`/`version`/`create` parsing deferred.

## Global Constraints

- Python `>=3.12`; zero runtime dependencies; ship `py.typed`.
- Never `shell=True`; argv is always a list.
- DSN goes only through `GOOSE_DBSTRING` in the child env, never argv.
- DSN never appears in exception messages, `repr(Goose)`, or a returned/raised `GooseResult`.
- Every invocation passes `-env=none` so goose does not load a `.env` from the app's cwd (my call; verified on goose v3.28.0).
- Constructor args override inherited `GOOSE_*` env vars; omitted args fall back to inherited values.
- Verified env vars on goose v3.28.0: `GOOSE_DRIVER`, `GOOSE_DBSTRING`, `GOOSE_MIGRATION_DIR`, `GOOSE_TABLE`.

## Review Focus

1. DSN echoed back by goose in stderr (e.g. connection errors) → redacted in `GooseCommandError` message and in `err.result.stderr`. (Task 2)
2. `dbstring` omitted, DSN inherited from parent `GOOSE_DBSTRING` → still redacted. (Task 2)
3. `GOOSE_BINARY` set to a path that doesn't exist / isn't executable → `GooseNotFoundError`, not a raw `FileNotFoundError`. (Task 1)
4. A `.env` in the cwd containing `GOOSE_DBSTRING` → ignored (`-env=none` in argv). (Task 2)
5. `migrations_dir` given as `pathlib.Path` → accepted. (Task 2)

## File Structure

- `src/goose_py/__init__.py`: public re-exports only.
- `src/goose_py/_binary.py`: `find_binary()`.
- `src/goose_py/_result.py`: `GooseResult`.
- `src/goose_py/errors.py`: exception hierarchy.
- `src/goose_py/_goose.py`: `Goose` class.
- `tests/fake_goose.py`: fake binary that echoes argv+env as JSON.
- `tests/conftest.py`: `fake_goose` fixture.
- `tests/test_binary.py`, `tests/test_goose.py`, `tests/test_integration.py`.

## PR Stack

- **PR 1, branch `core-up` (Tasks 1–3):** lookup, result/errors, `Goose.up()` + `run()`.
- **PR 2, branch `integration-readme`, stacked on `core-up` (Task 4):** real-goose SQLite test, README.
- **PR 3, branch `more-commands`, stacked on `integration-readme` (Task 5):** remaining pass-through commands.

Candidate later PRs (not in this plan): parsed `status()`/`version()` + `GooseParseError`, `create()` → `Path`, optional bundled-binary package, CI workflow.

---

### Task 1: Project setup, result/errors, binary lookup

**Files:**
- Modify: `pyproject.toml` (real description; `[dependency-groups] dev = ["pytest>=8"]`)
- Modify: `src/goose_py/__init__.py` (drop `hello`)
- Create: `src/goose_py/_result.py`, `src/goose_py/errors.py`, `src/goose_py/_binary.py`
- Test: `tests/test_binary.py`

**Interfaces:**
- Produces:
  - `GooseResult` (`@dataclass(frozen=True)`): `args: tuple[str, ...]`, `returncode: int`, `stdout: str`, `stderr: str`.
  - `GooseError(Exception)`: `__init__(self, message: str, result: GooseResult | None = None)`, attribute `result`.
  - `GooseNotFoundError(GooseError)`, `GooseCommandError(GooseError)`, `GooseTimeoutError(GooseError)`.
  - `find_binary() -> str` in `_binary.py`.
  - `__init__.py` exports `Goose` (added in Task 2), `GooseResult`, and all four errors.

- [ ] **Step 1: Branch and set up.** `git checkout -b core-up`, edit `pyproject.toml`, run `uv sync`.

- [ ] **Step 2: Write failing tests in `tests/test_binary.py`**

```python
def test_goose_binary_env_wins(tmp_path, monkeypatch):
    exe = tmp_path / "mygoose"; exe.write_text("#!/bin/sh\n"); exe.chmod(0o755)
    monkeypatch.setenv("GOOSE_BINARY", str(exe))
    assert find_binary() == str(exe)

def test_goose_binary_env_missing_file_raises(monkeypatch):
    monkeypatch.setenv("GOOSE_BINARY", "/nonexistent/goose")
    with pytest.raises(GooseNotFoundError, match="GOOSE_BINARY"):
        find_binary()

def test_falls_back_to_path(tmp_path, monkeypatch):
    exe = tmp_path / "goose"; exe.write_text("#!/bin/sh\n"); exe.chmod(0o755)
    monkeypatch.delenv("GOOSE_BINARY", raising=False)
    monkeypatch.setenv("PATH", str(tmp_path))
    assert find_binary() == str(exe)

def test_not_found_anywhere(tmp_path, monkeypatch):
    monkeypatch.delenv("GOOSE_BINARY", raising=False)
    monkeypatch.setenv("PATH", str(tmp_path))
    with pytest.raises(GooseNotFoundError, match="install goose"):
        find_binary()
```

- [ ] **Step 3: Run `uv run pytest tests/test_binary.py -v`.** Expected: FAIL (import error).

- [ ] **Step 4: Implement** `_result.py`, `errors.py`, `_binary.py`. `find_binary` checks `GOOSE_BINARY` first: if it is set, it must be an existing executable file (`os.access(p, os.X_OK)`), otherwise raise mentioning `GOOSE_BINARY`. Then it falls back to `shutil.which("goose")`. The not-found message: `"goose binary not found: install goose (https://github.com/pressly/goose) or set GOOSE_BINARY"`.

- [ ] **Step 5: Run `uv run pytest -v`.** Expected: PASS.

- [ ] **Step 6: Commit** `feat: add result type, errors, and binary lookup`.

### Task 2: `Goose` class with env/argv building and `run()`

**Files:**
- Create: `src/goose_py/_goose.py`, `tests/fake_goose.py`, `tests/conftest.py`
- Modify: `src/goose_py/__init__.py`
- Test: `tests/test_goose.py`

**Interfaces:**
- Consumes: `find_binary`, `GooseResult`, the errors.
- Produces:
  - `Goose.__init__(self, driver: str | None = None, dbstring: str | None = None, migrations_dir: str | os.PathLike[str] | None = None, *, table: str | None = None, allow_missing: bool = False, no_versioning: bool = False, timeout: float | None = None, env: Mapping[str, str] | None = None)`
  - `Goose.run(self, *args: str) -> GooseResult`: raises `GooseCommandError` on nonzero exit and `GooseTimeoutError` on timeout.

**Fake binary:** `tests/fake_goose.py` is a Python script with a `#!<sys.executable>` shebang written by the fixture into `tmp_path/goose` and chmod 755. It prints `json.dumps({"argv": sys.argv[1:], "env": {k: v for k in os.environ if k.startswith(("GOOSE_", "EXTRA_"))}})` to stdout, writes `$FAKE_STDERR` to stderr if set, sleeps `$FAKE_SLEEP` seconds if set, and exits with `$FAKE_EXIT` (default 0). The `fake_goose` fixture sets `GOOSE_BINARY` to it, clears inherited `GOOSE_DRIVER`/`GOOSE_DBSTRING`/`GOOSE_MIGRATION_DIR`/`GOOSE_TABLE`, and returns a helper `call(result) -> dict` that `json.loads(result.stdout)`.

- [ ] **Step 1: Write failing tests in `tests/test_goose.py`**

```python
def test_dsn_and_config_go_in_env_not_argv(fake_goose):
    g = Goose("postgres", "postgres://u:secret@h/db", pathlib.Path("migs"), table="t")
    out = fake_goose(g.run("up"))
    assert out["env"]["GOOSE_DBSTRING"] == "postgres://u:secret@h/db"
    assert out["env"]["GOOSE_DRIVER"] == "postgres"
    assert out["env"]["GOOSE_MIGRATION_DIR"] == "migs"
    assert out["env"]["GOOSE_TABLE"] == "t"
    assert all("secret" not in a for a in out["argv"])

def test_argv_flags_before_command(fake_goose):
    g = Goose("sqlite3", "x.db", "m", allow_missing=True, no_versioning=True)
    assert fake_goose(g.run("up-to", "5"))["argv"] == [
        "-env=none", "-allow-missing", "-no-versioning", "up-to", "5"]

def test_default_argv_disables_dotenv(fake_goose):
    assert fake_goose(Goose("sqlite3", "x.db").run("up"))["argv"] == ["-env=none", "up"]

def test_inherited_env_used_when_arg_omitted(fake_goose, monkeypatch):
    monkeypatch.setenv("GOOSE_DBSTRING", "inherited.db")
    assert fake_goose(Goose("sqlite3").run("up"))["env"]["GOOSE_DBSTRING"] == "inherited.db"

def test_arg_overrides_inherited_env(fake_goose, monkeypatch):
    monkeypatch.setenv("GOOSE_DRIVER", "mysql")
    assert fake_goose(Goose("sqlite3", "x.db").run("up"))["env"]["GOOSE_DRIVER"] == "sqlite3"

def test_extra_env_passed(fake_goose):
    out = fake_goose(Goose("sqlite3", "x.db", env={"EXTRA_A": "1"}).run("up"))
    assert out["env"]["EXTRA_A"] == "1"

def test_nonzero_exit_raises_with_redacted_stderr(fake_goose, monkeypatch):
    monkeypatch.setenv("FAKE_EXIT", "1")
    monkeypatch.setenv("FAKE_STDERR", "failed to connect to postgres://u:secret@h/db")
    g = Goose("postgres", "postgres://u:secret@h/db")
    with pytest.raises(GooseCommandError) as ei:
        g.run("up")
    assert "secret" not in str(ei.value)
    assert "***" in str(ei.value)
    assert ei.value.result.returncode == 1
    assert "secret" not in ei.value.result.stderr

def test_inherited_dsn_is_redacted(fake_goose, monkeypatch):
    monkeypatch.setenv("GOOSE_DBSTRING", "postgres://u:secret@h/db")
    monkeypatch.setenv("FAKE_EXIT", "1")
    monkeypatch.setenv("FAKE_STDERR", "bad postgres://u:secret@h/db")
    with pytest.raises(GooseCommandError) as ei:
        Goose("postgres").run("up")
    assert "secret" not in str(ei.value)

def test_successful_result_is_redacted(fake_goose):
    r = Goose("postgres", "postgres://u:secret@h/db").run("up")
    assert "secret" not in r.stdout   # fake echoes env, which contains the DSN

def test_repr_hides_dsn():
    assert "secret" not in repr(Goose("postgres", "postgres://u:secret@h/db"))

def test_timeout_raises(fake_goose, monkeypatch):
    monkeypatch.setenv("FAKE_SLEEP", "5")
    with pytest.raises(GooseTimeoutError):
        Goose("sqlite3", "x.db", timeout=0.2).run("up")
```

- [ ] **Step 2: Run `uv run pytest tests/test_goose.py -v`.** Expected: FAIL (no `Goose`).

- [ ] **Step 3: Implement `Goose` in `_goose.py`.**
  - Resolve the binary lazily in `run()` with `find_binary()`, so constructing a `Goose` never fails.
  - Child env: `{**os.environ, **(env or {})}`, then set each non-None of `GOOSE_DRIVER`/`GOOSE_DBSTRING`/`GOOSE_MIGRATION_DIR` (`os.fspath`)/`GOOSE_TABLE`.
  - argv: `[binary, "-env=none", *("-allow-missing" if set), *("-no-versioning" if set), *args]`. `GooseResult.args` omits the binary path.
  - Call `subprocess.run(argv, env=..., capture_output=True, text=True, timeout=self.timeout)`.
  - Redact the child env's `GOOSE_DBSTRING`: if it is non-empty, replace every occurrence with `***` in stdout, stderr and args before building `GooseResult`.
  - Nonzero exit raises `GooseCommandError(f"goose {' '.join(args)} failed (exit {rc}): {last 10 stderr lines}", result)`.
  - `TimeoutExpired` becomes `GooseTimeoutError(f"goose {...} timed out after {timeout}s")` via `raise ... from None`, so the exception chain doesn't carry the unredacted env.
  - `__repr__`: `Goose(driver=..., migrations_dir=...)`, no DSN.
  - Export `Goose` from `__init__.py`.

- [ ] **Step 4: Run `uv run pytest -v`.** Expected: all PASS.

- [ ] **Step 5: Commit** `feat: add Goose class with env-based config and DSN redaction`.

### Task 3: `up()`

**Files:**
- Modify: `src/goose_py/_goose.py`
- Test: `tests/test_goose.py`

**Interfaces:**
- Produces: `Goose.up(self) -> GooseResult`, equivalent to `self.run("up")`.

- [ ] **Step 1: Write the failing test**

```python
def test_up(fake_goose):
    assert fake_goose(Goose("sqlite3", "x.db").up())["argv"] == ["-env=none", "up"]
```

- [ ] **Step 2: Run it.** Expected: FAIL (`AttributeError`).
- [ ] **Step 3: Implement `up`.**
- [ ] **Step 4: Run `uv run pytest -v`.** Expected: PASS.
- [ ] **Step 5: Commit** `feat: add Goose.up`, then push and open PR 1 (`core-up` → `main`).

### Task 4: SQLite integration test and README (PR 2)

**Files:**
- Create: `tests/test_integration.py`
- Modify: `README.md`

**Interfaces:**
- Consumes: `Goose`, `GooseCommandError`.

- [ ] **Step 1: Branch** with `git checkout -b integration-readme` (from `core-up`).

- [ ] **Step 2: Write the test.** Mark the module `pytest.mark.skipif(shutil.which("goose") is None and "GOOSE_BINARY" not in os.environ, reason="goose not installed")`.

```python
def test_up_against_sqlite(tmp_path):
    migs = tmp_path / "m"; migs.mkdir()
    (migs / "001_init.sql").write_text(
        "-- +goose Up\nCREATE TABLE t(id int);\n-- +goose Down\nDROP TABLE t;\n")
    db = tmp_path / "x.db"
    Goose("sqlite3", str(db), migs).up()
    names = {r[0] for r in sqlite3.connect(db).execute("select name from sqlite_master")}
    assert "t" in names and "goose_db_version" in names

def test_bad_migration_dir_raises(tmp_path):
    with pytest.raises(GooseCommandError, match="does not exist"):
        Goose("sqlite3", str(tmp_path / "x.db"), tmp_path / "nope").up()
```

- [ ] **Step 3: Run `uv run pytest tests/test_integration.py -v`.** Expected: PASS (goose v3.28.0 is installed locally).

- [ ] **Step 4: Write the README.** Include: what it is (wrapper over a goose binary *you* install); install; the lookup order (`GOOSE_BINARY`, then `PATH`); a Dockerfile snippet; a five-line startup example using `Goose(...).up()` and catching `GooseError`; and a note that config is passed via `GOOSE_*` env vars, `.env` is not loaded, and the DSN is redacted. For the Dockerfile snippet, download the release asset `goose_linux_x86_64` from `https://github.com/pressly/goose/releases/download/v3.28.0/` to `/usr/local/bin/goose` and chmod it.

- [ ] **Step 5: Commit** `test: add sqlite integration test; docs: README`, then push and open PR 2 with base `core-up`.

### Task 5: Pass-through commands (PR 3)

**Files:**
- Modify: `src/goose_py/_goose.py`
- Test: `tests/test_goose.py`, `tests/test_integration.py`

**Interfaces:**
- Produces, each returning `GooseResult` via `self.run(...)`:
  - `up_by_one()` → `up-by-one`
  - `up_to(version: int)` → `up-to <version>`
  - `down()` → `down`
  - `down_to(version: int)` → `down-to <version>`
  - `redo()` → `redo`
  - `reset()` → `reset`
  - `validate()` → `validate`
  - `fix()` → `fix`

- [ ] **Step 1: Branch** with `git checkout -b more-commands` (from `integration-readme`).

- [ ] **Step 2: Write failing tests.** One parametrized test:

```python
@pytest.mark.parametrize("call,expected", [
    (lambda g: g.up_by_one(), ["up-by-one"]),
    (lambda g: g.up_to(3), ["up-to", "3"]),
    (lambda g: g.down(), ["down"]),
    (lambda g: g.down_to(0), ["down-to", "0"]),
    (lambda g: g.redo(), ["redo"]),
    (lambda g: g.reset(), ["reset"]),
    (lambda g: g.validate(), ["validate"]),
    (lambda g: g.fix(), ["fix"]),
])
def test_command_argv(fake_goose, call, expected):
    assert fake_goose(call(Goose("sqlite3", "x.db")))["argv"] == ["-env=none", *expected]
```

  Add an integration test: `up()` then `down()` on the SQLite fixture, and assert table `t` is gone.

- [ ] **Step 3: Run.** Expected: FAIL.
- [ ] **Step 4: Implement the eight methods.**
- [ ] **Step 5: Run `uv run pytest -v`.** Expected: all PASS.
- [ ] **Step 6: Commit** `feat: add remaining pass-through commands`, then push and open PR 3 with base `integration-readme`.
