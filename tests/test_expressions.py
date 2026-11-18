import contextlib
import io
import unittest

from lang.expressions import evaluate_expression, parse_expression
from lang.interpreter import Runtime, execute_lines
from lang.lsp import analyze_document
from lang.syntax import parse_program
from lang.typecheck import check_types


class ExpressionTests(unittest.TestCase):
    def test_precedence_parentheses_and_associativity(self):
        runtime = Runtime()
        self.assertEqual(evaluate_expression("1 + 2 * 3", runtime), 7)
        self.assertEqual(evaluate_expression("(1 + 2) * 3", runtime), 9)
        self.assertEqual(evaluate_expression("2 ** 3 ** 2", runtime), 512)
        self.assertEqual(evaluate_expression("-2 ** 2", runtime), -4)

    def test_boolean_operators_short_circuit_and_require_booleans(self):
        runtime = Runtime()
        self.assertFalse(evaluate_expression("false and missing", runtime))
        self.assertTrue(evaluate_expression("true or missing", runtime))
        with self.assertRaisesRegex(TypeError, "boolean operands"):
            evaluate_expression("1 and true", runtime)

    def test_only_supported_expression_syntax_is_accepted(self):
        for source in (
            "1 if true else 0",
            "x.y",
            "values[0]",
            "f(*args)",
            "f(**kwargs)",
            "(f() for x in values)",
            "range()",
            "range(1, 2, 3, 4)",
            "range(start=1)",
        ):
            with self.subTest(source=source), self.assertRaises(SyntaxError):
                parse_expression(source)

    def test_function_calls_are_supported_in_expressions(self):
        output = io.StringIO()
        source = [
            "func define double value:int -> int",
            "    return value * 2",
            "endfunc",
            "define var total: int = double(3) + double(4)",
            "define var named: int = double(value=5)",
            "text output double(total)",
            "define var squares: list[int] = [double(x) for x in range(3)]",
            "text output squares",
        ]
        with contextlib.redirect_stdout(output):
            execute_lines(source, source_name="calls.yl")

        self.assertEqual(output.getvalue(), "28\n[0, 2, 4]\n")

    def test_expression_calls_report_missing_functions_and_arguments(self):
        runtime = Runtime()
        with self.assertRaisesRegex(ValueError, "is not defined"):
            evaluate_expression("missing(1)", runtime)
        execute_lines(
            [
                "func define greet name",
                "    return name",
                "endfunc",
            ],
            runtime,
        )
        with self.assertRaisesRegex(TypeError, "expects 1 argument"):
            evaluate_expression("greet()", runtime)

    def test_static_checker_infers_expression_call_results(self):
        self.assertEqual(
            check_types(
                [
                    "func define double value:int -> int",
                    "    return value * 2",
                    "endfunc",
                    'define var invalid: string = ""',
                    "set invalid = double(2)",
                ]
            ),
            [(4, "Type mismatch: assignment has type 'int' but variable "
                 "'invalid' has type 'string'.")],
        )

    def test_f_strings_and_list_comprehensions(self):
        runtime = Runtime()
        runtime.define_var("name", "string", "Terps")
        runtime.define_var("numbers", "list", [1, 2, 3, 4])
        runtime.define_var("count", "int", 7)
        self.assertEqual(
            evaluate_expression('f"Hello, {name}!"', runtime),
            "Hello, Terps!",
        )
        self.assertEqual(
            evaluate_expression('f"{name!r}: {count:02d}"', runtime),
            "'Terps': 07",
        )
        self.assertEqual(
            evaluate_expression("[number * number for number in range(5)]", runtime),
            [0, 1, 4, 9, 16],
        )
        self.assertEqual(
            evaluate_expression(
                "[number for number in numbers if number % 2 == 0]", runtime
            ),
            [2, 4],
        )
        self.assertIsNone(runtime.get_var("number"))

    def test_f_strings_and_comprehensions_work_in_programs(self):
        output = io.StringIO()
        source = [
            'define var name: string = "Terps"',
            "define var squares: list[int] = [x * x for x in range(4)]",
            'text output f"Hello, {name}!"',
            "text output squares",
        ]
        with contextlib.redirect_stdout(output):
            execute_lines(source, source_name="expressions.yl")
        self.assertEqual(output.getvalue(), "Hello, Terps!\n[0, 1, 4, 9]\n")

    def test_command_parser_keeps_source_locations(self):
        nodes = parse_program(
            ["", "    text output value # comment"],
            source_name="sample.yl",
            line_numbers=[10, 11],
        )
        self.assertEqual(len(nodes), 1)
        self.assertEqual(nodes[0].tokens, ("text", "output", "value"))
        self.assertEqual(nodes[0].location.source_name, "sample.yl")
        self.assertEqual(nodes[0].location.line, 11)
        self.assertEqual(nodes[0].location.column, 5)

    def test_declarations_assignment_output_comparisons_and_returns(self):
        output = io.StringIO()
        source = [
            "define var base: int = 2",
            "define var result: int = base * 3 + 1",
            "set result = (result - 1) ** 2",
            "text output result",
            "define var passed: bool = false",
            "compare result >= 36 and not false passed",
            "if passed",
            "    text output 'passed'",
            "endif",
            "func define calculate value:int -> int",
            "    return value * value",
            "endfunc",
            "define var square: int = 0",
            "func call calculate 5 -> square",
            "text output square",
        ]
        with contextlib.redirect_stdout(output):
            execute_lines(source, source_name="expressions.yl")

        self.assertEqual(output.getvalue(), "36\npassed\n25\n")

    def test_assignment_enforces_declared_type_and_existing_target(self):
        for source, message in (
            (["define var count: int = 1", "set count = true"], "Cannot assign"),
            (["set count = 1"], "is not defined"),
        ):
            output = io.StringIO()
            with self.subTest(source=source):
                with contextlib.redirect_stdout(output), self.assertRaises(SystemExit):
                    execute_lines(source, source_name="assignment.yl")
            self.assertIn(message, output.getvalue())

    def test_control_conditions_must_be_boolean(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output), self.assertRaises(SystemExit):
            execute_lines(["if 1", "endif"], source_name="condition.yl")
        self.assertIn("Condition must evaluate to a boolean.", output.getvalue())

    def test_language_server_parses_new_expression_forms(self):
        self.assertEqual(
            analyze_document(
                "define var value: int = 0\n"
                "set value = (2 + 3) * 4\n"
                "define var squares: list[int] = [x * x for x in range(5)]\n"
                'define var greeting: string = f"Value: {value}"\n'
                "if value >= 20 and not false\n"
                "    text output value\n"
                "endif\n"
            ),
            [],
        )
        diagnostics = analyze_document(
            "define var value: int = 0\n"
            "set value = 1 if true else 0\n"
        )
        self.assertTrue(any("Unsupported syntax" in item["message"] for item in diagnostics))
        self.assertEqual(
            analyze_document(
                "func define double value:int -> int\n"
                "    return value * 2\n"
                "endfunc\n"
                "define var total: int = double(2) + 1\n"
            ),
            [],
        )

    def test_static_checker_infers_expression_results(self):
        diagnostics = analyze_document(
            "define var count: int = 1\n"
            "set count = count + 2\n"
            "define var label: string = ''\n"
            "set label = count * 2\n"
            "if count\n"
            "endif\n"
        )
        messages = [item["message"] for item in diagnostics]
        self.assertEqual(len(messages), 2)
        self.assertTrue(any("assignment has type 'int'" in item for item in messages))
        self.assertTrue(any("condition has type 'int'" in item for item in messages))


if __name__ == "__main__":
    unittest.main()
