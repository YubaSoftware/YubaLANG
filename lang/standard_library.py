"""Bundled standard-library modules exposed through the language importer."""

import base64
import binascii
import collections as _collections
import csv
import datetime as datetime_module
import hashlib
import io
import json
import math
import os
import random
import re
import sqlite3
import subprocess
import sys as _sys
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Callable


STANDARD_MODULES = frozenset(
    {
        "std.path",
        "std.fs",
        "std.time",
        "std.random",
        "std.math",
        "std.json",
        "std.encoding",
        "std.process",
        "std.http",
        "std.csv",
        "std.url",
        "std.hash",
        "std.pathlib",
        "std.re",
        "std.os",
        "std.statistics",
        "std.sqlite",
        "std.collections",
        "std.sys",
        "math",
        "random",
        "datetime",
        "json",
        "pathlib",
        "re",
        "os",
        "hashlib",
        "base64",
        "subprocess",
        "statistics",
        "sqlite",
        "collections",
        "sys",
    }
)
STANDARD_MODULE_ALIASES = {
    "math": "math",
    "random": "random",
    "datetime": "datetime",
    "json": "json",
    "pathlib": "pathlib",
    "re": "re",
    "os": "os",
    "hashlib": "hashlib",
    "base64": "base64",
    "subprocess": "subprocess",
    "csv": "csv",
    "statistics": "statistics",
    "sqlite": "sqlite",
    "collections": "collections",
    "sys": "sys",
}


def is_standard_module(name: str) -> bool:
    return name in STANDARD_MODULES or name in STANDARD_MODULE_ALIASES


def _string(value: Any, label: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{label} must be a string.")
    return value


def _finite_number(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{label} must be a number.")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{label} must be finite.")
    return result


def _number(value: Any, label: str) -> int | float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{label} must be a number.")
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError(f"{label} must be finite.")
    return value


def _positive_integer(value: Any, label: str, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{label} must be an integer.")
    if not 1 <= value <= maximum:
        raise ValueError(f"{label} must be between 1 and {maximum}.")
    return value


def _path_functions() -> dict[str, Callable[..., Any]]:
    def join(*parts: str) -> str:
        if not parts:
            raise TypeError("join() requires at least one path.")
        return str(Path(_string(parts[0], "Path")).joinpath(
            *(_string(part, "Path") for part in parts[1:])
        ))

    def normalize(path: str) -> str:
        return os.path.normpath(_string(path, "Path"))

    def basename(path: str) -> str:
        return Path(_string(path, "Path")).name

    def dirname(path: str) -> str:
        return str(Path(_string(path, "Path")).parent)

    def extension(path: str) -> str:
        return Path(_string(path, "Path")).suffix

    def is_absolute(path: str) -> bool:
        return Path(_string(path, "Path")).is_absolute()

    def resolve(path: str) -> str:
        return str(Path(_string(path, "Path")).resolve())

    def relative(path: str, base: str) -> str:
        return os.path.relpath(
            _string(path, "Path"), _string(base, "Base path")
        )

    return {
        "join": join,
        "normalize": normalize,
        "basename": basename,
        "dirname": dirname,
        "extension": extension,
        "is_absolute": is_absolute,
        "resolve": resolve,
        "relative": relative,
    }


def _filesystem_functions() -> dict[str, Callable[..., Any]]:
    def read_text(path: str) -> str:
        return Path(_string(path, "Path")).read_text(encoding="utf-8")

    def write_data(target: Path, data: bytes, overwrite: bool) -> None:
        if not isinstance(overwrite, bool):
            raise TypeError("overwrite must be a boolean.")
        if not overwrite:
            descriptor = os.open(
                target,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0),
                0o666,
            )
            try:
                with os.fdopen(descriptor, "wb") as output:
                    output.write(data)
            except BaseException:
                target.unlink(missing_ok=True)
                raise
            return None

        temporary_path: str | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="wb", dir=target.parent, delete=False
            ) as output:
                temporary_path = output.name
                output.write(data)
                output.flush()
                os.fsync(output.fileno())
            os.replace(temporary_path, target)
            temporary_path = None
        finally:
            if temporary_path is not None:
                Path(temporary_path).unlink(missing_ok=True)
        return None

    def read_bytes(path: str) -> bytes:
        return Path(_string(path, "Path")).read_bytes()

    def write_text(path: str, contents: str, overwrite: bool = False) -> None:
        target = Path(_string(path, "Path"))
        data = _string(contents, "Contents").encode("utf-8")
        return write_data(target, data, overwrite)

    def write_bytes(
        path: str,
        contents: bytes | bytearray,
        overwrite: bool = False,
    ) -> None:
        if not isinstance(contents, (bytes, bytearray)):
            raise TypeError("Contents must be bytes or bytearray.")
        return write_data(
            Path(_string(path, "Path")),
            bytes(contents),
            overwrite,
        )

    def exists(path: str) -> bool:
        return Path(_string(path, "Path")).exists()

    def is_file(path: str) -> bool:
        return Path(_string(path, "Path")).is_file()

    def list_dir(path: str) -> list[str]:
        return sorted(
            item.name for item in Path(_string(path, "Path")).iterdir()
        )

    def mkdir(path: str, parents: bool = False, exist_ok: bool = False) -> None:
        if not isinstance(parents, bool) or not isinstance(exist_ok, bool):
            raise TypeError("parents and exist_ok must be booleans.")
        Path(_string(path, "Path")).mkdir(
            parents=parents, exist_ok=exist_ok
        )
        return None

    def remove_file(path: str) -> None:
        Path(_string(path, "Path")).unlink()
        return None

    return {
        "read_text": read_text,
        "write_text": write_text,
        "read_bytes": read_bytes,
        "write_bytes": write_bytes,
        "exists": exists,
        "is_file": is_file,
        "list_dir": list_dir,
        "mkdir": mkdir,
        "remove_file": remove_file,
    }


def _time_functions(clock: Callable[[], float]) -> dict[str, Callable[..., Any]]:
    def now() -> float:
        return clock()

    def utc_iso(timestamp: int | float) -> str:
        moment = datetime_module.datetime.fromtimestamp(
            _finite_number(timestamp, "Timestamp"),
            tz=datetime_module.timezone.utc,
        )
        return moment.isoformat().replace("+00:00", "Z")

    def parse_iso(value: str) -> float:
        text = _string(value, "ISO timestamp")
        if not text.endswith("Z") and "+" not in text[10:] and "-" not in text[10:]:
            raise ValueError("ISO timestamp must include a UTC offset.")
        moment = datetime_module.datetime.fromisoformat(
            text[:-1] + "+00:00" if text.endswith("Z") else text
        )
        if moment.tzinfo is None:
            raise ValueError("ISO timestamp must include a UTC offset.")
        return moment.timestamp()

    def sleep(seconds: int | float) -> None:
        duration = _finite_number(seconds, "Duration")
        if duration < 0:
            raise ValueError("Duration must not be negative.")
        time.sleep(duration)
        return None

    return {"now": now, "utc_iso": utc_iso, "parse_iso": parse_iso, "sleep": sleep}


def _random_functions(source: random.Random) -> dict[str, Callable[..., Any]]:
    def seed(value: int) -> None:
        if isinstance(value, bool) or not isinstance(value, int):
            raise TypeError("Seed must be an integer.")
        source.seed(value)
        return None

    def integer(minimum: int, maximum: int) -> int:
        for value, label in ((minimum, "Minimum"), (maximum, "Maximum")):
            if isinstance(value, bool) or not isinstance(value, int):
                raise TypeError(f"{label} must be an integer.")
        if minimum > maximum:
            raise ValueError("Minimum must not exceed maximum.")
        return source.randint(minimum, maximum)

    def uniform(minimum: int | float, maximum: int | float) -> float:
        low = _finite_number(minimum, "Minimum")
        high = _finite_number(maximum, "Maximum")
        if low > high:
            raise ValueError("Minimum must not exceed maximum.")
        return source.uniform(low, high)

    def choice(values: list[Any]) -> Any:
        if not isinstance(values, (list, tuple, str)) or not values:
            raise ValueError("choice() requires a non-empty list, tuple, or string.")
        return source.choice(values)

    def random() -> float:
        return source.random()

    def randint(start: int, stop: int) -> int:
        if isinstance(start, bool) or not isinstance(start, int):
            raise TypeError("Start must be an integer.")
        if isinstance(stop, bool) or not isinstance(stop, int):
            raise TypeError("Stop must be an integer.")
        if start > stop:
            raise ValueError("Start must not exceed stop.")
        return source.randint(start, stop)

    def shuffle(values: list[Any]) -> list[Any]:
        if not isinstance(values, list):
            raise TypeError("shuffle() requires a list.")
        source.shuffle(values)
        return values

    def sample(values: list[Any], count: int) -> list[Any]:
        if not isinstance(values, list):
            raise TypeError("sample() requires a list.")
        if isinstance(count, bool) or not isinstance(count, int):
            raise TypeError("Count must be an integer.")
        if not 0 <= count <= len(values):
            raise ValueError("Sample count is out of range.")
        return source.sample(values, count)

    return {
        "seed": seed,
        "integer": integer,
        "uniform": uniform,
        "choice": choice,
        "random": random,
        "randint": randint,
        "shuffle": shuffle,
        "sample": sample,
    }


def _math_functions() -> dict[str, Callable[..., Any]]:
    def numeric(function: Callable[[int | float], Any]) -> Callable[[Any], Any]:
        def apply(value: Any) -> Any:
            return function(_number(value, "Argument"))
        return apply

    def power(base: Any, exponent: Any) -> float:
        return math.pow(
            _number(base, "Base"),
            _number(exponent, "Exponent"),
        )

    def is_finite(value: Any) -> bool:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError("Argument must be a number.")
        return math.isfinite(value)

    def tan(value: Any) -> float:
        return math.tan(_number(value, "Argument"))

    def log(value: Any, base: Any | None = None) -> float:
        number = _number(value, "Argument")
        if base is None:
            return math.log(number)
        base_value = _number(base, "Base")
        if base_value <= 0 or base_value == 1:
            raise ValueError("Log base must be > 0 and not equal to 1.")
        return math.log(number, base_value)

    def log10(value: Any) -> float:
        return math.log10(_number(value, "Argument"))

    return {
        "abs": numeric(abs),
        "ceil": numeric(math.ceil),
        "floor": numeric(math.floor),
        "sqrt": numeric(math.sqrt),
        "pow": power,
        "sin": numeric(math.sin),
        "cos": numeric(math.cos),
        "tan": tan,
        "is_finite": is_finite,
        "log": log,
        "log10": log10,
        "pi": lambda: math.pi,
        "e": lambda: math.e,
        "tau": lambda: math.tau,
    }


def _json_functions() -> dict[str, Callable[..., Any]]:
    def reject_constant(value: str) -> None:
        raise ValueError(f"Invalid JSON numeric constant '{value}'.")

    def loads(value: str) -> Any:
        return json.loads(
            _string(value, "JSON input"),
            parse_constant=reject_constant,
        )

    def dumps(value: Any, indent: int | None = None, sort_keys: bool = False) -> str:
        if indent is not None and (
            isinstance(indent, bool) or not isinstance(indent, int) or indent < 0
        ):
            raise ValueError("indent must be none or a non-negative integer.")
        if not isinstance(sort_keys, bool):
            raise TypeError("sort_keys must be a boolean.")
        return json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            indent=indent,
            sort_keys=sort_keys,
        )

    def load(path: str) -> Any:
        with Path(_string(path, "Path")).open("r", encoding="utf-8") as source:
            return json.load(source, parse_constant=reject_constant)

    def dump(value: Any, path: str, indent: int | None = None, sort_keys: bool = False) -> None:
        target = Path(_string(path, "Path"))
        with target.open("w", encoding="utf-8") as output:
            json.dump(
                value,
                output,
                ensure_ascii=False,
                allow_nan=False,
                indent=indent,
                sort_keys=sort_keys,
            )
        return None

    return {"loads": loads, "dumps": dumps, "load": load, "dump": dump}


def _encoding_functions() -> dict[str, Callable[..., Any]]:
    def utf8_encode(value: str) -> bytes:
        return _string(value, "Text").encode("utf-8")

    def utf8_decode(value: bytes | bytearray) -> str:
        if not isinstance(value, (bytes, bytearray)):
            raise TypeError("UTF-8 input must be bytes or bytearray.")
        return bytes(value).decode("utf-8", errors="strict")

    def base64_encode(value: bytes | bytearray) -> str:
        if not isinstance(value, (bytes, bytearray)):
            raise TypeError("Base64 input must be bytes or bytearray.")
        return base64.b64encode(bytes(value)).decode("ascii")

    def base64_decode(value: str) -> bytes:
        try:
            return base64.b64decode(
                _string(value, "Base64 input"), validate=True
            )
        except binascii.Error as error:
            raise ValueError(f"Invalid base64 input: {error}") from error

    return {
        "utf8_encode": utf8_encode,
        "utf8_decode": utf8_decode,
        "base64_encode": base64_encode,
        "base64_decode": base64_decode,
    }


def _csv_functions() -> dict[str, Callable[..., Any]]:
    def loads(value: str, delimiter: str = ",") -> list[list[str]]:
        text = _string(value, "CSV input")
        separator = _string(delimiter, "Delimiter")
        if len(separator) != 1 or separator in "\r\n":
            raise ValueError("CSV delimiter must be one non-newline character.")
        return [
            row
            for row in csv.reader(
                io.StringIO(text, newline=""),
                delimiter=separator,
                strict=True,
            )
        ]

    def dumps(rows: list[list[str]], delimiter: str = ",") -> str:
        separator = _string(delimiter, "Delimiter")
        if len(separator) != 1 or separator in "\r\n":
            raise ValueError("CSV delimiter must be one non-newline character.")
        if not isinstance(rows, (list, tuple)):
            raise TypeError("CSV rows must be a list or tuple of rows.")
        stream = io.StringIO(newline="")
        writer = csv.writer(stream, delimiter=separator, lineterminator="\n")
        for row in rows:
            if not isinstance(row, (list, tuple)) or any(
                not isinstance(cell, str) for cell in row
            ):
                raise TypeError("Each CSV row must be a list or tuple of strings.")
            writer.writerow(row)
        return stream.getvalue()

    return {"loads": loads, "dumps": dumps}


def _url_functions() -> dict[str, Callable[..., Any]]:
    def parse(value: str) -> dict[str, Any]:
        parsed = urllib.parse.urlsplit(_string(value, "URL"))
        try:
            port = parsed.port
        except ValueError as error:
            raise ValueError(f"Invalid URL port: {error}") from error
        return {
            "scheme": parsed.scheme,
            "host": parsed.hostname,
            "port": port,
            "path": parsed.path,
            "query": parsed.query,
            "fragment": parsed.fragment,
            "username": parsed.username,
            "is_absolute": bool(parsed.scheme and parsed.netloc),
        }

    def join(base: str, reference: str) -> str:
        return urllib.parse.urljoin(
            _string(base, "Base URL"),
            _string(reference, "URL reference"),
        )

    def encode_component(value: str) -> str:
        return urllib.parse.quote(_string(value, "URL component"), safe="")

    def decode_component(value: str) -> str:
        try:
            return urllib.parse.unquote(
                _string(value, "URL component"),
                encoding="utf-8",
                errors="strict",
            )
        except UnicodeDecodeError as error:
            raise ValueError(f"URL component is not valid UTF-8: {error}") from error

    def parse_query(value: str) -> dict[str, list[str]]:
        pairs = urllib.parse.parse_qsl(
            _string(value, "Query string"),
            keep_blank_values=True,
            strict_parsing=False,
            encoding="utf-8",
            errors="strict",
        )
        result: dict[str, list[str]] = {}
        for key, item in pairs:
            result.setdefault(key, []).append(item)
        return result

    def build_query(values: dict[str, Any]) -> str:
        if not isinstance(values, dict):
            raise TypeError("Query parameters must be a dictionary.")
        normalized: dict[str, str | list[str]] = {}
        for key, value in values.items():
            if not isinstance(key, str):
                raise TypeError("Query parameter names must be strings.")
            if isinstance(value, str):
                normalized[key] = value
            elif isinstance(value, (list, tuple)) and all(
                isinstance(item, str) for item in value
            ):
                normalized[key] = list(value)
            else:
                raise TypeError(
                    "Query parameter values must be strings or lists of strings."
                )
        return urllib.parse.urlencode(normalized, doseq=True)

    return {
        "parse": parse,
        "join": join,
        "encode_component": encode_component,
        "decode_component": decode_component,
        "parse_query": parse_query,
        "build_query": build_query,
    }


def _hash_functions() -> dict[str, Callable[..., Any]]:
    def sha256(value: str | bytes | bytearray) -> str:
        if isinstance(value, str):
            data = value.encode("utf-8")
        elif isinstance(value, (bytes, bytearray)):
            data = bytes(value)
        else:
            raise TypeError("Hash input must be a string, bytes, or bytearray.")
        return hashlib.sha256(data).hexdigest()

    def sha256_file(path: str) -> str:
        digest = hashlib.sha256()
        try:
            with Path(_string(path, "Path")).open("rb") as source:
                for chunk in iter(lambda: source.read(1024 * 1024), b""):
                    digest.update(chunk)
        except OSError as error:
            raise OSError(f"Cannot hash file '{path}': {error}") from error
        return digest.hexdigest()

    return {"sha256": sha256, "sha256_file": sha256_file}


def _collections_functions() -> dict[str, Callable[..., Any]]:
    def counter(values: Any) -> Any:
        return _collections.Counter(values)

    def deque(values: Any = None, maxlen: int | None = None) -> Any:
        if values is None:
            values = ()
        if maxlen is not None and (isinstance(maxlen, bool) or not isinstance(maxlen, int)):
            raise TypeError("maxlen must be an integer or None.")
        return _collections.deque(values, maxlen=maxlen)

    def defaultdict(default_factory: Any = None) -> Any:
        if default_factory is None:
            return _collections.defaultdict()
        return _collections.defaultdict(default_factory)

    return {"Counter": counter, "deque": deque, "defaultdict": defaultdict}


def _sqlite_functions() -> dict[str, Callable[..., Any]]:
    def connect(path: str, **kwargs: Any) -> sqlite3.Connection:
        return sqlite3.connect(_string(path, "Database path"), **kwargs)

    return {"connect": connect}


def _datetime_functions() -> dict[str, Callable[..., Any]]:
    def now() -> float:
        return time.time()

    def today() -> str:
        return datetime_module.date.today().isoformat()

    def timestamp() -> float:
        return time.time()

    def format_date(value: Any, pattern: str = "%Y-%m-%d %H:%M:%S") -> str:
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            moment = datetime_module.datetime.fromtimestamp(float(value), tz=datetime_module.timezone.utc)
        elif isinstance(value, str):
            text = _string(value, "Date")
            try:
                moment = datetime_module.datetime.fromisoformat(text)
            except ValueError as error:
                raise ValueError(f"Date '{value}' is not ISO-8601 parseable.") from error
        else:
            raise TypeError("Date value must be an ISO-8601 string or Unix timestamp.")
        return moment.strftime(_string(pattern, "Date format"))

    def parse_date(value: str) -> str:
        text = _string(value, "Date")
        try:
            return datetime_module.datetime.fromisoformat(text).isoformat()
        except ValueError as error:
            raise ValueError(f"Date '{value}' is not ISO-8601 parseable.") from error

    return {
        "now": now,
        "today": today,
        "timestamp": timestamp,
        "format_date": format_date,
        "parse_date": parse_date,
    }


def _pathlib_functions() -> dict[str, Callable[..., Any]]:
    fs = _filesystem_functions()
    path = _path_functions()

    def exists(path_value: str) -> bool:
        return fs["exists"](_string(path_value, "Path"))

    def is_file(path_value: str) -> bool:
        return fs["is_file"](_string(path_value, "Path"))

    def is_dir(path_value: str) -> bool:
        return Path(_string(path_value, "Path")).is_dir()

    def mkdir(path_value: str, parents: bool = False, exist_ok: bool = False) -> None:
        return fs["mkdir"](_string(path_value, "Path"), parents, exist_ok)

    def listdir(path_value: str) -> list[str]:
        return fs["list_dir"](_string(path_value, "Path"))

    def basename(path_value: str) -> str:
        return path["basename"](_string(path_value, "Path"))

    def extension(path_value: str) -> str:
        return path["extension"](_string(path_value, "Path"))

    return {
        "exists": exists,
        "is_file": is_file,
        "is_dir": is_dir,
        "mkdir": mkdir,
        "listdir": listdir,
        "basename": basename,
        "extension": extension,
    }


def _re_functions() -> dict[str, Callable[..., Any]]:
    def search(pattern: str, text: str) -> dict[str, Any] | None:
        match = re.search(_string(pattern, "Pattern"), _string(text, "Text"))
        if match is None:
            return None
        return {"match": match.group(0), "start": match.start(), "end": match.end()}

    def match(pattern: str, text: str) -> dict[str, Any] | None:
        match = re.match(_string(pattern, "Pattern"), _string(text, "Text"))
        if match is None:
            return None
        return {"match": match.group(0), "start": match.start(), "end": match.end()}

    def findall(pattern: str, text: str) -> list[str]:
        return re.findall(_string(pattern, "Pattern"), _string(text, "Text"))

    def sub(pattern: str, replacement: str, text: str) -> str:
        return re.sub(
            _string(pattern, "Pattern"),
            _string(replacement, "Replacement"),
            _string(text, "Text"),
        )

    return {"search": search, "match": match, "findall": findall, "sub": sub}


def _statistics_functions() -> dict[str, Callable[..., Any]]:
    import statistics as _statistics

    def mean(values: list[float]) -> float:
        if not isinstance(values, (list, tuple)):
            raise TypeError("mean() requires a list or tuple.")
        return _statistics.mean(values)

    def median(values: list[float]) -> float:
        if not isinstance(values, (list, tuple)):
            raise TypeError("median() requires a list or tuple.")
        return _statistics.median(values)

    def mode(values: list[float]) -> float | list[float]:
        if not isinstance(values, (list, tuple)):
            raise TypeError("mode() requires a list or tuple.")
        return _statistics.mode(values)

    def stdev(values: list[float]) -> float:
        if not isinstance(values, (list, tuple)):
            raise TypeError("stdev() requires a list or tuple.")
        return _statistics.stdev(values)

    def variance(values: list[float]) -> float:
        if not isinstance(values, (list, tuple)):
            raise TypeError("variance() requires a list or tuple.")
        return _statistics.variance(values)

    def correlation(left: list[float], right: list[float]) -> float:
        if not isinstance(left, (list, tuple)) or not isinstance(right, (list, tuple)):
            raise TypeError("correlation() requires two lists or tuples.")
        return _statistics.correlation(left, right)

    def percentile(values: list[float], point: float) -> float:
        if not isinstance(values, (list, tuple)):
            raise TypeError("percentile() requires a list or tuple.")
        if isinstance(point, bool) or not isinstance(point, (int, float)):
            raise TypeError("Point must be numeric.")
        return _statistics.quantiles(values, n=100, method="linear")[int(point) - 1]

    return {
        "mean": mean,
        "median": median,
        "mode": mode,
        "stdev": stdev,
        "variance": variance,
        "correlation": correlation,
        "percentile": percentile,
    }


def _process_functions(program_args: list[str]) -> dict[str, Callable[..., Any]]:
    def args() -> list[str]:
        return list(program_args)

    def env(name: str) -> str | None:
        return os.environ.get(_string(name, "Environment variable name"))

    def exit_process(code: int = 0) -> None:
        if isinstance(code, bool) or not isinstance(code, int):
            raise TypeError("Exit code must be an integer.")
        if not 0 <= code <= 255:
            raise ValueError("Exit code must be between 0 and 255.")
        raise SystemExit(code)

    def run(
        arguments: list[str],
        timeout: int | float = 30.0,
        max_output_bytes: int = 1_048_576,
    ) -> dict[str, Any]:
        if (
            not isinstance(arguments, list)
            or not arguments
            or any(not isinstance(item, str) for item in arguments)
        ):
            raise TypeError("Subprocess arguments must be a non-empty list of strings.")
        duration = _finite_number(timeout, "Timeout")
        if not 0 < duration <= 3600:
            raise ValueError("Timeout must be greater than 0 and at most 3600 seconds.")
        output_limit = _positive_integer(
            max_output_bytes, "Output limit", 67_108_864
        )
        if any("\x00" in item for item in arguments):
            raise ValueError("Subprocess arguments must not contain NUL characters.")

        process = subprocess.Popen(
            arguments,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=False,
        )
        assert process.stdout is not None and process.stderr is not None
        output: dict[str, bytearray] = {
            "stdout": bytearray(),
            "stderr": bytearray(),
        }
        total_size = 0
        output_exceeded = False
        reader_errors: list[OSError] = []
        output_lock = threading.Lock()

        def capture(stream: Any, name: str) -> None:
            nonlocal total_size, output_exceeded
            try:
                while True:
                    chunk = stream.read(65536)
                    if not chunk:
                        return
                    with output_lock:
                        available = max(0, output_limit - total_size)
                        output[name].extend(chunk[:available])
                        total_size += min(len(chunk), available)
                        if len(chunk) > available:
                            output_exceeded = True
                            try:
                                process.kill()
                            except OSError:
                                pass
            except OSError as error:
                with output_lock:
                    reader_errors.append(error)
                try:
                    process.kill()
                except OSError:
                    pass

        readers = [
            threading.Thread(target=capture, args=(process.stdout, "stdout"), daemon=True),
            threading.Thread(target=capture, args=(process.stderr, "stderr"), daemon=True),
        ]
        for reader in readers:
            reader.start()
        try:
            return_code = process.wait(timeout=duration)
        except subprocess.TimeoutExpired as error:
            process.kill()
            process.wait()
            for reader in readers:
                reader.join()
            process.stdout.close()
            process.stderr.close()
            raise TimeoutError(f"Subprocess exceeded its {duration:g}-second timeout.") from error
        for reader in readers:
            reader.join()
        process.stdout.close()
        process.stderr.close()
        if reader_errors:
            raise OSError(f"Cannot capture subprocess output: {reader_errors[0]}") from reader_errors[0]
        if output_exceeded:
            raise ValueError(
                f"Subprocess output exceeded the {output_limit}-byte limit."
            )
        return {
            "exit_code": return_code,
            "stdout": bytes(output["stdout"]),
            "stderr": bytes(output["stderr"]),
        }

    return {"args": args, "env": env, "exit": exit_process, "run": run}


class _SafeRedirectHandler(urllib.request.HTTPRedirectHandler):
    def __init__(self) -> None:
        super().__init__()
        self.redirect_count = 0

    def redirect_request(
        self,
        request: urllib.request.Request,
        response: Any,
        code: int,
        message: str,
        headers: Any,
        new_url: str,
    ) -> urllib.request.Request | None:
        if self.redirect_count >= 5:
            raise urllib.error.HTTPError(
                request.full_url, code, "Redirect limit exceeded", headers, response
            )
        old = urllib.parse.urlsplit(request.full_url)
        new = urllib.parse.urlsplit(urllib.parse.urljoin(request.full_url, new_url))
        if (
            new.scheme not in ("http", "https")
            or not new.hostname
            or new.username is not None
            or new.password is not None
        ):
            raise ValueError(
                "HTTP redirects must target an HTTP(S) URL without user info."
            )
        if old.scheme == "https" and new.scheme != "https":
            raise ValueError("HTTPS redirects may not downgrade to HTTP.")
        redirected = super().redirect_request(
            request, response, code, message, headers, new.geturl()
        )
        if redirected is None:
            return None
        self.redirect_count += 1
        old_origin = (old.scheme, old.hostname, old.port)
        new_origin = (new.scheme, new.hostname, new.port)
        if old_origin != new_origin:
            for collection in (redirected.headers, redirected.unredirected_hdrs):
                for header in list(collection):
                    if header.casefold() in {
                        "authorization",
                        "cookie",
                        "proxy-authorization",
                    }:
                        redirected.remove_header(header)
        return redirected


def _http_functions() -> dict[str, Callable[..., Any]]:
    def request(
        url: str,
        method: str = "GET",
        body: str | bytes | bytearray | None = None,
        headers: dict[str, str] | None = None,
        timeout: int | float = 10.0,
        max_bytes: int = 1_048_576,
    ) -> dict[str, Any]:
        address = _string(url, "URL")
        parsed = urllib.parse.urlsplit(address)
        if (
            parsed.scheme not in ("http", "https")
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
        ):
            raise ValueError("URL must be HTTP(S), include a host, and contain no user info.")
        verb = _string(method, "HTTP method").upper()
        if not verb.isascii() or not verb.isalpha():
            raise ValueError("HTTP method must contain only ASCII letters.")
        if body is None:
            payload = None
        elif isinstance(body, str):
            payload = body.encode("utf-8")
        elif isinstance(body, (bytes, bytearray)):
            payload = bytes(body)
        else:
            raise TypeError("HTTP body must be none, string, bytes, or bytearray.")
        if headers is None:
            request_headers: dict[str, str] = {}
        elif isinstance(headers, dict):
            request_headers = {}
            for name, value in headers.items():
                if not isinstance(name, str) or not isinstance(value, str):
                    raise TypeError("HTTP header names and values must be strings.")
                if "\r" in name or "\n" in name or "\r" in value or "\n" in value:
                    raise ValueError("HTTP headers must not contain line breaks.")
                request_headers[name] = value
        else:
            raise TypeError("HTTP headers must be a dictionary.")
        duration = _finite_number(timeout, "Timeout")
        if not 0 < duration <= 300:
            raise ValueError("Timeout must be greater than 0 and at most 300 seconds.")
        size_limit = _positive_integer(max_bytes, "Response limit", 67_108_864)
        handler = _SafeRedirectHandler()
        opener = urllib.request.build_opener(handler)
        http_request = urllib.request.Request(
            address, data=payload, headers=request_headers, method=verb
        )
        try:
            response = opener.open(http_request, timeout=duration)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            chunks = bytearray()
            while True:
                chunk = response.read(min(65536, size_limit + 1 - len(chunks)))
                if not chunk:
                    break
                chunks.extend(chunk)
                if len(chunks) > size_limit:
                    raise ValueError(
                        f"HTTP response exceeded the {size_limit}-byte limit."
                    )
            return {
                "status": response.status,
                "headers": dict(response.headers.items()),
                "body": bytes(chunks),
            }

    return {"request": request}


def standard_module_functions(
    name: str,
    clock: Callable[[], float],
    random_source: random.Random,
    program_args: list[str],
) -> dict[str, Callable[..., Any]]:
    canonical_name = {
        "math": "math",
        "random": "random",
        "datetime": "datetime",
        "json": "json",
        "pathlib": "pathlib",
        "re": "re",
        "os": "os",
        "hashlib": "hashlib",
        "base64": "base64",
        "subprocess": "subprocess",
        "csv": "csv",
        "statistics": "statistics",
        "sqlite": "sqlite",
        "collections": "collections",
        "sys": "sys",
    }.get(name, name)
    modules: dict[str, Callable[[], dict[str, Callable[..., Any]]]] = {
        "std.path": _path_functions,
        "std.fs": _filesystem_functions,
        "std.time": lambda: _time_functions(clock),
        "std.random": lambda: _random_functions(random_source),
        "std.math": _math_functions,
        "std.json": _json_functions,
        "std.encoding": _encoding_functions,
        "std.process": lambda: _process_functions(program_args),
        "std.http": _http_functions,
        "std.csv": _csv_functions,
        "std.url": _url_functions,
        "std.hash": _hash_functions,
        "std.pathlib": _pathlib_functions,
        "std.re": _re_functions,
        "std.os": lambda: {
            "getenv": lambda key, default=None: os.environ.get(_string(key, "Environment variable name"), default),
            "environ": dict(os.environ),
            "path": os.path,
            "listdir": lambda path: sorted(os.listdir(_string(path, "Path"))),
            "mkdir": lambda path, parents=False: os.makedirs(_string(path, "Path"), exist_ok=parents),
        },
        "std.statistics": _statistics_functions,
        "std.sqlite": _sqlite_functions,
        "std.collections": _collections_functions,
        "std.sys": lambda: {
            "argv": lambda: list(program_args),
            "platform": _sys.platform,
            "version": _sys.version,
            "exit": lambda code=0: (_ for _ in ()).throw(SystemExit(code)),
        },
        "math": _math_functions,
        "random": lambda: _random_functions(random_source),
        "datetime": _datetime_functions,
        "json": _json_functions,
        "pathlib": _pathlib_functions,
        "re": _re_functions,
        "os": lambda: {
            "getenv": lambda key, default=None: os.environ.get(_string(key, "Environment variable name"), default),
            "environ": dict(os.environ),
            "path": os.path,
            "listdir": lambda path: sorted(os.listdir(_string(path, "Path"))),
            "mkdir": lambda path, parents=False: os.makedirs(_string(path, "Path"), exist_ok=parents),
        },
        "hashlib": _hash_functions,
        "base64": lambda: {
            "encode": base64.b64encode,
            "decode": base64.b64decode,
        },
        "subprocess": lambda: _process_functions(program_args),
        "csv": _csv_functions,
        "statistics": _statistics_functions,
        "sqlite": _sqlite_functions,
        "collections": _collections_functions,
        "sys": lambda: {
            "argv": lambda: list(program_args),
            "platform": _sys.platform,
            "version": _sys.version,
            "exit": lambda code=0: (_ for _ in ()).throw(SystemExit(code)),
        },
    }
    if canonical_name not in modules:
        raise KeyError(f"Unknown standard module '{name}'.")
    return modules[canonical_name]()
