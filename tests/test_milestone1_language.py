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


if __name__ == "__main__":
    unittest.main()
