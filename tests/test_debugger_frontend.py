import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from lang.debugger import Debugger
from lang.debugger_frontend import DebuggerExit, DebuggerFrontend
from lang.interpreter import execute_lines
from lang.runtime import Runtime


REPOSITORY_ROOT = Path(__file__).resolve().parent.parent
ENTRY_POINT = REPOSITORY_ROOT / "YubaLANG.py"


class ScriptedInput:
    def __init__(self, commands: list[str]) -> None:
        self.commands = list(commands)
        self.prompts: list[str] = []

    def __call__(self, prompt: str) -> str:
        self.prompts.append(prompt)
        if not self.commands:
            raise EOFError
        return self.commands.pop(0)


def attach_frontend(
    commands: list[str], sources: dict[str, list[str]] | None = None
) -> tuple[Debugger, DebuggerFrontend, list[str]]:
    lines: list[str] = []
    debugger = Debugger(lambda event: frontend.on_stop(event))
    frontend = DebuggerFrontend(
        debugger,
        input_fn=ScriptedInput(commands),
        output_fn=lines.append,
        source_loader=(sources or {}).get,
    )
    return debugger, frontend, lines


class DebuggerFrontendTests(unittest.TestCase):
    def test_breakpoint_inspection_and_stepping(self):
        debugger, _, lines = attach_frontend(
            ["vars", "stack", "step", "continue"]
        )
        debugger.add_breakpoint(3)
        execute_lines(
            [
                "define var count: int = 0",
                "func define increment",
                "    set count = count + 1",
                "endfunc",
                "func call increment",
                "set count = count",
            ],
            Runtime(debugger=debugger),
        )
        output = "\n".join(lines)
        self.assertIn("Stopped at <memory>:3 (breakpoint, depth 1)", output)
        self.assertIn("count = 0", output)
        self.assertIn("increment at <memory>", output)
        self.assertIn("Stopped at <memory>:6 (step, depth 0)", output)

    def test_help_list_unknown_commands_and_quit(self):
        debugger, _, lines = attach_frontend(
            ["help", "list", "bogus", "quit"],
            {"sample.yl": ["define var count: int = 0", "text output count"]},
        )
        debugger.add_breakpoint(1, "sample.yl")
        with self.assertRaises(DebuggerExit):
            execute_lines(
                ["define var count: int = 0", "text output count"],
                Runtime(debugger=debugger),
                "sample.yl",
            )
        output = "\n".join(lines)
        self.assertIn("continue (c)", output)
        self.assertIn(">    1 define var count: int = 0", output)
        self.assertIn("Unknown debugger command 'bogus'", output)

    def test_breakpoints_can_be_added_removed_and_cleared(self):
        debugger, _, lines = attach_frontend(
            [
                "break 3",
                "breakpoints",
                "delete 3",
                "breakpoints",
                "delete",
                "breakpoints",
                "continue",
            ]
        )
        debugger.add_breakpoint(1)
        execute_lines(["define var count: int = 1"], Runtime(debugger=debugger))
        output = "\n".join(lines)
        self.assertIn("Breakpoint set at <memory>:3", output)
        self.assertIn("<memory>:3", output)
        self.assertIn("Breakpoint removed at <memory>:3", output)
        self.assertIn("All breakpoints cleared.", output)
        self.assertIn("No breakpoints.", output)

    def test_eof_continues_execution(self):
        debugger, _, lines = attach_frontend([])
        debugger.add_breakpoint(1)
        execute_lines(
            ["define var count: int = 1", "text output count"],
            Runtime(debugger=debugger),
        )
        self.assertIn("Stopped at <memory>:1", "\n".join(lines))


class DebuggerCliTests(unittest.TestCase):
    def test_cli_debug_stops_inspects_and_continues(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "program.yl"
            source.write_text(
                "define var count: int = 0\n"
                "set count = count + 1\n"
                "text output count\n",
                encoding="utf-8",
            )
            result = subprocess.run(
                [
                    sys.executable,
                    str(ENTRY_POINT),
                    "debug",
                    "--break",
                    "2",
                    str(source),
                ],
                input="vars\ncontinue\n",
                capture_output=True,
                text=True,
                encoding="utf-8",
                check=False,
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "1\n")
        self.assertIn("Stopped at", result.stderr)
        self.assertIn("count = 0", result.stderr)

    def test_cli_debug_quit_leaves_program_unfinished(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "program.yl"
            source.write_text(
                "define var count: int = 0\n"
                'text output "should not run"\n',
                encoding="utf-8",
            )
            result = subprocess.run(
                [
                    sys.executable,
                    str(ENTRY_POINT),
                    "debug",
                    "--break",
                    "1",
                    str(source),
                ],
                input="quit\n",
                capture_output=True,
                text=True,
                encoding="utf-8",
                check=False,
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "")
        self.assertIn("Debug session ended.", result.stderr)

    def test_debug_requires_a_source_file_and_valid_breakpoints(self):
        result = subprocess.run(
            [sys.executable, str(ENTRY_POINT), "debug"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("Usage: py YubaLANG.py debug", result.stderr)

        result = subprocess.run(
            [
                sys.executable,
                str(ENTRY_POINT),
                "debug",
                "--break",
                "not-a-line",
                "program.yl",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("invalid breakpoint", result.stderr)


if __name__ == "__main__":
    unittest.main()
