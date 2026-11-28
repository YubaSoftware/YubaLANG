# YubaLANG standard library

YubaLANG 1.4 provides bundled modules under the reserved `std.*` namespace.
Import one like any other module and call its functions with `func call`:

```hl
import std.path as path
import std.json as json

define var joined: string = ""
define var value: dict = {}
func call path.join "data" "settings.json" -> joined
func call json.loads '{"enabled": true}' -> value
```

These modules are part of the YubaLANG runtime. They do not need a manifest
dependency, package installation, or network access (except `std.http`). The
namespace is reserved: an import matching a bundled `std.*` module resolves to
the standard library before local or package modules.

## Modules

| Module | Functions |
| --- | --- |
| `std.path` | `join`, `normalize`, `basename`, `dirname`, `extension`, `is_absolute`, `resolve`, `relative` |
| `std.fs` | `read_text`, `write_text`, `read_bytes`, `write_bytes`, `atomic_write_text`, `atomic_write_bytes`, `replace`, `exists`, `is_file`, `is_dir`, `size`, `modified`, `list_dir`, `list_files`, `expand`, `mkdir`, `remove_file` |
| `std.time` | `now`, `utc_iso`, `parse_iso`, `sleep` |
| `std.random` | `seed`, `integer`, `uniform`, `choice`, `random`, `randint`, `shuffle`, `sample` |
| `std.math` | `abs`, `ceil`, `floor`, `sqrt`, `pow`, `sin`, `cos`, `is_finite`, `pi`, `e` |
| `std.json` | `loads`, `dumps` |
| `std.encoding` | `utf8_encode`, `utf8_decode`, `base64_encode`, `base64_decode` |
| `std.process` | `args`, `env`, `exit`, `run` |
| `std.http` | `request` |
| `std.csv` | `loads`, `dumps` |
| `std.url` | `parse`, `join`, `encode_component`, `decode_component`, `parse_query`, `build_query` |
| `std.hash` | `sha256`, `sha256_file` |
| `std.regex` | `compile`, `is_match`, `fullmatch`, `search`, `match`, `findall`, `finditer`, `split`, `sub`, `subn`, `escape`, `group_count` |
| `std.glob` | `match`, `filter`, `expand`, `has_magic`, `walk` |
| `std.tempfile` | `file`, `directory`, `name`, `cleanup`, `is_tracked` |
| `std.archive` | `create`, `add_bytes`, `add_text`, `add_file`, `close`, `abort`, `list`, `info`, `read`, `read_text`, `extract`, `verify` |
| `std.sqlite` | `open`, `execute`, `executemany`, `query`, `begin`, `commit`, `rollback`, `close`, `tables` |
| `std.uuid` | `uuid1`, `uuid3`, `uuid4`, `uuid5`, `parse`, `is_valid`, `nil`, `max` |
| `std.decimal` | `parse`, `add`, `subtract`, `multiply`, `divide`, `modulo`, `power`, `sqrt`, `negate`, `abs`, `compare`, `quantize`, `round`, `to_integer`, `is_finite`, `is_nan`, `is_zero`, `sign`, `format` |
| `std.statistics` | `mean`, `fmean`, `median`, `median_low`, `median_high`, `mode`, `multimode`, `stdev`, `variance`, `pstdev`, `pvariance`, `correlation`, `linear_regression`, `percentile`, `quantiles`, `summary` |
| `std.logging` | `configure`, `set_level`, `get_level`, `log`, `debug`, `info`, `warning`, `error`, `critical`, `add_file`, `remove_file`, `flush` |
| `std.terminal` | `is_tty`, `size`, `supports_color`, `style`, `strip_ansi`, `reset`, `clear`, `move`, `hide_cursor`, `show_cursor` |
| `std.env` | `get`, `has`, `set`, `unset`, `all`, `args`, `cwd`, `chdir`, `home`, `temp_dir`, `platform`, `executable`, `pid`, `separator`, `path_separator`, `expand_vars`, `expand_user` |
| `std.io` | `write`, `writeline`, `read`, `readline`, `flush`, `is_tty`, `encoding` |
| `std.sys` | `argv`, `platform`, `version`, `limits`, `set_limit`, `exit` |

`func call namespace.function ... -> destination` stores the result in an
existing variable. Use `bytes` for binary values, `dict` for JSON objects and
HTTP responses, and `list` for process arguments and directory entries.

## Paths and files

Paths use the host operating system's `pathlib.Path` semantics. Separators,
absolute-path checks, normalization, and resolution therefore follow the
platform running the program; the library does not reinterpret a Windows path
as a POSIX path or vice versa. `resolve` makes a path absolute and resolves
existing path components. `join` and `normalize` are lexical operations and
do not themselves check file existence.

Text file APIs use strict UTF-8 without adding a byte-order mark; a BOM already
in a file is preserved as the first text character. `read_bytes` and
`write_bytes` handle raw bytes. `write_text` and `write_bytes` create a new
file by default and fail rather than overwriting an existing file. Pass
`overwrite=true` to replace it atomically using a temporary file in the same
directory. `atomic_write_text` and `atomic_write_bytes` always replace through
a temporary file and `fsync`; `replace(source, destination)` exposes the host's
atomic rename operation. Parent directories are not created implicitly.
`remove_file` removes one file or symbolic link and never recursively deletes
directories. `is_dir`, `size`, and `modified` inspect a path, and `list_files`
or `expand` return sorted path lists so repeated runs observe the same order.
The filesystem APIs operate with the program's host privileges; they are not a
sandbox or a path-containment boundary.

```hl
import std.fs as fs

define var contents: string = ""
func call fs.read_text "notes.txt" -> contents
func call fs.write_text "copy.txt" contents
```

## Time, randomness, math, data, and encoding

`std.time.now()` returns a Unix timestamp in seconds. `utc_iso(timestamp)`
formats an RFC 3339-compatible UTC timestamp ending in `Z`; `parse_iso(text)`
returns a Unix timestamp and rejects strings without an explicit UTC offset.
`sleep(seconds)` blocks the current program and rejects negative durations.
Tests can supply a clock to the host `Runtime` constructor instead of relying
on wall-clock time.

`std.random` owns a generator per runtime. `seed(integer)` makes subsequent
results reproducible; `integer(minimum, maximum)` includes both endpoints,
`uniform(minimum, maximum)` returns a float, and `choice(values)` requires a
non-empty list, tuple, or string. Tests can also inject a seeded generator
through the host `Runtime` constructor. This module is not a cryptographic
random source.

`std.math` provides common scalar operations and the `pi()` and `e()` constants
as zero-argument functions. `std.json.loads(text)` parses JSON into YubaLANG
values. `loads` rejects non-standard numeric constants. `dumps(value,
indent=none, sort_keys=false)` emits JSON, preserves Unicode characters, and
rejects non-finite floating-point numbers. Unsupported host values (such as
sets and bytes) produce explicit errors.

`std.encoding.utf8_encode(text)` and `utf8_decode(bytes)` use strict UTF-8.
`base64_encode(bytes)` returns ASCII text, and `base64_decode(text)` validates
the input rather than accepting malformed data.

`std.csv.loads(text, delimiter=",")` returns rows of string cells and parses
quoted fields and embedded newlines according to CSV rules. `dumps(rows,
delimiter=",")` accepts rows of strings and emits deterministic LF-terminated
CSV, quoting cells when required. Delimiters must be a single non-newline
character.

`std.url.parse(url)` returns a dictionary with `scheme`, `host`, `port`,
`path`, `query`, `fragment`, `username`, and `is_absolute` fields. Passwords
are intentionally not returned. `join(base, reference)` resolves relative URL
references. Component encoding uses UTF-8 percent-encoding; query helpers
represent repeated query keys as lists of strings, preserve blank values, and
reject non-string query values.

`std.hash.sha256(value)` returns a lowercase hexadecimal SHA-256 digest of
UTF-8 text or raw bytes. `sha256_file(path)` reads a file incrementally and
returns the digest without loading the complete file into memory. SHA-256 is
for integrity and identification, not password storage or signatures.

## Regular expressions and globbing

`std.regex.compile(pattern, flags="", allow_unsafe=false)` returns a dictionary
with `pattern`, `flags`, and `groups`. Every matching, replacement, and split
function accepts either that dictionary or a pattern string. Flags are the
letters `i` (ignore case), `m` (multiline), `s` (dot matches newline), `x`
(verbose), `a` (ASCII), and `u` (Unicode). `search`, `match`, and `fullmatch`
return `none` or a dictionary containing `match`, `groups`, `groupdict`,
`start`, `end`, and `span`. `findall` returns strings or lists of groups;
`finditer` returns the same match dictionaries as `search`.

Patterns are limited to 4096 characters, input text to 8 MiB, and a single call
to 100,000 matches. A pattern containing an obvious nested quantifier such as
`(a+)+` is rejected with `regex-backtracking` before it can consume excessive
time. Pass `allow_unsafe=true` only after reviewing the input bounds. These
limits reduce accidental denial of service; they do not make arbitrary
user-supplied patterns safe.

```hl
import std.regex as regex

define var compiled: dict = {}
define var found: list = []
func call regex.compile "(?P<word>\\w+)-(\\d+)" -> compiled
func call regex.findall "\\d+" "item-42 and item-7" -> found
```

`std.glob` provides lexical glob matching and path expansion. `match` and
`filter` use `fnmatch`-style `*`, `?`, and bracket patterns; `expand` uses the
host glob implementation, and `walk` recursively lists matching files under a
directory. All returned lists are sorted.

## Temporary files and archives

`std.tempfile.file(suffix="", prefix="tmp", directory=none, text="")` and
`directory(...)` create resources and return `{"path": ..., "kind": ...}`.
They are registered with the runtime, so a normal file run removes them at
cleanup. `cleanup(path)` removes a tracked or explicit path immediately and
`is_tracked(path)` reports whether the runtime owns it. A temporary file is
written as strict UTF-8. Temporary names are not a security boundary: create
files in a directory controlled by the program when other users can write to
the system temporary directory.

`std.archive` writes ZIP files and reads or extracts them. `create` returns a
handle dictionary and refuses to overwrite an existing archive unless
`overwrite=true`; `add_text`, `add_bytes`, and `add_file` add entries;
`close` commits the archive atomically and `abort` discards it. `list`, `info`,
`read`, `read_text`, `extract`, and `verify` inspect existing archives.
Member names must be relative, must not contain `..`, and must name files;
extraction rejects symbolic links, refuses to overwrite by default, and limits
the total extracted size to 256 MiB (or `max_bytes`). These checks prevent path
traversal through archive entries.

```hl
import std.tempfile as tempfile
import std.archive as archive

define var temporary: dict = {}
define var temporary_path: string = ""
define var writer: dict = {}
func call tempfile.file suffix=".txt" text="payload" -> temporary
getattr temporary "path" temporary_path
func call archive.create "bundle.zip" -> writer
func call archive.add_file writer "payload.txt" temporary_path
func call archive.close writer
```

## SQLite

`std.sqlite.open(path=":memory:", timeout=5.0, read_only=false)` returns a
handle dictionary; `read_only` requires an existing file. Use `execute` or
`executemany` with a list, tuple, or dictionary of parameters; values are bound
by the SQLite driver and are never interpolated into SQL. `query` returns a list
of dictionaries and accepts `limit` (default 10,000, maximum 100,000).
`begin`, `commit`, and `rollback` control an explicit transaction. Closing a
handle rolls back an active transaction and is idempotent. SQL text is limited
to 1 MiB, parameters to 10,000 values, and rows to the query limit.

```hl
import std.sqlite as sqlite

define var database: dict = {}
define var rows: list = []
define var parameters: list = ["first"]
func call sqlite.open ":memory:" -> database
func call sqlite.execute database "CREATE TABLE items (id INTEGER PRIMARY KEY, name TEXT)"
func call sqlite.execute database "INSERT INTO items (name) VALUES (?)" parameters
func call sqlite.query database "SELECT * FROM items" -> rows
func call sqlite.close database
```

## Identifiers, decimals, and statistics

`std.uuid.uuid4()` generates a random identifier; `uuid1` uses the host time
and node; `uuid3` and `uuid5` derive deterministic identifiers from a namespace
(`dns`, `url`, `oid`, `x500`, or a UUID string) and a name. `parse` returns
`canonical`, `hex`, `int`, `urn`, `version`, and `variant` fields. `nil()` and
`max()` return the all-zero and all-ones identifiers. UUIDs are not secrets.

`std.decimal` performs decimal arithmetic without binary floating-point rounding
surprises. Values may be strings, integers, or floats (floats are converted
through their shortest decimal representation). Arithmetic functions accept
`precision` (default 28) and `rounding` (default `half_even`; supported names
include `half_up`, `half_down`, `up`, `down`, `ceiling`, `floor`, and `05up`).
Results are strings so callers choose when to convert to a numeric type.

`std.statistics` accepts non-empty lists or tuples of finite numbers. It
provides `mean`, `fmean`, `median`, `median_low`, `median_high`, `mode`,
`multimode`, sample and population standard deviation and variance,
`correlation`, `linear_regression`, `percentile`, `quantiles`, and `summary`.
`summary` returns `count`, `minimum`, `maximum`, `mean`, `median`, and
`stdev`. `percentile` uses linear interpolation between the closest ranks.

## Logging, terminal, environment, and streams

`std.logging` writes deterministic text records to `stdout`, `stderr`, or one
or more files. `configure(level="info", destination="stderr", timestamps=true)`
sets the threshold and destination; `debug`, `info`, `warning`, `error`, and
`critical` emit records. `add_file(path, level="info", append=true)` returns a
handle and `remove_file` closes it. Records are flushed immediately, so they are
visible even if the program exits later. Logging is synchronous and intended
for diagnostics, not high-throughput structured logging.

`std.terminal.style(text, fg=none, bg=none, bold=false, underline=false,
dim=false)` returns ANSI styling; colors are names such as `red` or
`bright_blue`, or palette numbers from 0 through 255. `strip_ansi` removes
styling, `size` reports terminal columns and rows, and `is_tty` or
`supports_color` report whether styling is appropriate. Styling is only text;
the library never changes terminal modes.

`std.env` reads and updates the host environment and working directory.
`get(name, default=none)`, `has`, `set`, `unset`, `all`, `args`, `cwd`, `chdir`,
`home`, `temp_dir`, `platform`, `executable`, `pid`, `separator`,
`path_separator`, `expand_vars`, and `expand_user` are available. `chdir`
changes the process-wide working directory and therefore affects later file and
subprocess operations. Environment values are strings; invalid names and
values containing `=` or NUL are rejected.

`std.io` writes text or bytes to the standard streams and reads binary standard
input. `write(value, stream="stdout", newline=false, flush=false)` accepts a
string for the text stream or bytes/bytearray for the binary stream.
`writeline`, `read`, `readline`, `flush`, `is_tty`, and `encoding` provide the
remaining stream operations. The text stream uses the host encoding; the
binary stream bypasses text encoding.

## Runtime limits

Every runtime has configurable bounds. The defaults are:

| Limit | Default | Meaning |
| --- | --- | --- |
| `max_call_depth` | 128 | Nested user and native function calls. |
| `max_collection_size` | 1,000,000 | Entries in a top-level list, tuple, set, or dictionary. |
| `http_default_timeout` | 10 seconds | HTTP timeout when the caller omits one. |
| `http_max_timeout` | 300 seconds | Largest accepted HTTP timeout. |
| `http_default_max_bytes` | 1 MiB | Default HTTP response body limit. |
| `http_max_bytes` | 64 MiB | Largest accepted HTTP response body limit. |
| `process_default_timeout` | 30 seconds | Subprocess timeout when the caller omits one. |
| `process_max_timeout` | 3600 seconds | Largest accepted subprocess timeout. |
| `process_default_max_output_bytes` | 1 MiB | Default combined subprocess output limit. |
| `process_max_output_bytes` | 64 MiB | Largest accepted subprocess output limit. |

Hosts may pass these fields to `Runtime(...)`. Programs can read the current
values with `std.sys.limits()` and update them with
`std.sys.set_limit(name, value)`; a default bound may not exceed its maximum,
and a maximum may not fall below its default. Exceeding a limit raises a
source-located diagnostic with the `limit-error` or `stack-overflow` code.
Collection checks apply when a value is assigned or mutated; nested
collections are checked as they are assigned.

## Typed errors and resource handles

`try`/`catch` catches language and runtime errors. A plain `catch` handles any
error. `catch <variable>` stores a dictionary with `kind`, `message`, `code`,
`cause`, `stack`, and `value`; its string form remains the human-readable
message, so existing `text output problem` examples keep working. Use
`catch <kind> as <variable>` to handle only one kind, such as `io`, `type`,
`value`, `index`, `key`, `regex`, `archive`, `sqlite`, `http`, `process`,
`timeout`, or `limit`. A non-matching kind rethrows the original error.

```hl
define var problem: dict = {}
define var caught: dict = {}
define var kind: string = ""
error io "disk full" problem
try
    throw problem
catch io as caught
    getattr caught "kind" kind
    text output kind
endtry
```

The `stack` field is a list of dictionaries with `function`, `source`, and
`line`; it is captured when the error is caught and never contains a Python
traceback. The `cause` field may hold another error value, allowing wrappers
without exposing host exception objects. Use `error <kind> <message>
<destination> [cause]` to construct an error value explicitly.

Iterators created with `iter` and the resources behind standard-library
handles (temporary files and directories, archives, SQLite connections, and log
files) are registered with the runtime. Use the module's close function for an
early close, such as `archive.close`, `sqlite.close`, or
`logging.remove_file`; use `close` for a file or iterator. Closing an already
closed resource is a no-op. At normal exit, tracked resources close in reverse
registration order, every resource is attempted even if an earlier close
fails, and the first failure is raised after cleanup finishes. A file iterator
owns its file: closing the iterator closes the underlying file.

## Ordering and hashing guarantees

- Dictionaries preserve insertion order. Updating an existing key does not
  move it; deleting and re-inserting a key moves it to the end.
- Lists and tuples preserve their explicit order. `sorted` and all
  standard-library functions documented as returning sorted paths or names use
  a stable, locale-independent ordering.
- Sets and the set-like results of collection operations do not promise
  iteration order. Convert them to a sorted list when output order matters.
- Strings hash and compare by Unicode code point; bytes hash and compare by
  byte value. Numeric equality follows host IEEE-754 semantics for floats.
- Hash-based collection lookup is deterministic for a single runtime but the
  numeric hash seed is not a stable cross-run identifier. Do not persist or
  transmit `id()` values or raw hash values.

## Process APIs

`std.process.args()` returns arguments supplied after the source file or
project separator. For projects, pass them after `--`:

```text
YubaLANG run [project-directory] -- first second
YubaLANG main.yl first second
```

`env(name)` returns a string or `none` when the variable is unset. `exit(code)`
terminates the program with an integer status from 0 through 255. `run(args,
timeout=30.0, max_output_bytes=1048576)` starts a subprocess with an explicit
non-empty list of string arguments, no shell, and closed standard input. It
returns a dictionary containing `exit_code`, `stdout`, and `stderr`; output
fields are bytes. The default timeout is 30 seconds, the maximum is one hour,
and combined captured output is limited to 1 MiB by default (1 byte through
64 MiB). These defaults and maxima are configurable through the runtime limits
described above.
A timeout, output-limit breach, or operating-system launch failure is an
explicit runtime error. The child inherits the current working directory and
environment and runs with the caller's privileges; this is not a sandbox.

## HTTP client

`std.http.request(url, method="GET", body=none, headers=none, timeout=10.0,
max_bytes=1048576)` is synchronous and returns a dictionary with integer
`status`, string `headers`, and byte `body`. HTTP error statuses such as 404
are returned as responses; transport, timeout, and policy errors are reported
as runtime errors.

The client follows at most five redirects (using the standard 301/302/303
POST-to-GET behavior and preserving methods for 307/308), accepts only HTTP(S)
URLs without embedded user information (including redirect targets), and never
downgrades an HTTPS request to HTTP.
TLS certificate and hostname verification use the platform's default verified
TLS configuration and cannot be disabled through this API. Authorization,
cookie, and proxy-authorization headers are stripped on cross-origin
redirects. No cookie jar or credential store is used. The timeout is a
per-socket-operation timeout, must be greater than zero, and is at most 300
seconds by default; DNS lookup is not covered, and a server that continually
sends data may take longer than that overall. Response bodies are streamed and
limited to 1 MiB by default, with a maximum of 64 MiB. Both bounds are
configurable through the runtime limits described above. String request bodies
are encoded as UTF-8; byte request bodies remain unchanged. Response bodies are
always returned as bytes.

```hl
import std.http as http

define var response: dict = {}
func call http.request "https://example.invalid/status" -> response
```

Network access is not required for other standard-library modules. Tests for
HTTP behavior should use local fixtures rather than an external service.

## Stability and async policy

The standard-library API baseline is version 1.0, bundled with the YubaLANG
1.4 runtime. The runtime version selects the standard-library API; a project
manifest does not pin standard-library modules separately.

- New modules and functions may be added compatibly within a minor runtime
  release.
- Existing names, argument meanings, return shapes, encoding behavior, and
  documented errors remain stable within a minor release line.
- A breaking change requires a major runtime version and migration guidance.
- A deprecated API must document its replacement and remain available through
  at least one subsequent minor release before removal.
- Patch releases may correct behavior that contradicts this reference but
  must not silently repurpose an API.
- Platform or network APIs must document their side effects, resource limits,
  and error behavior. Standard-library exceptions are source-located.

The 1.4 API is synchronous. YubaLANG has no event loop, cancellation model, or
concurrent task semantics, so asynchronous I/O is deferred; the HTTP client
and sleep operation block the calling program. Time and randomness have
injectable host-runtime seams, filesystem and subprocess tests use isolated
temporary fixtures, and HTTP tests use local servers. No standard-library
operation is a security sandbox.
