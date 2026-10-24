from dataclasses import dataclass


@dataclass(frozen=True)
class GooseResult:
    """Outcome of one goose invocation. ``args`` excludes the binary path."""

    args: tuple[str, ...]
    returncode: int
    stdout: str
    stderr: str
