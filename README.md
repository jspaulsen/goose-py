# goose-py

A thin, typed Python API over the [goose](https://github.com/pressly/goose) migration CLI.

goose-py does **not** ship the goose binary. Install goose yourself; goose-py runs it as a subprocess.

## Install

goose-py isn't published to PyPI. Install it from GitHub, pinned to a release tag:

```sh
uv add git+https://github.com/jspaulsen/goose-py --tag v0.1.0
```

Or with pip:

```sh
pip install "goose-py @ git+https://github.com/jspaulsen/goose-py@v0.1.0"
```

See [Releases](https://github.com/jspaulsen/goose-py/releases) for available tags.

goose-py looks for the binary in this order:

1. The `GOOSE_BINARY` env var (must point at an executable file)
2. `goose` on `PATH`

If neither is found, `GooseNotFoundError` is raised.

In a Docker image:

```dockerfile
ADD --chmod=755 https://github.com/pressly/goose/releases/download/v3.28.0/goose_linux_x86_64 /usr/local/bin/goose
```

## Usage

Run migrations at application startup:

```python
import os

from goose_py import Goose, GooseError

try:
    Goose("postgres", os.environ["DATABASE_URL"], "./migrations").up()
except GooseError as e:
    raise SystemExit(f"migrations failed: {e}")
```

`Goose(...)` also accepts `table=`, `allow_missing=`, `no_versioning=`, `timeout=` (seconds) and `env=` (extra env vars for the child process). `run(*args)` runs any other goose command.

## Notes

- The driver, DSN, migrations dir and table are passed to goose through `GOOSE_DRIVER`, `GOOSE_DBSTRING`, `GOOSE_MIGRATION_DIR` and `GOOSE_TABLE`, never as arguments, so the DSN doesn't appear in process listings. Arguments you leave out fall back to those env vars if they're already set.
- goose's `.env` loading is disabled (`-env=none`), so a stray `.env` in your working directory can't change which database is migrated.
- The DSN is replaced with `***` in results, exception messages and `repr`.
- A nonzero exit raises `GooseCommandError` (with `.result` holding stdout/stderr); a timeout raises `GooseTimeoutError`.
