# goose-py: Python wrapper for goose — spec

Oct 24, 2026 · @Jacob

Build a pip-installable Python package that ships the [pressly/goose](https://github.com/pressly/goose) binary and exposes a thin, typed Python API over its CLI. No Go toolchain or cgo is needed at install time.

## Goal and non-goals

**Goals**

- `pip install goose-py` works on Linux (x86\_64, aarch64, glibc and musl), macOS (x86\_64, arm64) and Windows (x86\_64) with no extra setup.
- A Python API covering the core goose commands, plus a `goose` console script that passes arguments through to the bundled binary unchanged.
- Pin one upstream goose version per wheel release, so behavior is reproducible.

**Non-goals**

- No cgo or in-process bindings, and no reimplementation of goose logic in Python.
- No Python-authored code migrations; SQL migrations only.
- No sharing of SQLAlchemy or psycopg connections; goose opens its own connection from a driver name and DSN.
- No async API in v1.

## Packaging

Each wheel contains the matching goose binary at `goose_py/_bin/goose` (or `goose.exe`), and the wheel's version encodes the upstream version.

1. **Binary source.** Download the official release assets for the pinned version from the goose GitHub releases, and verify their checksums in CI. Fall back to `go build ./cmd/goose` with `CGO_ENABLED=0` only for targets that have no release asset.
2. **Wheel tags.** Build one platform wheel per target with `py3-none-<platform>` tags (`manylinux_2_17_x86_64`, `manylinux_2_17_aarch64`, `musllinux_1_2_x86_64`, `macosx_10_12_x86_64`, `macosx_11_0_arm64`, `win_amd64`). The package is pure Python apart from the binary, so it needs no ABI tag.
3. **Build tooling.** Use `hatchling` with a small build hook that drops in the right binary per target, driven by a GitHub Actions matrix. Publish with PyPI trusted publishing.
4. **Versioning.** Use `<goose version>.<wrapper patch>`, for example `3.27.1.0`. A wrapper-only fix bumps only the last part.
5. **Binary discovery.** Look up the binary in this order: the `GOOSE_BINARY` env var, then the bundled binary, then `goose` on `PATH`. Raise `GooseNotFoundError` if none is found.
6. **sdist.** Ship an sdist that installs without a binary and uses `GOOSE_BINARY` or `PATH`, for unsupported platforms.

**Open question:** check that the `goose-py` name is free on PyPI before the first release.

## Python API

The public surface is one `Goose` class and one result type. Every method runs the binary once with `subprocess.run` and returns, or raises, synchronously.

```python
from goose_py import Goose

g = Goose(
    driver="postgres",                 # postgres | mysql | sqlite3 | mssql | clickhouse | ...
    dbstring="postgres://...",
    migrations_dir="./migrations",
    table=None,                        # maps to -table / GOOSE_TABLE
    allow_missing=False,               # -allow-missing
    no_versioning=False,               # -no-versioning
    timeout=None,                      # seconds, passed to subprocess
    env=None,                          # extra env vars (e.g. for ENVSUB migrations)
)

g.up() -> GooseResult
g.up_by_one() -> GooseResult
g.up_to(version: int) -> GooseResult
g.down() -> GooseResult
g.down_to(version: int) -> GooseResult
g.redo() -> GooseResult
g.reset() -> GooseResult
g.status() -> list[MigrationStatus]
g.version() -> int
g.create(name: str, kind: Literal["sql"] = "sql") -> Path   # works without a DB
g.fix() -> GooseResult                                     # works without a DB
g.validate() -> GooseResult                                # works without a DB
g.run(*args: str) -> GooseResult                           # raw escape hatch
```

- `GooseResult` is a frozen dataclass with `args`, `returncode`, `stdout` and `stderr`.
- `MigrationStatus` is a frozen dataclass with `version: int`, `source: str`, `applied_at: datetime | None` and `pending: bool`.
- `Goose.binary_version()` returns the bundled goose version string from `goose --version`.
- The `goose` console script runs `os.execv` on the bundled binary (or uses `subprocess` on Windows) with `sys.argv[1:]`.
- Ship type hints and `py.typed`, and support Python 3.9 and later with no runtime dependencies.

## Configuration, errors and output

**Configuration**

- The DSN is passed through the `GOOSE_DBSTRING` env var of the child process, never as an argument, so it doesn't appear in process listings. `GOOSE_DRIVER`, `GOOSE_MIGRATION_DIR` and `GOOSE_TABLE` are set the same way.
- Arguments passed to the constructor override inherited `GOOSE_*` env vars. If an argument is omitted, the inherited env var is used, which matches CLI behavior.
- Commands are built as argument lists; never use `shell=True`.

**Errors**

- `GooseError(Exception)` is the base class and carries `result: GooseResult`.
- `GooseNotFoundError` is raised when no binary is found.
- `GooseCommandError` is raised on a nonzero exit. Its message includes the last stderr lines, with the DSN redacted.
- `GooseTimeoutError` wraps `subprocess.TimeoutExpired`.
- Any substring matching the DSN is redacted from exception messages and `repr` output.

**Parsing output**

- Only `status`, `version` and `create` are parsed; everything else returns raw output.
- First check whether the pinned goose version has a machine-readable output flag (for example JSON for `status`). If it does, use it.
- If it doesn't, parse the text output with anchored regexes kept in a single `_parse.py` module. Test them against golden output captured from the pinned binary.
- A parse failure raises `GooseParseError`, which includes the raw output, rather than returning partial data.

## Testing and acceptance

**Tests**

- Unit tests use a fake binary (a small script set through `GOOSE_BINARY`). They check the argument list and env built for each method, DSN redaction, error mapping and timeouts.
- Parser tests run against golden stdout files captured from the pinned goose version.
- Integration tests run the real bundled binary against SQLite (a temp file) on every matrix target. They cover `create`, `up`, `status`, `down`, `redo`, `reset` and `version`.
- A Postgres integration job runs on Linux only, using a service container.
- After building each wheel, install it into a clean venv and run `goose --version` plus one SQLite `up`.

**Done when**

- [ ] Wheels for all six targets in Packaging build in CI and install in a clean environment with no Go toolchain.
- [ ] Every `Goose` method in the Python API section is implemented, typed and tested.
- [ ] The DSN never appears in argv, exception messages or logs.
- [ ] Bumping the pinned goose version is a one-line change, after which CI refreshes the binaries and fails if the golden output drifts.
- [ ] A README shows install, a five-line usage example, and the binary lookup order.
