"""Milestone 3 standard-library modules.

The functions in this module are intentionally host-value based: they return
plain YubaLANG values (strings, numbers, lists, dictionaries) or tracked
resource handles so every API can be used through the existing command and
expression syntax.
"""

from __future__ import annotations

import decimal as _decimal
import fnmatch
import glob as _glob
import io
import os
import re
import shutil
import sqlite3
import stat
import statistics as _statistics
import sys
import tempfile as _tempfile
import threading
import time
import uuid as _uuid
import zipfile
from pathlib import Path
from typing import Any, Callable

from .error_values import StdLibError


def _string(value: Any, label: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{label} must be a string.")
    return value


def _boolean(value: Any, label: str) -> bool:
    if not isinstance(value, bool):
        raise TypeError(f"{label} must be a boolean.")
    return value


def _integer(value: Any, label: str, minimum: int | None = None, maximum: int | None = None) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{label} must be an integer.")
    if minimum is not None and value < minimum:
        raise ValueError(f"{label} must be at least {minimum}.")
    if maximum is not None and value > maximum:
        raise ValueError(f"{label} must be at most {maximum}.")
    return value


def _number(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{label} must be a number.")
    result = float(value)
    if not result == result or result in (float("inf"), float("-inf")):
        raise ValueError(f"{label} must be finite.")
    return result


def _bytes(value: Any, label: str) -> bytes:
    if isinstance(value, (bytes, bytearray)):
        return bytes(value)
    raise TypeError(f"{label} must be bytes or bytearray.")


def _register(runtime: Any, resource: Any) -> None:
    if runtime is None:
        raise RuntimeError("This operation requires a YubaLANG runtime.")
    runtime.register_resource(resource)


# ---------------------------------------------------------------------------
# std.regex


_MAX_REGEX_PATTERN = 4096
_MAX_REGEX_TEXT = 8_388_608
_MAX_REGEX_MATCHES = 100_000
_NESTED_QUANTIFIER = re.compile(r"\((?:[^()]|\([^()]*\))*[+*][^()]*\)[+*{]")


def _regex_flags(value: str) -> int:
    flags = 0
    for character in _string(value, "Flags"):
        if character == "i":
            flags |= re.IGNORECASE
        elif character == "m":
            flags |= re.MULTILINE
        elif character == "s":
            flags |= re.DOTALL
        elif character == "x":
            flags |= re.VERBOSE
        elif character == "a":
            flags |= re.ASCII
        elif character == "u":
            flags |= re.UNICODE
        else:
            raise ValueError(
                "Regex flags may contain only i, m, s, x, a, and u."
            )
    return flags


def _regex_compile(
    pattern: str,
    flags: str = "",
    allow_unsafe: bool = False,
) -> re.Pattern[str]:
    text = _string(pattern, "Pattern")
    if len(text) > _MAX_REGEX_PATTERN:
        raise StdLibError(
            "regex",
            f"Regex pattern exceeds the {_MAX_REGEX_PATTERN}-character limit.",
            "regex-error",
        )
    if not _boolean(allow_unsafe, "allow_unsafe") and _NESTED_QUANTIFIER.search(text):
        raise StdLibError(
            "regex",
            "Regex pattern contains a nested quantifier that may backtrack "
            "excessively; rewrite it or pass allow_unsafe=true.",
            "regex-backtracking",
        )
    try:
        return re.compile(text, _regex_flags(flags))
    except re.error as error:
        raise StdLibError(
            "regex",
            f"Invalid regular expression: {error}",
            "regex-error",
        ) from error


def _regex_pattern(value: Any, flags: str, allow_unsafe: bool) -> re.Pattern[str]:
    if isinstance(value, dict):
        source = value.get("pattern")
        stored_flags = value.get("flags", "")
        if not isinstance(source, str) or not isinstance(stored_flags, str):
            raise TypeError("A compiled pattern must contain string 'pattern' and 'flags'.")
        return _regex_compile(source, stored_flags, allow_unsafe)
    return _regex_compile(_string(value, "Pattern"), flags, allow_unsafe)


def _regex_text(value: Any) -> str:
    text = _string(value, "Text")
    if len(text) > _MAX_REGEX_TEXT:
        raise StdLibError(
            "regex",
            f"Regex text exceeds the {_MAX_REGEX_TEXT}-character limit.",
            "regex-error",
        )
    return text


def _match_result(match: re.Match[str]) -> dict[str, Any]:
    return {
        "match": match.group(0),
        "groups": list(match.groups()),
        "groupdict": dict(match.groupdict()),
        "start": match.start(),
        "end": match.end(),
        "span": [match.start(), match.end()],
    }


def regex_functions() -> dict[str, Callable[..., Any]]:
    def compile_pattern(
        pattern: str,
        flags: str = "",
        allow_unsafe: bool = False,
    ) -> dict[str, Any]:
        compiled = _regex_compile(pattern, flags, allow_unsafe)
        return {
            "pattern": compiled.pattern,
            "flags": _string(flags, "Flags"),
            "groups": compiled.groups,
        }

    def is_match(
        pattern: Any,
        text: str,
        flags: str = "",
        allow_unsafe: bool = False,
    ) -> bool:
        return _regex_pattern(pattern, flags, allow_unsafe).search(_regex_text(text)) is not None

    def fullmatch(
        pattern: Any,
        text: str,
        flags: str = "",
        allow_unsafe: bool = False,
    ) -> bool:
        return _regex_pattern(pattern, flags, allow_unsafe).fullmatch(_regex_text(text)) is not None

    def search(
        pattern: Any,
        text: str,
        flags: str = "",
        allow_unsafe: bool = False,
    ) -> dict[str, Any] | None:
        match = _regex_pattern(pattern, flags, allow_unsafe).search(_regex_text(text))
        return None if match is None else _match_result(match)

    def match(
        pattern: Any,
        text: str,
        flags: str = "",
        allow_unsafe: bool = False,
    ) -> dict[str, Any] | None:
        match = _regex_pattern(pattern, flags, allow_unsafe).match(_regex_text(text))
        return None if match is None else _match_result(match)

    def findall(
        pattern: Any,
        text: str,
        flags: str = "",
        allow_unsafe: bool = False,
    ) -> list[Any]:
        matches = _regex_pattern(pattern, flags, allow_unsafe).findall(_regex_text(text))
        if len(matches) > _MAX_REGEX_MATCHES:
            raise StdLibError(
                "regex",
                f"Regex found more than {_MAX_REGEX_MATCHES} matches.",
                "regex-error",
            )
        return [list(item) if isinstance(item, tuple) else item for item in matches]

    def finditer(
        pattern: Any,
        text: str,
        flags: str = "",
        allow_unsafe: bool = False,
    ) -> list[dict[str, Any]]:
        results = []
        for match in _regex_pattern(pattern, flags, allow_unsafe).finditer(_regex_text(text)):
            results.append(_match_result(match))
            if len(results) > _MAX_REGEX_MATCHES:
                raise StdLibError(
                    "regex",
                    f"Regex found more than {_MAX_REGEX_MATCHES} matches.",
                    "regex-error",
                )
        return results

    def split(
        pattern: Any,
        text: str,
        maxsplit: int = 0,
        flags: str = "",
        allow_unsafe: bool = False,
    ) -> list[str]:
        count = _integer(maxsplit, "maxsplit", 0)
        return _regex_pattern(pattern, flags, allow_unsafe).split(
            _regex_text(text), maxsplit=count
        )

    def sub(
        pattern: Any,
        replacement: str,
        text: str,
        count: int = 0,
        flags: str = "",
        allow_unsafe: bool = False,
    ) -> str:
        return _regex_pattern(pattern, flags, allow_unsafe).sub(
            _string(replacement, "Replacement"),
            _regex_text(text),
            count=_integer(count, "count", 0),
        )

    def subn(
        pattern: Any,
        replacement: str,
        text: str,
        count: int = 0,
        flags: str = "",
        allow_unsafe: bool = False,
    ) -> dict[str, Any]:
        result, replacements = _regex_pattern(pattern, flags, allow_unsafe).subn(
            _string(replacement, "Replacement"),
            _regex_text(text),
            count=_integer(count, "count", 0),
        )
        return {"text": result, "count": replacements}

    def escape(text: str) -> str:
        return re.escape(_string(text, "Text"))

    def group_count(pattern: Any, flags: str = "", allow_unsafe: bool = False) -> int:
        return _regex_pattern(pattern, flags, allow_unsafe).groups

    return {
        "compile": compile_pattern,
        "is_match": is_match,
        "fullmatch": fullmatch,
        "search": search,
        "match": match,
        "findall": findall,
        "finditer": finditer,
        "split": split,
        "sub": sub,
        "subn": subn,
        "escape": escape,
        "group_count": group_count,
    }


# ---------------------------------------------------------------------------
# std.glob


def glob_functions() -> dict[str, Callable[..., Any]]:
    def match(path: str, pattern: str) -> bool:
        return fnmatch.fnmatchcase(
            _string(path, "Path"), _string(pattern, "Pattern")
        )

    def filter_paths(paths: list[str], pattern: str) -> list[str]:
        if not isinstance(paths, (list, tuple)) or any(
            not isinstance(item, str) for item in paths
        ):
            raise TypeError("Paths must be a list or tuple of strings.")
        text = _string(pattern, "Pattern")
        return sorted(item for item in paths if fnmatch.fnmatchcase(item, text))

    def expand(pattern: str, recursive: bool = True) -> list[str]:
        text = _string(pattern, "Pattern")
        if "\x00" in text:
            raise ValueError("Pattern must not contain NUL characters.")
        return sorted(_glob.glob(text, recursive=_boolean(recursive, "recursive")))

    def has_magic(pattern: str) -> bool:
        return _glob.has_magic(_string(pattern, "Pattern"))

    def walk(path: str = ".", pattern: str = "*", recursive: bool = False) -> list[str]:
        root = Path(_string(path, "Path"))
        if not root.is_dir():
            raise ValueError(f"'{path}' is not a directory.")
        matcher = _string(pattern, "Pattern")
        iterator = root.rglob("*") if _boolean(recursive, "recursive") else root.glob("*")
        return sorted(
            str(item)
            for item in iterator
            if item.is_file() and fnmatch.fnmatchcase(item.name, matcher)
        )

    return {
        "match": match,
        "filter": filter_paths,
        "expand": expand,
        "has_magic": has_magic,
        "walk": walk,
    }


# ---------------------------------------------------------------------------
# std.tempfile


class _TempResource:
    def __init__(self, path: Path, directory: bool) -> None:
        self.path = path
        self.directory = directory
        self.closed = False

    def close(self) -> None:
        if self.closed:
            return
        self.closed = True
        try:
            if self.directory:
                shutil.rmtree(self.path, ignore_errors=True)
            else:
                self.path.unlink(missing_ok=True)
        except OSError:
            pass


def tempfile_functions(runtime: Any = None) -> dict[str, Callable[..., Any]]:
    tracked: dict[str, _TempResource] = {}

    def create_file(
        suffix: str = "",
        prefix: str = "tmp",
        directory: str | None = None,
        text: str = "",
    ) -> dict[str, Any]:
        target_directory = (
            _string(directory, "Directory") if directory is not None else None
        )
        handle = _tempfile.NamedTemporaryFile(
            mode="w",
            suffix=_string(suffix, "Suffix"),
            prefix=_string(prefix, "Prefix"),
            dir=target_directory,
            delete=False,
            encoding="utf-8",
            newline="",
        )
        try:
            handle.write(_string(text, "Text"))
        finally:
            handle.close()
        path = Path(handle.name)
        resource = _TempResource(path, directory=False)
        tracked[str(path)] = resource
        _register(runtime, resource)
        return {"path": str(path), "kind": "file"}

    def create_directory(
        suffix: str = "",
        prefix: str = "tmp",
        directory: str | None = None,
    ) -> dict[str, Any]:
        path = Path(
            _tempfile.mkdtemp(
                suffix=_string(suffix, "Suffix"),
                prefix=_string(prefix, "Prefix"),
                dir=_string(directory, "Directory") if directory is not None else None,
            )
        )
        resource = _TempResource(path, directory=True)
        tracked[str(path)] = resource
        _register(runtime, resource)
        return {"path": str(path), "kind": "directory"}

    def name(
        suffix: str = "",
        prefix: str = "tmp",
        directory: str | None = None,
    ) -> str:
        descriptor, temporary_name = _tempfile.mkstemp(
            suffix=_string(suffix, "Suffix"),
            prefix=_string(prefix, "Prefix"),
            dir=_string(directory, "Directory") if directory is not None else None,
        )
        os.close(descriptor)
        Path(temporary_name).unlink(missing_ok=True)
        return temporary_name

    def cleanup(path: str) -> bool:
        target = str(Path(_string(path, "Path")))
        resource = tracked.pop(target, None)
        if resource is not None:
            resource.close()
            if runtime is not None:
                runtime.close_resource(resource)
            return True
        candidate = Path(target)
        if candidate.is_dir():
            shutil.rmtree(candidate)
            return True
        if candidate.exists():
            candidate.unlink()
            return True
        return False

    def is_tracked(path: str) -> bool:
        return str(Path(_string(path, "Path"))) in tracked

    return {
        "file": create_file,
        "directory": create_directory,
        "name": name,
        "cleanup": cleanup,
        "is_tracked": is_tracked,
    }


# ---------------------------------------------------------------------------
# std.archive


_MAX_ARCHIVE_MEMBERS = 100_000
_MAX_ARCHIVE_BYTES = 268_435_456
_MAX_ARCHIVE_ENTRY = 67_108_864


def _safe_archive_name(name: str) -> str:
    text = _string(name, "Archive member name").replace("\\", "/")
    if not text or text.endswith("/"):
        raise StdLibError(
            "archive", "Archive member name must name a file.", "archive-error"
        )
    if text.startswith("/") or re.match(r"^[A-Za-z]:", text):
        raise StdLibError(
            "archive",
            "Archive member names must be relative.",
            "archive-error",
        )
    parts = [part for part in text.split("/") if part not in ("", ".")]
    if not parts or any(part == ".." for part in parts):
        raise StdLibError(
            "archive",
            "Archive member names must not contain '..'.",
            "archive-error",
        )
    return "/".join(parts)


def _safe_extract_path(root: Path, name: str) -> Path:
    safe_name = _safe_archive_name(name)
    candidate = (root / safe_name).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError as error:
        raise StdLibError(
            "archive",
            f"Archive member '{name}' escapes the destination directory.",
            "archive-error",
        ) from error
    return candidate


class _ArchiveWriter:
    def __init__(self, target: Path, overwrite: bool) -> None:
        self.target = target
        self.overwrite = overwrite
        self.closed = False
        self.aborted = False
        self.temporary_path: Path | None = None
        self.archive: zipfile.ZipFile | None = None
        if target.exists() and not overwrite:
            raise FileExistsError(f"Archive '{target}' already exists.")
        target.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = _tempfile.mkstemp(
            prefix=f".{target.name}.", suffix=".tmp", dir=target.parent
        )
        os.close(descriptor)
        self.temporary_path = Path(temporary_name)
        self.archive = zipfile.ZipFile(
            self.temporary_path, "w", compression=zipfile.ZIP_DEFLATED
        )

    def close(self) -> None:
        if self.closed:
            return
        self.closed = True
        assert self.archive is not None and self.temporary_path is not None
        self.archive.close()
        if self.aborted:
            self.temporary_path.unlink(missing_ok=True)
            return
        os.replace(self.temporary_path, self.target)
        self.temporary_path = None

    def abort(self) -> None:
        if self.closed:
            return
        self.aborted = True
        self.close()


def archive_functions(runtime: Any = None) -> dict[str, Callable[..., Any]]:
    writers: dict[int, _ArchiveWriter] = {}
    counter = [0]

    def _writer(handle: Any) -> _ArchiveWriter:
        identifier = handle.get("id") if isinstance(handle, dict) else handle
        writer = writers.get(identifier) if isinstance(identifier, int) else None
        if writer is None or writer.closed:
            raise ValueError("Archive handle is not open.")
        return writer

    def create(path: str, overwrite: bool = False) -> dict[str, Any]:
        target = Path(_string(path, "Path"))
        writer = _ArchiveWriter(target, _boolean(overwrite, "overwrite"))
        counter[0] += 1
        identifier = counter[0]
        writers[identifier] = writer
        _register(runtime, writer)
        return {"id": identifier, "path": str(target)}

    def _add(handle: Any, name: str, data: bytes) -> None:
        writer = _writer(handle)
        safe_name = _safe_archive_name(name)
        assert writer.archive is not None
        writer.archive.writestr(safe_name, data)

    def add_bytes(handle: Any, name: str, data: Any) -> None:
        if isinstance(data, str):
            payload = data.encode("utf-8")
        else:
            payload = _bytes(data, "Archive data")
        if len(payload) > _MAX_ARCHIVE_ENTRY:
            raise ValueError(
                f"Archive entry exceeds the {_MAX_ARCHIVE_ENTRY}-byte limit."
            )
        _add(handle, name, payload)

    def add_text(handle: Any, name: str, text: str) -> None:
        _add(handle, name, _string(text, "Text").encode("utf-8"))

    def add_file(handle: Any, name: str, source: str) -> None:
        path = Path(_string(source, "Source path"))
        if not path.is_file():
            raise ValueError(f"'{source}' is not a file.")
        size = path.stat().st_size
        if size > _MAX_ARCHIVE_ENTRY:
            raise ValueError(
                f"Archive entry exceeds the {_MAX_ARCHIVE_ENTRY}-byte limit."
            )
        _add(handle, name, path.read_bytes())

    def close(handle: Any) -> None:
        identifier = handle.get("id") if isinstance(handle, dict) else handle
        if not isinstance(identifier, int) or identifier not in writers:
            return None
        writer = writers.pop(identifier)
        if runtime is not None:
            runtime.close_resource(writer)
        else:
            writer.close()
        return None

    def abort(handle: Any) -> None:
        identifier = handle.get("id") if isinstance(handle, dict) else handle
        if not isinstance(identifier, int) or identifier not in writers:
            return None
        writer = writers.pop(identifier)
        writer.abort()
        if runtime is not None:
            runtime.close_resource(writer)
        return None

    def _open(path: str) -> zipfile.ZipFile:
        return zipfile.ZipFile(Path(_string(path, "Path")), "r")

    def list_members(path: str) -> list[str]:
        with _open(path) as archive:
            names = archive.namelist()
            if len(names) > _MAX_ARCHIVE_MEMBERS:
                raise ValueError(
                    f"Archive has more than {_MAX_ARCHIVE_MEMBERS} members."
                )
            return sorted(names)

    def info(path: str) -> list[dict[str, Any]]:
        with _open(path) as archive:
            entries = archive.infolist()
            if len(entries) > _MAX_ARCHIVE_MEMBERS:
                raise ValueError(
                    f"Archive has more than {_MAX_ARCHIVE_MEMBERS} members."
                )
            return sorted(
                (
                    {
                        "name": entry.filename,
                        "size": entry.file_size,
                        "compressed_size": entry.compress_size,
                        "is_dir": entry.is_dir(),
                        "crc": entry.CRC,
                    }
                    for entry in entries
                ),
                key=lambda item: item["name"],
            )

    def read(path: str, member: str) -> bytes:
        name = _safe_archive_name(member)
        with _open(path) as archive:
            try:
                info = archive.getinfo(name)
            except KeyError as error:
                raise StdLibError(
                    "archive",
                    f"Archive has no member '{member}'.",
                    "archive-error",
                ) from error
            if info.is_dir():
                raise StdLibError(
                    "archive",
                    f"Archive member '{member}' is a directory.",
                    "archive-error",
                )
            if info.file_size > _MAX_ARCHIVE_ENTRY:
                raise ValueError(
                    f"Archive member exceeds the {_MAX_ARCHIVE_ENTRY}-byte limit."
                )
            return archive.read(info)

    def read_text(path: str, member: str, encoding: str = "utf-8") -> str:
        try:
            return read(path, member).decode(_string(encoding, "Encoding"), errors="strict")
        except UnicodeDecodeError as error:
            raise ValueError(f"Archive member is not valid text: {error}") from error

    def extract(
        path: str,
        destination: str,
        members: list[str] | None = None,
        overwrite: bool = False,
        max_bytes: int = _MAX_ARCHIVE_BYTES,
    ) -> list[str]:
        root = Path(_string(destination, "Destination"))
        allow_overwrite = _boolean(overwrite, "overwrite")
        limit = _integer(max_bytes, "max_bytes", 1, _MAX_ARCHIVE_BYTES)
        root.mkdir(parents=True, exist_ok=True)
        extracted: list[str] = []
        total = 0
        with _open(path) as archive:
            infos = archive.infolist()
            if len(infos) > _MAX_ARCHIVE_MEMBERS:
                raise ValueError(
                    f"Archive has more than {_MAX_ARCHIVE_MEMBERS} members."
                )
            selected = None if members is None else {
                _safe_archive_name(item) for item in members
            }
            for entry in infos:
                if selected is not None and entry.filename not in selected:
                    continue
                if entry.is_dir():
                    target = _safe_extract_path(root, entry.filename.rstrip("/"))
                    target.mkdir(parents=True, exist_ok=True)
                    continue
                mode = entry.external_attr >> 16
                if stat.S_ISLNK(mode):
                    raise StdLibError(
                        "archive",
                        f"Archive member '{entry.filename}' is a symbolic link.",
                        "archive-error",
                    )
                target = _safe_extract_path(root, entry.filename)
                total += entry.file_size
                if total > limit:
                    raise ValueError(
                        f"Archive extraction exceeds the {limit}-byte limit."
                    )
                if target.exists() and not allow_overwrite:
                    raise FileExistsError(
                        f"Refusing to overwrite '{target}'."
                    )
                target.parent.mkdir(parents=True, exist_ok=True)
                data = archive.read(entry)
                temporary = target.with_name(f".{target.name}.yuba-tmp")
                try:
                    temporary.write_bytes(data)
                    os.replace(temporary, target)
                finally:
                    temporary.unlink(missing_ok=True)
                extracted.append(str(target))
        return sorted(extracted)

    def verify(path: str) -> bool:
        with _open(path) as archive:
            return archive.testzip() is None

    return {
        "create": create,
        "add_bytes": add_bytes,
        "add_text": add_text,
        "add_file": add_file,
        "close": close,
        "abort": abort,
        "list": list_members,
        "info": info,
        "read": read,
        "read_text": read_text,
        "extract": extract,
        "verify": verify,
    }


# ---------------------------------------------------------------------------
# std.sqlite


_MAX_SQL_LENGTH = 1_048_576
_MAX_SQL_ROWS = 100_000
_MAX_SQL_PARAMS = 10_000


class _SQLiteHandle:
    def __init__(self, path: str, connection: sqlite3.Connection) -> None:
        self.path = path
        self.connection = connection
        self.closed = False
        self.in_transaction = False

    def close(self) -> None:
        if self.closed:
            return
        self.closed = True
        try:
            if self.in_transaction:
                self.connection.rollback()
        finally:
            self.connection.close()
            self.in_transaction = False


def _sql_parameters(params: Any) -> Any:
    if params is None:
        return ()
    if isinstance(params, (list, tuple)):
        if len(params) > _MAX_SQL_PARAMS:
            raise ValueError(
                f"SQL parameters exceed the {_MAX_SQL_PARAMS}-value limit."
            )
        values = []
        for value in params:
            if isinstance(value, bool):
                values.append(int(value))
            elif value is None or isinstance(value, (int, float, str, bytes, bytearray)):
                values.append(value)
            else:
                raise TypeError(
                    "SQL parameters must be none, numbers, strings, or bytes."
                )
        return tuple(values)
    if isinstance(params, dict):
        if len(params) > _MAX_SQL_PARAMS:
            raise ValueError(
                f"SQL parameters exceed the {_MAX_SQL_PARAMS}-value limit."
            )
        values = {}
        for key, value in params.items():
            if not isinstance(key, str):
                raise TypeError("SQL parameter names must be strings.")
            if isinstance(value, bool):
                values[key] = int(value)
            elif value is None or isinstance(value, (int, float, str, bytes, bytearray)):
                values[key] = value
            else:
                raise TypeError(
                    "SQL parameters must be none, numbers, strings, or bytes."
                )
        return values
    raise TypeError("SQL parameters must be a list, tuple, dictionary, or none.")


def _sql_text(sql: Any) -> str:
    text = _string(sql, "SQL")
    if not text.strip():
        raise ValueError("SQL must not be empty.")
    if len(text) > _MAX_SQL_LENGTH:
        raise ValueError(f"SQL exceeds the {_MAX_SQL_LENGTH}-character limit.")
    return text


def sqlite_functions(runtime: Any = None) -> dict[str, Callable[..., Any]]:
    handles: dict[int, _SQLiteHandle] = {}
    counter = [0]

    def _handle(value: Any) -> _SQLiteHandle:
        identifier = value.get("id") if isinstance(value, dict) else value
        handle = handles.get(identifier) if isinstance(identifier, int) else None
        if handle is None or handle.closed:
            raise StdLibError(
                "sqlite", "SQLite handle is not open.", "sqlite-error"
            )
        return handle

    def open_database(
        path: str = ":memory:",
        timeout: float = 5.0,
        read_only: bool = False,
    ) -> dict[str, Any]:
        location = _string(path, "Database path")
        duration = _number(timeout, "Timeout")
        if not 0 < duration <= 300:
            raise ValueError("Timeout must be greater than 0 and at most 300 seconds.")
        if _boolean(read_only, "read_only"):
            if location == ":memory:":
                raise ValueError("In-memory databases cannot be read-only.")
            resolved = Path(location).resolve()
            if not resolved.is_file():
                raise ValueError(f"Database '{location}' does not exist.")
            connection = sqlite3.connect(
                f"{resolved.as_uri()}?mode=ro",
                timeout=duration,
                uri=True,
                isolation_level=None,
            )
        else:
            connection = sqlite3.connect(
                location,
                timeout=duration,
                isolation_level=None,
            )
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        handle = _SQLiteHandle(location, connection)
        counter[0] += 1
        identifier = counter[0]
        handles[identifier] = handle
        _register(runtime, handle)
        return {"id": identifier, "path": location}

    def execute(handle_value: Any, sql: str, params: Any = None) -> dict[str, Any]:
        handle = _handle(handle_value)
        cursor = handle.connection.execute(_sql_text(sql), _sql_parameters(params))
        return {"rowcount": cursor.rowcount, "lastrowid": cursor.lastrowid}

    def executemany(handle_value: Any, sql: str, rows: Any) -> dict[str, Any]:
        handle = _handle(handle_value)
        if not isinstance(rows, (list, tuple)):
            raise TypeError("Rows must be a list or tuple of parameter sequences.")
        if len(rows) > _MAX_SQL_PARAMS:
            raise ValueError(f"Rows exceed the {_MAX_SQL_PARAMS}-row limit.")
        cursor = handle.connection.executemany(
            _sql_text(sql), [_sql_parameters(row) for row in rows]
        )
        return {"rowcount": cursor.rowcount}

    def query(
        handle_value: Any,
        sql: str,
        params: Any = None,
        limit: int = 10_000,
    ) -> list[dict[str, Any]]:
        handle = _handle(handle_value)
        maximum = _integer(limit, "limit", 1, _MAX_SQL_ROWS)
        cursor = handle.connection.execute(_sql_text(sql), _sql_parameters(params))
        rows = cursor.fetchmany(maximum + 1)
        if len(rows) > maximum:
            raise StdLibError(
                "sqlite",
                f"SQLite query returned more than the {maximum}-row limit.",
                "sqlite-error",
            )
        return [dict(row) for row in rows]

    def begin(handle_value: Any) -> None:
        handle = _handle(handle_value)
        if handle.in_transaction:
            raise StdLibError(
                "sqlite",
                "A transaction is already active.",
                "sqlite-error",
            )
        handle.connection.execute("BEGIN")
        handle.in_transaction = True

    def commit(handle_value: Any) -> None:
        handle = _handle(handle_value)
        if not handle.in_transaction:
            raise StdLibError(
                "sqlite", "No transaction is active.", "sqlite-error"
            )
        handle.connection.commit()
        handle.in_transaction = False

    def rollback(handle_value: Any) -> None:
        handle = _handle(handle_value)
        if not handle.in_transaction:
            raise StdLibError(
                "sqlite", "No transaction is active.", "sqlite-error"
            )
        handle.connection.rollback()
        handle.in_transaction = False

    def close(handle_value: Any) -> None:
        identifier = (
            handle_value.get("id") if isinstance(handle_value, dict) else handle_value
        )
        if not isinstance(identifier, int) or identifier not in handles:
            return None
        handle = handles.pop(identifier)
        if runtime is not None:
            runtime.close_resource(handle)
        else:
            handle.close()
        return None

    def tables(handle_value: Any) -> list[str]:
        handle = _handle(handle_value)
        cursor = handle.connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' "
            "AND name NOT LIKE 'sqlite_%' ORDER BY name"
        )
        return [row[0] for row in cursor.fetchall()]

    return {
        "open": open_database,
        "execute": execute,
        "executemany": executemany,
        "query": query,
        "begin": begin,
        "commit": commit,
        "rollback": rollback,
        "close": close,
        "tables": tables,
    }


# ---------------------------------------------------------------------------
# std.uuid


def uuid_functions() -> dict[str, Callable[..., Any]]:
    namespaces = {
        "dns": _uuid.NAMESPACE_DNS,
        "url": _uuid.NAMESPACE_URL,
        "oid": _uuid.NAMESPACE_OID,
        "x500": _uuid.NAMESPACE_X500,
    }

    def _namespace(value: Any) -> _uuid.UUID:
        if isinstance(value, dict):
            value = value.get("canonical")
        text = _string(value, "Namespace")
        if text.lower() in namespaces:
            return namespaces[text.lower()]
        try:
            return _uuid.UUID(text)
        except ValueError as error:
            raise ValueError(f"Invalid UUID namespace '{value}'.") from error

    def uuid4() -> str:
        return str(_uuid.uuid4())

    def uuid1(node: int | None = None, clock_seq: int | None = None) -> str:
        node_value = None if node is None else _integer(node, "node", 0, 2**48 - 1)
        clock_value = None if clock_seq is None else _integer(clock_seq, "clock_seq", 0, 2**14 - 1)
        return str(_uuid.uuid1(node=node_value, clock_seq=clock_value))

    def uuid3(namespace: Any, name: str) -> str:
        return str(_uuid.uuid3(_namespace(namespace), _string(name, "Name")))

    def uuid5(namespace: Any, name: str) -> str:
        return str(_uuid.uuid5(_namespace(namespace), _string(name, "Name")))

    def parse(text: str) -> dict[str, Any]:
        try:
            value = _uuid.UUID(_string(text, "UUID"))
        except ValueError as error:
            raise ValueError(f"Invalid UUID '{text}'.") from error
        return {
            "canonical": str(value),
            "hex": value.hex,
            "int": value.int,
            "urn": value.urn,
            "version": value.version,
            "variant": str(value.variant),
        }

    def is_valid(text: str) -> bool:
        try:
            _uuid.UUID(_string(text, "UUID"))
        except ValueError:
            return False
        return True

    def nil() -> str:
        return str(_uuid.UUID(int=0))

    def maximum() -> str:
        return str(_uuid.UUID(int=(1 << 128) - 1))

    return {
        "uuid1": uuid1,
        "uuid3": uuid3,
        "uuid4": uuid4,
        "uuid5": uuid5,
        "parse": parse,
        "is_valid": is_valid,
        "nil": nil,
        "max": maximum,
    }


# ---------------------------------------------------------------------------
# std.decimal


_DECIMAL_ROUNDING = {
    "half_even": _decimal.ROUND_HALF_EVEN,
    "half_up": _decimal.ROUND_HALF_UP,
    "half_down": _decimal.ROUND_HALF_DOWN,
    "up": _decimal.ROUND_UP,
    "down": _decimal.ROUND_DOWN,
    "ceiling": _decimal.ROUND_CEILING,
    "floor": _decimal.ROUND_FLOOR,
    "05up": _decimal.ROUND_05UP,
}


def _decimal_value(value: Any, label: str = "Value") -> _decimal.Decimal:
    if isinstance(value, bool):
        raise TypeError(f"{label} must be a decimal string, integer, or float.")
    if isinstance(value, _decimal.Decimal):
        return value
    if isinstance(value, int):
        return _decimal.Decimal(value)
    if isinstance(value, float):
        return _decimal.Decimal(str(value))
    if isinstance(value, str):
        try:
            return _decimal.Decimal(value.strip())
        except _decimal.InvalidOperation as error:
            raise ValueError(f"{label} is not a valid decimal.") from error
    raise TypeError(f"{label} must be a decimal string, integer, or float.")


def _decimal_precision(value: Any) -> int:
    return _integer(value, "Precision", 1, 10_000)


def _decimal_rounding(value: Any) -> str:
    name = _string(value, "Rounding").lower()
    if name not in _DECIMAL_ROUNDING:
        raise ValueError(
            "Rounding must be one of: " + ", ".join(sorted(_DECIMAL_ROUNDING)) + "."
        )
    return name


def _decimal_operation(
    function: Callable[..., _decimal.Decimal],
    precision: int,
    rounding: str,
    *values: Any,
) -> str:
    try:
        with _decimal.localcontext() as context:
            context.prec = precision
            context.rounding = _DECIMAL_ROUNDING[rounding]
            result = function(*values)
    except (_decimal.InvalidOperation, _decimal.DivisionByZero, _decimal.Overflow) as error:
        raise ValueError(f"Decimal operation failed: {error}") from error
    return str(result)


def decimal_functions() -> dict[str, Callable[..., Any]]:
    def parse(text: Any) -> str:
        return str(_decimal_value(text))

    def add(left: Any, right: Any, precision: int = 28, rounding: str = "half_even") -> str:
        return _decimal_operation(
            lambda a, b: a + b,
            _decimal_precision(precision),
            _decimal_rounding(rounding),
            _decimal_value(left, "Left"),
            _decimal_value(right, "Right"),
        )

    def subtract(left: Any, right: Any, precision: int = 28, rounding: str = "half_even") -> str:
        return _decimal_operation(
            lambda a, b: a - b,
            _decimal_precision(precision),
            _decimal_rounding(rounding),
            _decimal_value(left, "Left"),
            _decimal_value(right, "Right"),
        )

    def multiply(left: Any, right: Any, precision: int = 28, rounding: str = "half_even") -> str:
        return _decimal_operation(
            lambda a, b: a * b,
            _decimal_precision(precision),
            _decimal_rounding(rounding),
            _decimal_value(left, "Left"),
            _decimal_value(right, "Right"),
        )

    def divide(left: Any, right: Any, precision: int = 28, rounding: str = "half_even") -> str:
        return _decimal_operation(
            lambda a, b: a / b,
            _decimal_precision(precision),
            _decimal_rounding(rounding),
            _decimal_value(left, "Left"),
            _decimal_value(right, "Right"),
        )

    def modulo(left: Any, right: Any, precision: int = 28, rounding: str = "half_even") -> str:
        return _decimal_operation(
            lambda a, b: a % b,
            _decimal_precision(precision),
            _decimal_rounding(rounding),
            _decimal_value(left, "Left"),
            _decimal_value(right, "Right"),
        )

    def power(base: Any, exponent: Any, precision: int = 28, rounding: str = "half_even") -> str:
        return _decimal_operation(
            lambda a, b: a ** b,
            _decimal_precision(precision),
            _decimal_rounding(rounding),
            _decimal_value(base, "Base"),
            _decimal_value(exponent, "Exponent"),
        )

    def sqrt(value: Any, precision: int = 28, rounding: str = "half_even") -> str:
        return _decimal_operation(
            lambda item: item.sqrt(),
            _decimal_precision(precision),
            _decimal_rounding(rounding),
            _decimal_value(value),
        )

    def negate(value: Any) -> str:
        return str(-_decimal_value(value))

    def absolute(value: Any) -> str:
        return str(abs(_decimal_value(value)))

    def compare(left: Any, right: Any) -> int:
        first, second = _decimal_value(left, "Left"), _decimal_value(right, "Right")
        return -1 if first < second else (1 if first > second else 0)

    def quantize(value: Any, places: int, rounding: str = "half_even") -> str:
        count = _integer(places, "Places", -1000, 1000)
        name = _decimal_rounding(rounding)
        try:
            with _decimal.localcontext() as context:
                context.rounding = _DECIMAL_ROUNDING[name]
                result = _decimal_value(value).quantize(
                    _decimal.Decimal(1).scaleb(-count)
                )
        except _decimal.InvalidOperation as error:
            raise ValueError(f"Decimal quantize failed: {error}") from error
        return str(result)

    def round_value(value: Any, places: int = 0, rounding: str = "half_even") -> str:
        return quantize(value, places, rounding)

    def to_integer(value: Any, rounding: str = "half_even") -> int:
        name = _decimal_rounding(rounding)
        try:
            with _decimal.localcontext() as context:
                context.rounding = _DECIMAL_ROUNDING[name]
                return int(_decimal_value(value).to_integral_value())
        except _decimal.InvalidOperation as error:
            raise ValueError(f"Decimal conversion failed: {error}") from error

    def is_finite(value: Any) -> bool:
        return _decimal_value(value).is_finite()

    def is_nan(value: Any) -> bool:
        return _decimal_value(value).is_nan()

    def is_zero(value: Any) -> bool:
        return _decimal_value(value).is_zero()

    def sign(value: Any) -> int:
        item = _decimal_value(value)
        if item.is_nan():
            raise ValueError("NaN has no sign.")
        if item == 0:
            return 0
        return -1 if item.is_signed() else 1

    def format_value(value: Any, places: int | None = None) -> str:
        if places is None:
            return str(_decimal_value(value))
        return quantize(value, places)

    return {
        "parse": parse,
        "add": add,
        "subtract": subtract,
        "multiply": multiply,
        "divide": divide,
        "modulo": modulo,
        "power": power,
        "sqrt": sqrt,
        "negate": negate,
        "abs": absolute,
        "compare": compare,
        "quantize": quantize,
        "round": round_value,
        "to_integer": to_integer,
        "is_finite": is_finite,
        "is_nan": is_nan,
        "is_zero": is_zero,
        "sign": sign,
        "format": format_value,
    }


# ---------------------------------------------------------------------------
# std.statistics


def statistics_functions() -> dict[str, Callable[..., Any]]:
    def values(source: Any, label: str = "Values") -> list[float]:
        if not isinstance(source, (list, tuple)):
            raise TypeError(f"{label} must be a list or tuple.")
        result = []
        for item in source:
            if isinstance(item, bool) or not isinstance(item, (int, float)):
                raise TypeError(f"{label} must contain only numbers.")
            number = float(item)
            if number != number or number in (float("inf"), float("-inf")):
                raise ValueError(f"{label} must contain only finite numbers.")
            result.append(number)
        if not result:
            raise ValueError(f"{label} must not be empty.")
        return result

    def mean(source: Any) -> float:
        return _statistics.mean(values(source))

    def fmean(source: Any) -> float:
        return _statistics.fmean(values(source))

    def median(source: Any) -> float:
        return _statistics.median(values(source))

    def median_low(source: Any) -> float:
        return _statistics.median_low(values(source))

    def median_high(source: Any) -> float:
        return _statistics.median_high(values(source))

    def mode(source: Any) -> float:
        return _statistics.mode(values(source))

    def multimode(source: Any) -> list[float]:
        return _statistics.multimode(values(source))

    def stdev(source: Any) -> float:
        return _statistics.stdev(values(source))

    def variance(source: Any) -> float:
        return _statistics.variance(values(source))

    def pstdev(source: Any) -> float:
        return _statistics.pstdev(values(source))

    def pvariance(source: Any) -> float:
        return _statistics.pvariance(values(source))

    def correlation(left: Any, right: Any) -> float:
        first, second = values(left, "Left values"), values(right, "Right values")
        if len(first) != len(second):
            raise ValueError("Correlation requires equal-length collections.")
        return _statistics.correlation(first, second)

    def linear_regression(x: Any, y: Any) -> dict[str, float]:
        first, second = values(x, "X values"), values(y, "Y values")
        if len(first) != len(second):
            raise ValueError("Regression requires equal-length collections.")
        slope, intercept = _statistics.linear_regression(first, second)
        return {"slope": slope, "intercept": intercept}

    def percentile(source: Any, point: float) -> float:
        data = sorted(values(source))
        position = _number(point, "Percentile")
        if not 0 <= position <= 100:
            raise ValueError("Percentile must be between 0 and 100.")
        if len(data) == 1:
            return data[0]
        rank = (len(data) - 1) * position / 100.0
        lower = int(rank)
        upper = min(lower + 1, len(data) - 1)
        fraction = rank - lower
        return data[lower] + (data[upper] - data[lower]) * fraction

    def quantiles(source: Any, n: int = 4, method: str = "exclusive") -> list[float]:
        count = _integer(n, "n", 1, 1000)
        name = _string(method, "method").lower()
        if name not in ("exclusive", "inclusive"):
            raise ValueError("method must be 'exclusive' or 'inclusive'.")
        return _statistics.quantiles(values(source), n=count, method=name)

    def summary(source: Any) -> dict[str, Any]:
        data = values(source)
        return {
            "count": len(data),
            "minimum": min(data),
            "maximum": max(data),
            "mean": _statistics.fmean(data),
            "median": _statistics.median(data),
            "stdev": _statistics.stdev(data) if len(data) > 1 else 0.0,
        }

    return {
        "mean": mean,
        "fmean": fmean,
        "median": median,
        "median_low": median_low,
        "median_high": median_high,
        "mode": mode,
        "multimode": multimode,
        "stdev": stdev,
        "variance": variance,
        "pstdev": pstdev,
        "pvariance": pvariance,
        "correlation": correlation,
        "linear_regression": linear_regression,
        "percentile": percentile,
        "quantiles": quantiles,
        "summary": summary,
    }


# ---------------------------------------------------------------------------
# std.logging


_LOG_LEVELS = {"debug": 10, "info": 20, "warning": 30, "error": 40, "critical": 50}


class _LogFile:
    def __init__(self, path: Path, level: int) -> None:
        self.path = path
        self.level = level
        self.closed = False
        path.parent.mkdir(parents=True, exist_ok=True)
        self.stream = path.open("a", encoding="utf-8", newline="")

    def write(self, line: str) -> None:
        if self.closed:
            return
        self.stream.write(line)
        self.stream.flush()

    def close(self) -> None:
        if self.closed:
            return
        self.closed = True
        self.stream.close()


def logging_functions(runtime: Any = None) -> dict[str, Callable[..., Any]]:
    state: dict[str, Any] = {
        "level": "info",
        "destination": "stderr",
        "timestamps": True,
    }
    files: dict[int, _LogFile] = {}
    counter = [0]
    lock = threading.Lock()

    def _level(value: Any) -> int:
        name = _string(value, "Log level").lower()
        if name not in _LOG_LEVELS:
            raise ValueError(
                "Log level must be one of: " + ", ".join(_LOG_LEVELS) + "."
            )
        return _LOG_LEVELS[name]

    def configure(
        level: str = "info",
        destination: str = "stderr",
        timestamps: bool = True,
    ) -> dict[str, Any]:
        state["level"] = _string(level, "Log level").lower()
        if state["level"] not in _LOG_LEVELS:
            raise ValueError("Invalid log level.")
        target = _string(destination, "Destination").lower()
        if target not in ("stdout", "stderr", "none"):
            raise ValueError("Log destination must be 'stdout', 'stderr', or 'none'.")
        state["destination"] = target
        state["timestamps"] = _boolean(timestamps, "timestamps")
        return dict(state)

    def set_level(level: str) -> None:
        state["level"] = _string(level, "Log level").lower()
        if state["level"] not in _LOG_LEVELS:
            raise ValueError("Invalid log level.")

    def get_level() -> str:
        return state["level"]

    def _emit(level: str, message: str) -> None:
        numeric = _LOG_LEVELS[level]
        if numeric < _LOG_LEVELS[state["level"]]:
            return
        text = _string(message, "Message")
        if state["timestamps"]:
            stamp = time.strftime(
                "%Y-%m-%dT%H:%M:%SZ", time.gmtime(runtime.clock() if runtime else time.time())
            )
            line = f"{stamp} {level.upper()} {text}\n"
        else:
            line = f"{level.upper()} {text}\n"
        with lock:
            for handler in files.values():
                if numeric >= handler.level:
                    handler.write(line)
            destination = state["destination"]
            if destination == "stdout":
                sys.stdout.write(line)
                sys.stdout.flush()
            elif destination == "stderr":
                sys.stderr.write(line)
                sys.stderr.flush()

    def log(level: str, message: str) -> None:
        name = _string(level, "Log level").lower()
        if name not in _LOG_LEVELS:
            raise ValueError("Invalid log level.")
        _emit(name, message)

    def debug(message: str) -> None:
        _emit("debug", message)

    def info(message: str) -> None:
        _emit("info", message)

    def warning(message: str) -> None:
        _emit("warning", message)

    def error(message: str) -> None:
        _emit("error", message)

    def critical(message: str) -> None:
        _emit("critical", message)

    def add_file(path: str, level: str = "info", append: bool = True) -> dict[str, Any]:
        target = Path(_string(path, "Path"))
        numeric = _level(level)
        if target.exists() and not _boolean(append, "append"):
            target.unlink()
        handler = _LogFile(target, numeric)
        counter[0] += 1
        identifier = counter[0]
        files[identifier] = handler
        _register(runtime, handler)
        return {"id": identifier, "path": str(target)}

    def remove_file(handle: Any) -> None:
        identifier = handle.get("id") if isinstance(handle, dict) else handle
        handler = files.pop(identifier, None) if isinstance(identifier, int) else None
        if handler is None:
            raise ValueError("Log file handle is not open.")
        if runtime is not None:
            runtime.close_resource(handler)
        else:
            handler.close()

    def flush() -> None:
        for handler in files.values():
            handler.stream.flush()
        sys.stdout.flush()
        sys.stderr.flush()

    return {
        "configure": configure,
        "set_level": set_level,
        "get_level": get_level,
        "log": log,
        "debug": debug,
        "info": info,
        "warning": warning,
        "error": error,
        "critical": critical,
        "add_file": add_file,
        "remove_file": remove_file,
        "flush": flush,
    }


# ---------------------------------------------------------------------------
# std.terminal


_COLOR_NAMES = {
    "black": 30, "red": 31, "green": 32, "yellow": 33,
    "blue": 34, "magenta": 35, "cyan": 36, "white": 37,
    "default": 39, "bright_black": 90, "bright_red": 91,
    "bright_green": 92, "bright_yellow": 93, "bright_blue": 94,
    "bright_magenta": 95, "bright_cyan": 96, "bright_white": 97,
}
_BACKGROUND_NAMES = {
    "black": 40, "red": 41, "green": 42, "yellow": 43,
    "blue": 44, "magenta": 45, "cyan": 46, "white": 47,
    "default": 49, "bright_black": 100, "bright_red": 101,
    "bright_green": 102, "bright_yellow": 103, "bright_blue": 104,
    "bright_magenta": 105, "bright_cyan": 106, "bright_white": 107,
}
_ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")


def _terminal_stream(name: str) -> Any:
    target = _string(name, "Stream").lower()
    if target == "stdout":
        return sys.stdout
    if target == "stderr":
        return sys.stderr
    if target == "stdin":
        return sys.stdin
    raise ValueError("Stream must be 'stdin', 'stdout', or 'stderr'.")


def terminal_functions() -> dict[str, Callable[..., Any]]:
    def is_tty(stream: str = "stdout") -> bool:
        return bool(_terminal_stream(stream).isatty())

    def size() -> dict[str, int]:
        columns, lines = shutil.get_terminal_size(fallback=(80, 24))
        return {"columns": columns, "rows": lines}

    def supports_color() -> bool:
        if os.environ.get("NO_COLOR"):
            return False
        if os.environ.get("TERM", "").lower() == "dumb":
            return False
        return bool(sys.stdout.isatty())

    def _color_code(value: Any, background: bool) -> str:
        if isinstance(value, int) and not isinstance(value, bool):
            if not 0 <= value <= 255:
                raise ValueError("Color numbers must be between 0 and 255.")
            return f"{48 if background else 38};5;{value}"
        name = _string(value, "Color").lower()
        table = _BACKGROUND_NAMES if background else _COLOR_NAMES
        if name not in table:
            raise ValueError(f"Unknown color '{value}'.")
        return str(table[name])

    def style(
        text: str,
        fg: Any = None,
        bg: Any = None,
        bold: bool = False,
        underline: bool = False,
        dim: bool = False,
    ) -> str:
        value = _string(text, "Text")
        codes = []
        if _boolean(bold, "bold"):
            codes.append("1")
        if _boolean(dim, "dim"):
            codes.append("2")
        if _boolean(underline, "underline"):
            codes.append("4")
        if fg is not None:
            codes.append(_color_code(fg, background=False))
        if bg is not None:
            codes.append(_color_code(bg, background=True))
        if not codes:
            return value
        return f"\x1b[{';'.join(codes)}m{value}\x1b[0m"

    def strip_ansi(text: str) -> str:
        return _ANSI.sub("", _string(text, "Text"))

    def reset() -> str:
        return "\x1b[0m"

    def clear() -> str:
        return "\x1b[2J\x1b[H"

    def move(row: int, column: int) -> str:
        return f"\x1b[{_integer(row, 'row', 1)};{_integer(column, 'column', 1)}H"

    def hide_cursor() -> str:
        return "\x1b[?25l"

    def show_cursor() -> str:
        return "\x1b[?25h"

    return {
        "is_tty": is_tty,
        "size": size,
        "supports_color": supports_color,
        "style": style,
        "strip_ansi": strip_ansi,
        "reset": reset,
        "clear": clear,
        "move": move,
        "hide_cursor": hide_cursor,
        "show_cursor": show_cursor,
    }


# ---------------------------------------------------------------------------
# std.env


def env_functions(program_args: list[str]) -> dict[str, Callable[..., Any]]:
    def _name(value: Any) -> str:
        name = _string(value, "Environment variable name")
        if not name or "=" in name or "\x00" in name:
            raise ValueError("Environment variable names must be non-empty and contain no '=' or NUL.")
        return name

    def get(name: str, default: Any = None) -> Any:
        return os.environ.get(_name(name), default)

    def has(name: str) -> bool:
        return _name(name) in os.environ

    def set_value(name: str, value: str) -> None:
        os.environ[_name(name)] = _string(value, "Environment variable value")

    def unset(name: str) -> bool:
        key = _name(name)
        if key in os.environ:
            del os.environ[key]
            return True
        return False

    def all_values() -> dict[str, str]:
        return dict(os.environ)

    def args() -> list[str]:
        return list(program_args)

    def cwd() -> str:
        return os.getcwd()

    def chdir(path: str) -> None:
        os.chdir(_string(path, "Path"))

    def home() -> str:
        return str(Path.home())

    def temp_dir() -> str:
        return _tempfile.gettempdir()

    def platform() -> str:
        return sys.platform

    def executable() -> str:
        return sys.executable

    def pid() -> int:
        return os.getpid()

    def separator() -> str:
        return os.sep

    def path_separator() -> str:
        return os.pathsep

    def expand_vars(text: str) -> str:
        return os.path.expandvars(_string(text, "Text"))

    def expand_user(path: str) -> str:
        return os.path.expanduser(_string(path, "Path"))

    return {
        "get": get,
        "has": has,
        "set": set_value,
        "unset": unset,
        "all": all_values,
        "args": args,
        "cwd": cwd,
        "chdir": chdir,
        "home": home,
        "temp_dir": temp_dir,
        "platform": platform,
        "executable": executable,
        "pid": pid,
        "separator": separator,
        "path_separator": path_separator,
        "expand_vars": expand_vars,
        "expand_user": expand_user,
    }


# ---------------------------------------------------------------------------
# std.io


def io_functions() -> dict[str, Callable[..., Any]]:
    def _stream(name: str) -> tuple[Any, Any]:
        target = _string(name, "Stream").lower()
        if target == "stdout":
            return sys.stdout, getattr(sys.stdout, "buffer", None)
        if target == "stderr":
            return sys.stderr, getattr(sys.stderr, "buffer", None)
        if target == "stdin":
            return sys.stdin, getattr(sys.stdin, "buffer", None)
        raise ValueError("Stream must be 'stdin', 'stdout', or 'stderr'.")

    def write(
        value: Any,
        stream: str = "stdout",
        newline: bool = False,
        flush: bool = False,
    ) -> None:
        text_stream, binary_stream = _stream(stream)
        suffix = "\n" if _boolean(newline, "newline") else ""
        if isinstance(value, str):
            text_stream.write(value + suffix)
            target = text_stream
        elif isinstance(value, (bytes, bytearray)):
            if binary_stream is None:
                raise ValueError("This stream does not expose a binary buffer.")
            binary_stream.write(bytes(value))
            if suffix:
                binary_stream.write(suffix.encode("utf-8"))
            target = binary_stream
        else:
            raise TypeError("Stream values must be strings, bytes, or bytearray.")
        if _boolean(flush, "flush"):
            target.flush()

    def writeline(value: Any, stream: str = "stdout") -> None:
        write(value, stream, newline=True)

    def read(count: int = -1, stream: str = "stdin") -> bytes:
        size = _integer(count, "count", -1)
        _, binary_stream = _stream(stream)
        if stream.lower() != "stdin":
            raise ValueError("Only the standard input stream can be read.")
        if binary_stream is None:
            raise ValueError("This stream does not expose a binary buffer.")
        return binary_stream.read(size)

    def readline(stream: str = "stdin") -> str:
        text_stream, _ = _stream(stream)
        if stream.lower() != "stdin":
            raise ValueError("Only the standard input stream can be read.")
        return text_stream.readline()

    def flush(stream: str = "stdout") -> None:
        text_stream, binary_stream = _stream(stream)
        for candidate in (text_stream, binary_stream):
            if candidate is not None:
                candidate.flush()

    def is_tty(stream: str = "stdout") -> bool:
        return bool(_terminal_stream(stream).isatty())

    def encoding(stream: str = "stdout") -> str:
        return _terminal_stream(stream).encoding or "utf-8"

    return {
        "write": write,
        "writeline": writeline,
        "read": read,
        "readline": readline,
        "flush": flush,
        "is_tty": is_tty,
        "encoding": encoding,
    }
