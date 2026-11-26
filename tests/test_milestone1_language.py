import contextlib
import io
import unittest

from lang.interpreter import execute_lines


def run(source):
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        execute_lines(source, source_name="milestone1.yl")
    return output.getvalue()


class ForEachLoopTests(unittest.TestCase):
    def test_iterates_values_without_an_index(self):
        self.assertEqual(
            run([
                "define var numbers: list[int] = [1, 2, 3]",
                "define var total: int = 0",
                "loop for number in numbers",
                "    set total = total + number",
                "endloop",
                "text output total",
            ]),
            "6\n",
        )

    def test_iterates_strings_sets_and_dict_keys(self):
        self.assertEqual(
            run([
                'define var word: string = "ab"',
                "define var letters: list[string] = []",
                "loop for letter in word",
                "    letters.append(letter)",
                "endloop",
                "text output letters",
                "define var mapping: dict[string, int] = {'a': 1, 'b': 2}",
                "define var keys: list[string] = []",
                "loop for key in mapping",
                "    keys.append(key)",
                "endloop",
                "text output keys",
            ]),
            "['a', 'b']\n['a', 'b']\n",
        )

    def test_destructures_tuple_values(self):
        self.assertEqual(
            run([
                'define var pairs: list[tuple[int, string]] = [(1, "a"), (2, "b")]',
                "define var labels: list[string] = []",
                "loop for (number, label) in pairs",
                "    labels.append(f'{number}:{label}')",
                "endloop",
                "text output labels",
            ]),
            "['1:a', '2:b']\n",
        )

    def test_break_and_continue_match_count_loops(self):
        self.assertEqual(
            run([
                "define var numbers: list[int] = [1, 2, 3, 4, 5]",
                "define var total: int = 0",
                "loop for number in numbers",
                "    if number == 2",
                "        continue",
                "    endif",
                "    if number == 4",
                "        break",
                "    endif",
                "    set total = total + number",
                "endloop",
                "text output total",
            ]),
            "4\n",
        )

    def test_count_form_is_unchanged(self):
        self.assertEqual(
            run([
                "define var total: int = 0",
                "loop for 3",
                "    set total = total + 1",
                "endloop",
                "text output total",
            ]),
            "3\n",
        )

    def test_rejects_non_iterable_values(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output), self.assertRaises(SystemExit):
            execute_lines(
                ["loop for item in 5", "endloop"], source_name="loop.yl"
            )
        self.assertIn("requires an iterable value", output.getvalue())


class DestructuringTests(unittest.TestCase):
    def test_declaration_and_assignment(self):
        self.assertEqual(
            run([
                'define var pair: tuple[int, string] = (2, "two")',
                "define var (number, label): tuple[int, string] = pair",
                "text output number",
                "text output label",
                'define var other: tuple[int, string] = (3, "three")',
                "set (number, label) = other",
                "text output number",
                "text output label",
            ]),
            "2\ntwo\n3\nthree\n",
        )

    def test_list_destructuring_and_element_types(self):
        self.assertEqual(
            run([
                "define var values: list[int] = [4, 5]",
                "define var (left, right): list[int] = values",
                "text output left + right",
            ]),
            "9\n",
        )

    def test_reports_arity_and_non_sequence_errors(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output), self.assertRaises(SystemExit):
            execute_lines(
                [
                    "define var values: list[int] = [1, 2]",
                    "define var (left, right, third): list[int] = values",
                ],
                source_name="destructure.yl",
            )
        self.assertIn("Cannot unpack", output.getvalue())

        output = io.StringIO()
        with contextlib.redirect_stdout(output), self.assertRaises(SystemExit):
            execute_lines(
                [
                    "define var value: int = 1",
                    "define var (left, right): tuple[int, int] = value",
                ],
                source_name="destructure.yl",
            )
        self.assertIn("Cannot destructure", output.getvalue())


class EnumAndMatchTests(unittest.TestCase):
    def test_enum_construction_display_equality_and_annotation(self):
        self.assertEqual(
            run([
                "enum define Result ok(value: int) error(message: string) pending",
                "enum value Result.pending pending",
                "enum create Result.ok result 42",
                "enum create Result.ok same 42",
                "text output result",
                "text output result == same",
                "text output pending",
                "define var copy: Result = result",
                "text output copy",
            ]),
            "Result.ok(42)\nTrue\nResult.pending\nResult.ok(42)\n",
        )

    def test_enum_payload_type_check_and_unknown_variant(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output), self.assertRaises(SystemExit):
            execute_lines(
                [
                    "enum define Result ok(value: int)",
                    'enum create Result.ok result "no"',
                ],
                source_name="enum.yl",
            )
        self.assertIn("requires type 'int'", output.getvalue())

        output = io.StringIO()
        with contextlib.redirect_stdout(output), self.assertRaises(SystemExit):
            execute_lines(
                ["enum define Result ok", "enum create Result.missing result"],
                source_name="enum.yl",
            )
        self.assertIn("has no variant named 'missing'", output.getvalue())

    def test_match_binds_enum_payloads_and_falls_back(self):
        self.assertEqual(
            run([
                "enum define Result ok(value: int) error(message: string)",
                "enum create Result.error result 'boom'",
                "match result",
                "    case Result.ok(value)",
                "        text output f'ok {value}'",
                "    case Result.error(message)",
                "        text output f'error {message}'",
                "    else",
                "        text output 'never'",
                "endmatch",
            ]),
            "error boom\n",
        )

    def test_match_supports_literals_tuples_and_type_patterns(self):
        self.assertEqual(
            run([
                "match (1, 'a')",
                "    case (int, string)",
                "        text output 'typed tuple'",
                "    case (left, right)",
                "        text output f'{left}{right}'",
                "endmatch",
                "match 7",
                "    case 8",
                "        text output 'eight'",
                "    case int",
                "        text output 'integer'",
                "endmatch",
                "match none",
                "    case none",
                "        text output 'nothing'",
                "endmatch",
            ]),
            "typed tuple\ninteger\nnothing\n",
        )

    def test_match_without_a_matching_case_reports_non_exhaustive(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output), self.assertRaises(SystemExit):
            execute_lines(
                [
                    "enum define Result ok(value: int) error(message: string)",
                    "enum create Result.error result 'boom'",
                    "match result",
                    "    case Result.ok(value)",
                    "        text output value",
                    "endmatch",
                ],
                source_name="match.yl",
            )
        self.assertIn("match is not exhaustive", output.getvalue())
        self.assertIn("[non-exhaustive-match]", output.getvalue())

    def test_static_checker_reports_non_exhaustive_enum_matches(self):
        from lang.typecheck import check_types

        diagnostics = check_types([
            "enum define Color red green blue",
            "define var color: Color = selected",
            "match color",
            "    case Color.red",
            "        text output 'r'",
            "    case Color.green",
            "        text output 'g'",
            "endmatch",
        ])
        self.assertEqual(len(diagnostics), 1)
        self.assertIn("blue", diagnostics[0][1])

    def test_static_checker_treats_binding_and_wildcard_cases_as_exhaustive(self):
        from lang.typecheck import check_types

        self.assertEqual(
            check_types([
                "enum define Color red green",
                "define var color: Color = selected",
                "match color",
                "    case Color.red",
                "        text output 'r'",
                "    case other",
                "        text output other",
                "endmatch",
                "match color",
                "    case _",
                "        text output 'any'",
                "endmatch",
            ]),
            [],
        )

    def test_language_server_accepts_enum_and_match_syntax(self):
        from lang.lsp import analyze_document

        source = "\n".join([
            "enum define Result ok(value: int) error(message: string)",
            "enum create Result.ok result 1",
            "match result",
            "    case Result.ok(value)",
            "        text output value",
            "    case Result.error(message)",
            "        text output message",
            "endmatch",
        ])
        self.assertEqual(analyze_document(source), [])


class TypeAliasTests(unittest.TestCase):
    def test_aliases_work_in_annotations_collections_and_unions(self):
        self.assertEqual(
            run([
                "type define Number = int | float",
                "type define Names = list[string]",
                "define var total: Number = 1",
                "set total = 2.5",
                "define var names: Names = ['a', 'b']",
                "text output total",
                "text output names",
            ]),
            "2.5\n['a', 'b']\n",
        )

    def test_unknown_alias_target_is_rejected(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output), self.assertRaises(SystemExit):
            execute_lines(
                ["type define Broken = missing"], source_name="alias.yl"
            )
        self.assertIn("Unknown type: missing", output.getvalue())

    def test_self_referential_alias_is_rejected(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output), self.assertRaises(SystemExit):
            execute_lines(
                ["type define Loop = list[Loop]"], source_name="alias.yl"
            )
        self.assertIn("refers to itself", output.getvalue())

    def test_static_checker_expands_aliases(self):
        from lang.typecheck import check_types_detailed

        diagnostics = check_types_detailed(
            [
                "type define Number = int | float",
                "define var total: Number = 1",
                "func define double value:Number -> Number",
                "    return value * 2",
                "endfunc",
                "record define Box value:Number",
                "record create Box box 1",
            ],
            strict=True,
        )
        self.assertEqual(diagnostics, [])

        mismatches = check_types_detailed(
            [
                "type define Age = int",
                'define var age: Age = "old"',
            ]
        )
        self.assertEqual(len(mismatches), 1)
        self.assertIn("declares 'int'", mismatches[0].message)


class ConstantAndImmutableTests(unittest.TestCase):
    def test_constant_declarations_reject_reassignment(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output), self.assertRaises(SystemExit):
            execute_lines(
                [
                    "define const limit: int = 3",
                    "set limit = 4",
                ],
                source_name="constant.yl",
            )
        self.assertIn("Cannot reassign constant 'limit'", output.getvalue())
        self.assertIn("[constant-reassignment]", output.getvalue())

    def test_destructuring_constants_and_compound_reassignment(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output), self.assertRaises(SystemExit):
            execute_lines(
                [
                    "define const (left, right): tuple[int, int] = (1, 2)",
                    "set left += 1",
                ],
                source_name="constant.yl",
            )
        self.assertIn("Cannot reassign constant 'left'", output.getvalue())

    def test_immutable_record_fields_reject_mutation(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output), self.assertRaises(SystemExit):
            execute_lines(
                [
                    "record define Point const x:int y:int",
                    "record create Point point 1 2",
                    "setattr point x 5",
                ],
                source_name="record.yl",
            )
        self.assertIn("is immutable", output.getvalue())

        self.assertEqual(
            run([
                "record define Point const x:int y:int",
                "record create Point point 1 2",
                "setattr point y 5",
                "text output point.x + point.y",
            ]),
            "6\n",
        )

    def test_static_checker_reports_constant_reassignment(self):
        from lang.typecheck import check_types_detailed

        diagnostics = check_types_detailed([
            "define const limit: int = 3",
            "set limit = 4",
        ])
        self.assertTrue(
            any(
                diagnostic.code == "constant-reassignment"
                for diagnostic in diagnostics
            )
        )


class CompoundAssignmentTests(unittest.TestCase):
    def test_compound_assignment_operators(self):
        self.assertEqual(
            run([
                "define var number: int = 1",
                "set number += 2",
                "set number *= 3",
                "set number -= 1",
                "text output number",
                "define var bits: int = 6",
                "set bits &= 3",
                "set bits |= 8",
                "set bits ^= 1",
                "set bits <<= 1",
                "set bits >>= 1",
                "text output bits",
                'define var text_value: string = "a"',
                'set text_value += "b"',
                "text output text_value",
            ]),
            "8\n11\nab\n",
        )

    def test_compound_assignment_keeps_declared_type(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output), self.assertRaises(SystemExit):
            execute_lines(
                [
                    "define var count: int = 1",
                    "set count += 0.5",
                ],
                source_name="compound.yl",
            )
        self.assertIn("Cannot assign a float value", output.getvalue())


class LambdaTests(unittest.TestCase):
    def test_lambdas_are_values_and_expression_callbacks(self):
        self.assertEqual(
            run([
                "define var add: (int) -> int = lambda x: x + 1",
                "text output add(4)",
                "text output (lambda x: x * 2)(21)",
                "text output map(lambda x: x * 10, [1, 2, 3])",
                "text output filter(lambda x: x > 1, [1, 2, 3])",
                "text output sorted([3, 1, 2])",
                "text output sorted([3, 1, 2], reverse=true)",
            ]),
            "5\n42\n[10, 20, 30]\n[2, 3]\n[1, 2, 3]\n[3, 2, 1]\n",
        )

    def test_lambdas_can_be_used_by_command_callbacks(self):
        self.assertEqual(
            run([
                "define var values: list[int] = [1, 2, 3]",
                "define var scale: (int) -> int = lambda x: x * 10",
                "define var scaled: list[int] = []",
                "map scale values scaled",
                "text output scaled",
            ]),
            "[10, 20, 30]\n",
        )

    def test_lambda_arity_and_syntax_errors(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output), self.assertRaises(SystemExit):
            execute_lines(
                [
                    "define var add: (int) -> int = lambda x: x + 1",
                    "text output add(1, 2)",
                ],
                source_name="lambda.yl",
            )
        self.assertIn("expects 1 argument(s)", output.getvalue())


class OptionalChainTests(unittest.TestCase):
    def test_optional_access_calls_and_null_coalescing(self):
        self.assertEqual(
            run([
                "record define User name:string",
                "record create User user 'Ada'",
                "define var maybe: string | none = none",
                "define var present: string | none = 'yes'",
                "text output maybe ?: 'fallback'",
                "text output present ?: 'fallback'",
                "text output maybe?.upper()",
                "text output user?.name",
                "text output none?.name ?: 'missing'",
                "define var values: list[int] | none = none",
                "text output values?.[0]",
                "define var callback: ((int) -> int) | none = lambda x: x + 1",
                "text output callback?.(4)",
            ]),
            "fallback\nyes\nNone\nAda\nmissing\nNone\n5\n",
        )

    def test_null_coalescing_short_circuits_the_right_operand(self):
        self.assertEqual(
            run([
                "define var present: string | none = 'set'",
                "text output present ?: missing",
            ]),
            "set\n",
        )


if __name__ == "__main__":
    unittest.main()
