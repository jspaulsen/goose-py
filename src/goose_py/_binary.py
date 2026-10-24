import os
import shutil

from goose_py.errors import GooseNotFoundError


def find_binary() -> str:
    """Locate goose: ``GOOSE_BINARY`` first, then ``goose`` on ``PATH``."""
    override = os.environ.get("GOOSE_BINARY")
    if override:
        if os.path.isfile(override) and os.access(override, os.X_OK):
            return override
        raise GooseNotFoundError(
            f"GOOSE_BINARY is set to {override!r}, which is not an executable file"
        )

    found = shutil.which("goose")
    if found:
        return found
    raise GooseNotFoundError(
        "goose binary not found: install goose "
        "(https://github.com/pressly/goose) or set GOOSE_BINARY"
    )
