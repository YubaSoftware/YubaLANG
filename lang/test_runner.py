"""Discovery and execution of YubaLANG output-based tests."""

import difflib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from .coverage import (
    COVERAGE_ENVIRONMENT_VARIABLE,
    display_path,
    read_coverage,
    summarize_coverage,
)


TEST_TIMEOUT_SECONDS = 10


def _interpreter_command(program: Path) -> list[str]:
    if getattr(sys, "frozen", False):
        return [sys.executable, str(program)]
    entry_point = Path(__file__).resolve().parent.parent / "YubaLANG.py"
    return [sys.executable, str(entry_point), str(program)]


def _normalize_newlines(value: str) -> str:
    return value.replace("\r\n", "\n").replace("\r", "\n")


def _first_difference(expected: str, actual: str) -> str:
    expected_lines = expected.splitlines()
    actual_lines = actual.splitlines()
    for index, (expected_line, actual_line) in enumerate(
        zip(expected_lines, actual_lines), start=1
    ):
        if expected_line != actual_line:
            return f"line {index}: expected {expected_line!r}, got {actual_line!r}"
    if len(expected_lines) != len(actual_lines):
        index = min(len(expected_lines), len(actual_lines)) + 1
        expected_line = expected_lines[index - 1] if index <= len(expected_lines) else "<end of output>"
        actual_line = actual_lines[index - 1] if index <= len(actual_lines) else "<end of output>"
        return f"line {index}: expected {expected_line!r}, got {actual_line!r}"
    return f"line {max(1, len(expected_lines))}: trailing newline differs"


def _run_case(
    program: Path, coverage: bool = False
) -> tuple[str, str, str, str, dict[str, dict[int, int]]]:
    expected_file = program.with_suffix(".expected.txt")
    if not expected_file.is_file():
        return "ERROR", f"missing expected-output file: {expected_file}", "", "", {}

    coverage_path: str | None = None
    coverage_hits: dict[str, dict[int, int]] = {}
    environment = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    try:
        with expected_file.open("r", encoding="utf-8", newline="") as source:
            expected = _normalize_newlines(source.read())
        if coverage:
            handle, coverage_path = tempfile.mkstemp(
                prefix="yubalang-coverage-", suffix=".json"
            )
            os.close(handle)
            environment[COVERAGE_ENVIRONMENT_VARIABLE] = coverage_path
        result = subprocess.run(
            _interpreter_command(program),
            cwd=program.parent,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=environment,
            timeout=TEST_TIMEOUT_SECONDS,
            check=False,
        )
        if coverage_path is not None:
            coverage_hits = read_coverage(coverage_path)
    except (OSError, UnicodeError) as error:
        return "ERROR", str(error), "", "", {}
    except subprocess.TimeoutExpired:
        return "ERROR", f"timed out after {TEST_TIMEOUT_SECONDS} seconds", "", "", {}
    finally:
        if coverage_path is not None:
            try:
                os.unlink(coverage_path)
            except OSError:
                pass

    if result.returncode != 0:
        detail = _normalize_newlines(result.stdout + result.stderr).strip()
        if not detail:
            detail = f"interpreter exited with status {result.returncode}"
        return "ERROR", detail, expected, _normalize_newlines(result.stdout), coverage_hits

    actual = _normalize_newlines(result.stdout)
    if actual != expected:
        return "FAIL", _first_difference(expected, actual), expected, actual, coverage_hits
    return "PASS", "", expected, actual, coverage_hits


def run_tests(
    path: Path,
    filter_pattern: str | None = None,
    output_format: str = "text",
    coverage: bool = False,
) -> int:
    """Run all .yl tests under a directory, or one .yl test file."""
    path = path.resolve()

    if path.is_file() and path.suffix == ".yl":
        programs = [path]
    elif path.is_dir():
        programs = sorted(path.rglob("*.yl"))
    else:
        print(f"test: not a .yl file or directory: {path}", file=sys.stderr)
        return 2

    if filter_pattern:
        pattern = filter_pattern.casefold()
        programs = [
            program for program in programs
            if pattern in program.stem.casefold()
            or pattern in str(program.relative_to(path if path.is_dir() else path.parent)).casefold()
        ]
    if not programs:
        if output_format == "json":
            print(json.dumps({
                "path": str(path), "filter": filter_pattern,
                "counts": {"PASS": 0, "FAIL": 0, "ERROR": 0}, "tests": [],
            }, indent=2))
        else:
            message = "no .yl tests matched" if filter_pattern else "no .yl tests found"
            print(f"test: {message} in {path}", file=sys.stderr)
        return 1

    counts = {"PASS": 0, "FAIL": 0, "ERROR": 0}
    cases = []
    root = path if path.is_dir() else path.parent
    coverage_hits: dict[str, dict[int, int]] = {}
    for program in programs:
        status, detail, expected, actual, case_coverage = _run_case(program, coverage)
        counts[status] += 1
        case: dict[str, object] = {
            "name": str(program.relative_to(root)),
            "status": status,
            "detail": detail,
            "expected": expected,
            "actual": actual,
        }
        if coverage:
            for source_name, file_hits in case_coverage.items():
                merged = coverage_hits.setdefault(source_name, {})
                for line_number, hit_count in file_hits.items():
                    merged[line_number] = merged.get(line_number, 0) + hit_count
            case["coverage"] = {
                display_path(source_name, root): sorted(file_hits)
                for source_name, file_hits in sorted(case_coverage.items())
            }
        cases.append(case)
        if output_format == "text":
            print(f"{status}: {program}")
            if detail:
                print(f"  {detail}")
            if status == "FAIL":
                print("\n".join(difflib.unified_diff(
                    expected.splitlines(), actual.splitlines(),
                    fromfile="expected", tofile="actual", lineterm="",
                )))

    summary = (
        summarize_coverage(coverage_hits, programs, root) if coverage else None
    )
    if output_format == "json":
        report = {
            "path": str(path),
            "filter": filter_pattern,
            "counts": counts,
            "tests": cases,
        }
        if summary is not None:
            report["coverage"] = summary
        print(json.dumps(report, indent=2))
    else:
        print(
            f"Results: {counts['PASS']} passed, {counts['FAIL']} failed, "
            f"{counts['ERROR']} errored"
        )
        if summary is not None:
            print(
                f"Coverage: {summary['percent']:.1f}% "
                f"({summary['covered']}/{summary['total']} executable lines)"
            )
            for file_report in summary["files"]:
                print(
                    f"  {file_report['path']}: "
                    f"{file_report['percent']:.1f}% "
                    f"({file_report['covered']}/{file_report['total']})"
                )
    return 1 if counts["FAIL"] or counts["ERROR"] else 0
