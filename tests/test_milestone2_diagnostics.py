import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from lang.diagnostic_codes import (
    DIAGNOSTICS,
    code_for_runtime,
    explain_diagnostic,
    list_diagnostics,
)
from lang.lsp import analyze_document
from lang.runtime import LanguageException
from lang.typecheck import check_types, check_types_detailed

REPOSITORY_ROOT = Path(__file__).resolve().parent.parent
ENTRY_POINT = REPOSITORY_ROOT / "YubaLANG.py"
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "diagnostics"


def run_cli(*arguments):
    return subprocess.run(
        [sys.executable, str(ENTRY_POINT), *map(str, arguments)],
        cwd=REPOSITORY_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )


class DiagnosticCodeTests(unittest.TestCase):
    def test_every_registered_code_has_a_unique_explanation_and_severity(self):
        codes = [info.code for info in list_diagnostics()]
        self.assertEqual(len(codes), len(set(codes)))
        for info in list_diagnostics():
            with self.subTest(code=info.code):
                self.assertIn(info.severity, ("error", "warning"))
                self.assertTrue(info.title)
                self.assertTrue(info.explanation)
                self.assertTrue(info.example)
                explanation = explain_diagnostic(info.code)
                self.assertIsNotNone(explanation)
                self.assertIn(info.code, explanation)

    def test_reserved_pattern_diagnostics_are_explainable(self):
        self.assertIn("non-exhaustive-match", DIAGNOSTICS)
        self.assertIn("invalid-pattern", DIAGNOSTICS)
        self.assertIn("exhaustive", explain_diagnostic("non-exhaustive-match"))

    def test_runtime_errors_map_to_stable_codes(self):
        cases = [
            (ValueError("Variable 'missing' is not defined."), "undefined-variable"),
            (ValueError("Function 'missing' is not defined."), "undefined-function"),
            (ZeroDivisionError("Cannot divide by zero."), "division-by-zero"),
            (TypeError("Arithmetic requires numbers. Got 'x' instead."), "arithmetic-error"),
            (TypeError("Condition must evaluate to a boolean."), "condition-type"),
            (LanguageException("broken"), "uncaught-exception"),
            (OSError("missing file"), "io-error"),
            (AssertionError("Assertion failed: nope"), "assertion-failed"),
        ]
        for error, expected in cases:
            with self.subTest(error=type(error).__name__, message=str(error)):
                self.assertEqual(code_for_runtime(error), expected)

    def test_static_codes_are_registered(self):
        sources = [
            "if\n",
            "unknown command\n",
            "define var value: mystery = 1\n",
            'text output "unterminated\n',
            "if true\n",
            "define var value: int? = 5\n"
            "define var values: list[int] = [value]\n",
        ]
        for source in sources:
            for diagnostic in analyze_document(source):
                with self.subTest(code=diagnostic["code"]):
                    self.assertIn(diagnostic["code"], DIAGNOSTICS)


class NarrowingTests(unittest.TestCase):
    def test_narrows_optionals_in_if_and_else_branches(self):
        source = [
            "define var value: int? = 5",
            "if value != none",
            "    define var present: list[int] = [value]",
            "else",
            "    define var absent: list[none] = [value]",
            "endif",
        ]
        self.assertEqual(check_types(source), [])

    def test_narrows_unions_across_elseif_and_else(self):
        source = [
            "define var value: int | string | none = 5",
            "if value == none",
            "    define var nothing: list[none] = [value]",
            "elseif value == 5",
            "    define var numbers: list[int] = [value]",
            "else",
            "    define var text: list[string] = [value]",
            "endif",
        ]
        self.assertEqual(check_types(source), [])

        wrong = list(source)
        wrong[6] = "    define var text: list[int] = [value]"
        diagnostics = check_types(wrong)
        self.assertEqual([line for line, _ in diagnostics], [6])
        self.assertIn("list[string]", diagnostics[0][1])

    def test_early_return_narrows_the_following_statements(self):
        source = [
            "func define normalize candidate:int? -> int",
            "    if candidate == none",
            "        return 0",
            "    endif",
            "    define var values: list[int] = [candidate]",
            "    return 0",
            "endfunc",
        ]
        self.assertEqual(check_types(source), [])

    def test_unchecked_optional_still_fails_a_nested_generic(self):
        diagnostics = check_types(
            [
                "define var value: int? = 5",
                "define var values: list[int] = [value]",
            ]
        )
        self.assertEqual([line for line, _ in diagnostics], [1])
        self.assertIn("list[int | none]", diagnostics[0][1])

    def test_narrowing_does_not_change_runtime_checks(self):
        result = run_cli(
            "check",
            FIXTURES / "narrowing_ok.yl",
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


class InferenceTests(unittest.TestCase):
    def test_infers_comprehension_filters_and_collection_results(self):
        source = [
            "func define double item:int -> int",
            "    return item * 2",
            "endfunc",
            "define var numbers: list[int] = [1, 2]",
            "define var doubled: list[int] = []",
            "map double numbers doubled",
            "define var filtered: list[int] = []",
            "filter double numbers filtered",
            "define var sorted_values: list[int] = []",
            "sorted numbers sorted_values",
            "define var pairs: list[tuple[int, int]] = []",
            "enumerate numbers pairs",
            "define var squares: list[int] = [item * item for item in range(5)]",
            "define var first: int = 0",
            "list get numbers 0 first",
            "define var mapping: dict[string, int] = {'a': 1}",
            "define var fetched: int = 0",
            "dict get mapping 'a' fetched",
        ]
        self.assertEqual(check_types(source), [])

    def test_infers_map_results_and_reports_wrong_destination(self):
        diagnostics = check_types(
            [
                "func define double item:int -> int",
                "    return item * 2",
                "endfunc",
                "define var numbers: list[int] = [1, 2]",
                "define var labels: list[string] = []",
                "map double numbers labels",
            ]
        )
        self.assertEqual([line for line, _ in diagnostics], [5])
        self.assertIn("list[int]", diagnostics[0][1])

    def test_infers_comprehension_filter_narrowing(self):
        source = [
            "define var optional: int? = 5",
            "define var present: list[int] = "
            "[item for item in [optional] if item != none]",
        ]
        self.assertEqual(check_types(source), [])

    def test_infers_record_and_dictionary_field_results(self):
        source = [
            "record define Point x:int",
            "record create Point point 5",
            "define var coordinate: int = 0",
            "getattr point x coordinate",
            "define var mapping: dict[string, string] = {'name': 'Ada'}",
            "define var name: string = ''",
            "getattr mapping name name",
        ]
        self.assertEqual(check_types(source), [])

    def test_infers_simple_alias_chains(self):
        source = [
            "define var original: int = 1",
            "define var first: int = original",
            "define var second: int = first",
            "define var values: list[int] = [second]",
        ]
        self.assertEqual(check_types(source), [])


class SeverityAndModeTests(unittest.TestCase):
    def test_analyzer_reports_warning_severity(self):
        diagnostics = analyze_document(
            "define var count: int = 1\n"
            "if true\n"
            "    define var count: int = 2\n"
            "endif\n"
        )
        self.assertEqual([item["code"] for item in diagnostics], ["shadowed-variable"])
        self.assertEqual(diagnostics[0]["severity"], 2)

    def test_check_types_keeps_the_error_only_contract(self):
        source = [
            "func define stop -> int",
            "    return 0",
            '    text output "never"',
            "endfunc",
        ]
        self.assertEqual(check_types(source), [])
        detailed = check_types_detailed(source)
        self.assertEqual([item.code for item in detailed], ["unreachable-code"])
        self.assertEqual(detailed[0].severity, "warning")

    def test_strict_mode_adds_annotation_warnings(self):
        source = ["func define loose value:mystery", "endfunc"]
        self.assertEqual(
            [item.code for item in check_types_detailed(source)],
            [],
        )
        self.assertEqual(
            [item.code for item in check_types_detailed(source, strict=True)],
            ["invalid-annotation"],
        )

    def test_default_check_accepts_warnings_but_deny_warnings_fails(self):
        result = run_cli("check", FIXTURES / "shadow.yl")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("warning: Variable 'count' shadows", result.stdout)

        denied = run_cli("check", "--deny-warnings", FIXTURES / "shadow.yl")
        self.assertEqual(denied.returncode, 1)
        self.assertIn("[shadowed-variable]", denied.stdout)

    def test_strict_mode_fails_on_warnings_and_enables_extra_checks(self):
        strict = run_cli("check", "--strict", FIXTURES / "invalid_annotation.yl")
        self.assertEqual(strict.returncode, 1)
        self.assertIn("[invalid-annotation]", strict.stdout)

    def test_check_json_reports_stable_fields(self):
        result = run_cli("check", "--json", FIXTURES / "narrowing.yl")
        self.assertEqual(result.returncode, 1)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["schemaVersion"], 1)
        self.assertEqual(payload["tool"], "YubaLANG")
        self.assertEqual(payload["summary"], {"errors": 1, "warnings": 0})
        diagnostic = payload["diagnostics"][0]
        self.assertEqual(diagnostic["code"], "type-mismatch")
        self.assertEqual(diagnostic["severity"], "error")
        self.assertEqual(diagnostic["line"], 2)
        self.assertEqual(diagnostic["column"], 1)
        self.assertEqual(diagnostic["endLine"], 2)
        self.assertGreater(diagnostic["endColumn"], 1)
        self.assertIn("list[int | none]", diagnostic["message"])

    def test_explain_prints_a_short_explanation_and_example(self):
        result = run_cli("explain", "type-mismatch")
        self.assertEqual(result.returncode, 0)
        self.assertIn("type-mismatch (error)", result.stdout)
        self.assertIn("Example:", result.stdout)

        missing = run_cli("explain", "no-such-code")
        self.assertEqual(missing.returncode, 1)
        self.assertIn("unknown diagnostic code", missing.stderr)


class NegativeFixtureTests(unittest.TestCase):
    def test_fixtures_cover_new_diagnostics(self):
        cases = json.loads((FIXTURES / "cases.json").read_text(encoding="utf-8"))
        covered = set()
        for case in cases:
            source = (FIXTURES / case["file"]).read_text(encoding="utf-8")
            diagnostics = analyze_document(source, strict=case.get("strict", False))
            codes = [item["code"] for item in diagnostics]
            with self.subTest(file=case["file"]):
                self.assertEqual(codes, case["codes"])
                covered.update(codes)
        self.assertIn("invalid-annotation", covered)
        self.assertIn("invalid-syntax", covered)
        self.assertIn("type-mismatch", covered)
        self.assertIn("unreachable-code", covered)
        self.assertIn("shadowed-variable", covered)


if __name__ == "__main__":
    unittest.main()
