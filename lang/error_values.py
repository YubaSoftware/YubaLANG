"""Typed, inspectable error values for YubaLANG's ``try``/``catch`` protocol.

Error values are dictionary subclasses so they can be inspected with the
existing dictionary and attribute syntax.  They deliberately never expose
Python exception objects or tracebacks to the program.
"""

from __future__ import annotations

import re
import sqlite3
import zipfile
from typing import Any

from .diagnostic_codes import code_for_runtime


ERROR_KINDS = frozenset(
    {
        "any",
        "error",
        "language",
        "syntax",
        "type",
        "value",
        "index",
        "key",
        "attribute",
        "io",
        "zero_division",
        "overflow",
        "recursion",
        "assertion",
        "memory",
        "limit",
        "timeout",
        "http",
        "sqlite",
        "archive",
        "regex",
        "json",
        "process",
        "import",
        "record",
        "pattern",
    }
)

_KIND_BY_CODE = {
    "stack-overflow": "recursion",
    "memory-limit": "memory",
    "uncaught-exception": "language",
    "assertion-failed": "assertion",
    "division-by-zero": "zero_division",
    "index-error": "index",
    "key-error": "key",
    "attribute-error": "attribute",
    "io-error": "io",
    "syntax-error": "syntax",
    "type-error": "type",
    "value-error": "value",
    "limit-error": "limit",
    "import-error": "import",
    "import-cycle": "import",
    "record-error": "record",
    "invalid-pattern": "pattern",
    "non-exhaustive-match": "pattern",
    "regex-error": "regex",
    "regex-backtracking": "regex",
    "archive-error": "archive",
    "sqlite-error": "sqlite",
    "http-error": "http",
    "process-error": "process",
    "timeout-error": "timeout",
}


class StdLibError(ValueError):
    """A standard-library failure with an explicit catchable kind."""

    def __init__(self, kind: str, message: str, code: str | None = None) -> None:
        super().__init__(message)
        self.kind = kind
        self.code = code or f"{kind}-error"


class ErrorValue(dict):
    """A catchable error with kind, message, code, cause, and stack data."""

    def __init__(
        self,
        kind: str = "error",
        message: str = "",
        *,
        code: str | None = None,
        cause: Any = None,
        stack: list[dict[str, Any]] | None = None,
        value: Any = None,
    ) -> None:
        super().__init__(
            kind=kind,
            message=message,
            code=code or f"{kind}-error",
            cause=cause,
            stack=list(stack or []),
            value=value,
        )

    @property
    def kind(self) -> str:
        return self["kind"]

    @property
    def message(self) -> str:
        return self["message"]

    @property
    def code(self) -> str:
        return self["code"]

    @property
    def cause(self) -> Any:
        return self["cause"]

    @property
    def stack(self) -> list[dict[str, Any]]:
        return self["stack"]

    def __str__(self) -> str:
        return str(self["message"])

    def __repr__(self) -> str:
        return (
            f"ErrorValue(kind={self['kind']!r}, message={self['message']!r}, "
            f"code={self['code']!r})"
        )


def kind_for_error(error: BaseException) -> str:
    """Return the stable catchable kind for a host exception."""
    explicit = getattr(error, "kind", None)
    if isinstance(explicit, str) and explicit:
        return explicit
    if isinstance(error, sqlite3.Error):
        return "sqlite"
    if isinstance(error, zipfile.BadZipFile):
        return "archive"
    if isinstance(error, re.error):
        return "regex"
    if isinstance(error, TimeoutError):
        return "timeout"
    if isinstance(error, OverflowError):
        return "overflow"
    if isinstance(error, MemoryError):
        return "memory"
    if isinstance(error, RecursionError):
        return "recursion"
    code = code_for_runtime(error)
    if code in _KIND_BY_CODE:
        return _KIND_BY_CODE[code]
    return "error"


def stack_from_runtime(
    runtime: Any, source_name: str, line_number: int
) -> list[dict[str, Any]]:
    """Capture the YubaLANG call stack as plain data."""
    frames = [
        {"function": name, "source": source, "line": line}
        for name, source, line in runtime.call_stack
    ]
    frames.append({"function": "<top>", "source": source_name, "line": line_number})
    return frames


def error_value_for(
    error: BaseException,
    runtime: Any,
    source_name: str,
    line_number: int,
) -> ErrorValue:
    """Convert a host exception into an inspectable :class:`ErrorValue`."""
    from .runtime import LanguageException

    stack = stack_from_runtime(runtime, source_name, line_number)
    if isinstance(error, LanguageException):
        value = error.value
        if isinstance(value, ErrorValue):
            if not value["stack"]:
                value["stack"] = stack
            if not value["code"]:
                value["code"] = "uncaught-exception"
            return value
        return ErrorValue(
            "language",
            str(value),
            code="uncaught-exception",
            stack=stack,
            value=value,
        )
    kind = kind_for_error(error)
    cause = getattr(error, "__cause__", None)
    cause_value = None
    if isinstance(cause, ErrorValue):
        cause_value = cause
    return ErrorValue(
        kind,
        str(error),
        code=code_for_runtime(error),
        cause=cause_value,
        stack=stack,
    )


def kind_matches(kind: str, requested: str) -> bool:
    requested = requested.lower()
    return requested in ("any", "error") or kind.lower() == requested
