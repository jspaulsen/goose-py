from goose_py._result import GooseResult


class GooseError(Exception):
    """Base class for all goose-py errors."""

    def __init__(self, message: str, result: GooseResult | None = None) -> None:
        super().__init__(message)
        self.result = result


class GooseNotFoundError(GooseError):
    """No goose binary could be located."""


class GooseCommandError(GooseError):
    """goose exited with a nonzero status."""


class GooseTimeoutError(GooseError):
    """goose did not finish within the configured timeout."""
