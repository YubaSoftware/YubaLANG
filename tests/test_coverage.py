import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from lang.coverage import (
    COVERAGE_ENVIRONMENT_VARIABLE,
    CoverageCollector,
    executable_lines,
    read_coverage,
    summarize_coverage,
)
from lang.interpreter import run_file


class CoverageTests(unittest.TestCase):
    def test_executable_lines_skip_comments_blank_lines_and_terminators(self):
        source = (
            "# comment\n"
            "\n"
            "define var count: int = 0\n"
            "if count == 0\n"
            "    text output count\n"
            "else\n"
            '    text output "other"\n'
            "endif\n"
            "endfunc\n"
        )
        self.assertEqual(executable_lines(source), [3, 4, 5, 7])

    def test_collector_counts_repeated_executions(self):
        collector = CoverageCollector()
        collector.record("main.yl", 2)
        collector.record("main.yl", 2)
        collector.record("main.yl", 3)
        self.assertEqual(
            collector.as_dict(),
            {
                "version": 1,
                "files": {"main.yl": {"2": 2, "3": 1}},
            },
        )

    def test_run_file_writes_coverage_to_the_side_channel_only(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "program.yl"
            coverage_file = root / "coverage.json"
            source.write_text(
                "define var count: int = 0\n"
                "loop for 2\n"
                "    set count = count + 1\n"
                "endloop\n"
                'text output "done"\n',
                encoding="utf-8",
            )
            output = io.StringIO()
            with (
                patch.dict(
                    os.environ,
                    {COVERAGE_ENVIRONMENT_VARIABLE: str(coverage_file)},
                ),
                contextlib.redirect_stdout(output),
            ):
                run_file(str(source))

            self.assertEqual(output.getvalue(), "done\n")
            payload = json.loads(coverage_file.read_text(encoding="utf-8"))
            entries = payload["files"][str(source.resolve())]
            self.assertEqual(entries["1"], 1)
            self.assertEqual(entries["3"], 2)

    def test_coverage_file_is_written_when_the_program_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "broken.yl"
            coverage_file = root / "coverage.json"
            source.write_text(
                'define var value: string = "ok"\n'
                "text output missing\n",
                encoding="utf-8",
            )
            output = io.StringIO()
            with (
                patch.dict(
                    os.environ,
                    {COVERAGE_ENVIRONMENT_VARIABLE: str(coverage_file)},
                ),
                contextlib.redirect_stdout(output),
                self.assertRaises(SystemExit),
            ):
                run_file(str(source))
            self.assertTrue(coverage_file.is_file())
            self.assertEqual(
                sorted(read_coverage(coverage_file)[str(source.resolve())]),
                [1, 2],
            )

    def test_summary_reports_uncovered_executable_lines(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.yl"
            source.write_text(
                "define var flag: bool = true\n"
                "if flag\n"
                '    text output "hit"\n'
                "else\n"
                '    text output "miss"\n'
                "endif\n",
                encoding="utf-8",
            )
            summary = summarize_coverage(
                {str(source.resolve()): {1: 1, 2: 1, 3: 1}},
                [source],
                root,
            )
            self.assertEqual(summary["covered"], 3)
            self.assertEqual(summary["total"], 4)
            self.assertEqual(summary["files"][0]["path"], "source.yl")
            self.assertEqual(summary["files"][0]["uncovered"], [5])


if __name__ == "__main__":
    unittest.main()
