"""The only two exceptions the public API raises (per API contract)."""


class ProtocolError(Exception):
    """Violates an invariant, enum, or state machine rule. Exit code 1."""

    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(f"{code}: {message}")


class LockTimeout(Exception):
    """Could not take the write lock. Exit code 3."""

    def __init__(self, message: str = "write lock timeout"):
        self.message = message
        super().__init__(message)
