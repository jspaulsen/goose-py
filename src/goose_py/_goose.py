import os
import subprocess
from collections.abc import Callable, Mapping

from goose_py._binary import find_binary
from goose_py._result import GooseResult
from goose_py.errors import GooseCommandError, GooseTimeoutError

_REDACTED = "***"
_STDERR_TAIL_LINES = 10


class Goose:
    """Runs goose commands against one database.

    ``driver``, ``dbstring``, ``migrations_dir`` and ``table`` are passed to goose
    through ``GOOSE_*`` env vars (never argv). Any left as ``None`` fall back to
    the inherited environment.
    """

    def __init__(
        self,
        driver: str | None = None,
        dbstring: str | None = None,
        migrations_dir: str | os.PathLike[str] | None = None,
        *,
        table: str | None = None,
        allow_missing: bool = False,
        no_versioning: bool = False,
        timeout: float | None = None,
        env: Mapping[str, str] | None = None,
    ) -> None:
        self.driver = driver
        self._dbstring = dbstring
        self.migrations_dir = migrations_dir
        self.table = table
        self.allow_missing = allow_missing
        self.no_versioning = no_versioning
        self.timeout = timeout
        self.env = dict(env or {})

    def __repr__(self) -> str:
        return f"Goose(driver={self.driver!r}, migrations_dir={self.migrations_dir!r})"

    def run(self, *args: str) -> GooseResult:
        """Run goose with ``args`` after the configured flags.

        Raises ``GooseCommandError`` on a nonzero exit and ``GooseTimeoutError``
        if ``timeout`` elapses. The DSN is redacted from the returned result.
        """
        child_env = self._child_env()
        argv = self._flags() + list(args)
        redact = _redactor(child_env.get("GOOSE_DBSTRING", ""))
        shown_args = tuple(redact(a) for a in argv)

        try:
            proc = subprocess.run(
                [find_binary(), *argv],
                env=child_env,
                capture_output=True,
                text=True,
                timeout=self.timeout,
            )
        except subprocess.TimeoutExpired:
            # `from None` keeps the unredacted TimeoutExpired out of the chain.
            raise GooseTimeoutError(
                f"goose {' '.join(shown_args)} timed out after {self.timeout}s"
            ) from None

        result = GooseResult(
            args=shown_args,
            returncode=proc.returncode,
            stdout=redact(proc.stdout),
            stderr=redact(proc.stderr),
        )
        if result.returncode != 0:
            tail = "\n".join(result.stderr.strip().splitlines()[-_STDERR_TAIL_LINES:])
            raise GooseCommandError(
                f"goose {' '.join(shown_args)} failed (exit {result.returncode}): {tail}",
                result,
            )
        return result

    def _flags(self) -> list[str]:
        flags = ["-env=none"]
        if self.allow_missing:
            flags.append("-allow-missing")
        if self.no_versioning:
            flags.append("-no-versioning")
        return flags

    def _child_env(self) -> dict[str, str]:
        child = {**os.environ, **self.env}
        overrides = {
            "GOOSE_DRIVER": self.driver,
            "GOOSE_DBSTRING": self._dbstring,
            "GOOSE_MIGRATION_DIR": (
                os.fspath(self.migrations_dir) if self.migrations_dir is not None else None
            ),
            "GOOSE_TABLE": self.table,
        }
        child.update({k: v for k, v in overrides.items() if v is not None})
        return child


def _redactor(secret: str) -> Callable[[str], str]:
    if not secret:
        return lambda text: text
    return lambda text: text.replace(secret, _REDACTED)
