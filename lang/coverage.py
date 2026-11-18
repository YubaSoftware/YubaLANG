"""Source-level line coverage collection for YubaLANG programs and tests."""

from dataclasses import dataclass, field
import json
from pathlib import Path
from typing import Any, Iterable

from .syntax import tokenize_line


COVERAGE_VERSION = 1
COVERAGE_ENVIRONMENT_VARIABLE = "YUBALANG_COVERAGE_FILE"

_STRUCTURAL_COMMANDS = frozenset(
    {"elseif", "else", "endif", "catch", "finally", "endfunc", "endloop", "endtry"}
)


@dataclass
class CoverageCollector:
    """Record executed source lines as a per-file hit count."""

    hits: dict[str, dict[int, int]] = field(default_factory=dict)

    def record(self, source_name: str, line_number: int) -> None:
        file_hits = self.hits.setdefault(source_name, {})
        file_hits[line_number] = file_hits.get(line_number, 0) + 1

    def as_dict(self) -> dict[str, Any]:
        return {
            "version": COVERAGE_VERSION,
            "files": {
                source_name: {
                    str(line_number): count
                    for line_number, count in sorted(file_hits.items())
                }
                for source_name, file_hits in sorted(self.hits.items())
            },
        }


def write_coverage(path: str | Path, collector: CoverageCollector) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    temporary.write_text(
        json.dumps(collector.as_dict(), indent=2, sort_keys=True),
        encoding="utf-8",
    )
    temporary.replace(destination)


def read_coverage(path: str | Path) -> dict[str, dict[int, int]]:
    """Read a coverage side-channel file into source-name to line-count maps."""
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return {}
    files = payload.get("files") if isinstance(payload, dict) else None
    if not isinstance(files, dict):
        return {}
    result: dict[str, dict[int, int]] = {}
    for source_name, file_hits in files.items():
        if not isinstance(source_name, str) or not isinstance(file_hits, dict):
            continue
        counts: dict[int, int] = {}
        for line_number, count in file_hits.items():
            try:
                line = int(line_number)
                hits = int(count)
            except (TypeError, ValueError):
                continue
            if line > 0 and hits > 0:
                counts[line] = hits
        result[source_name] = counts
    return result


def executable_lines(source: str) -> list[int]:
    """Return one-based line numbers that the interpreter can execute.

    Blank lines, comments, and branch/block terminators are excluded. Branch
    bodies and statements inside function definitions remain executable.
    """
    result: list[int] = []
    for line_number, line in enumerate(source.splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        try:
            parts = tokenize_line(stripped)
        except SyntaxError:
            parts = ()
        if parts and parts[0] in _STRUCTURAL_COMMANDS:
            continue
        result.append(line_number)
    return result


def display_path(source_name: str, root: Path) -> str:
    path = Path(source_name)
    try:
        relative = path.resolve().relative_to(root.resolve())
    except (OSError, ValueError):
        return str(path)
    return str(relative)


def summarize_coverage(
    coverage: dict[str, dict[int, int]],
    source_paths: Iterable[str | Path],
    root: Path,
) -> dict[str, Any]:
    """Build a deterministic report from collected hits and source files."""
    paths = {str(Path(source_name).resolve()) for source_name in coverage}
    paths.update(str(Path(path).resolve()) for path in source_paths)

    files = []
    total_lines = 0
    covered_lines = 0
    for path in sorted(paths):
        try:
            source = Path(path).read_text(encoding="utf-8-sig")
        except (OSError, UnicodeError):
            continue
        executable = executable_lines(source)
        hits = coverage.get(path, {})
        uncovered = [line for line in executable if line not in hits]
        covered = len(executable) - len(uncovered)
        total_lines += len(executable)
        covered_lines += covered
        percent = (covered / len(executable) * 100.0) if executable else 100.0
        files.append({
            "path": display_path(path, root),
            "covered": covered,
            "total": len(executable),
            "percent": round(percent, 1),
            "uncovered": uncovered,
        })

    percent = (covered_lines / total_lines * 100.0) if total_lines else 100.0
    return {
        "covered": covered_lines,
        "total": total_lines,
        "percent": round(percent, 1),
        "files": files,
    }
