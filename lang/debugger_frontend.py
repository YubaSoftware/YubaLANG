"""Interactive command frontend for the host-side debugger hooks."""

from dataclasses import dataclass, field
from typing import Callable

from .debugger import DebugEvent, Debugger


class DebuggerExit(Exception):
    """Raised when the user ends an interactive debug session."""


_HELP = {
    "break [source:]line": "Set a breakpoint.",
    "delete [source:]line": "Remove a breakpoint; with no argument, clear all.",
    "breakpoints": "List registered breakpoints.",
    "continue (c)": "Run until the next breakpoint or the end of the program.",
    "step (s)": "Step into the next executed statement.",
    "next (n)": "Step over the next statement.",
    "finish (f)": "Run until the current function returns.",
    "stack (bt)": "Show the call stack.",
    "vars": "Show locally visible variables.",
    "list [line]": "Show source around the current or requested line.",
    "quit (q)": "End the debug session without running the rest of the program.",
    "help (h)": "Show this command list.",
}


@dataclass
class DebuggerFrontend:
    """Drive a ``Debugger`` through a small interactive command loop.

    ``input_fn`` receives a prompt and returns one command line. Inject a
    different function for tests or editor integrations. ``output_fn``
    receives every line printed by the frontend so hosts can direct the
    debugger UI somewhere other than the program's standard output.
    """

    debugger: Debugger
    input_fn: Callable[[str], str] = input
    output_fn: Callable[[str], None] = print
    source_loader: Callable[[str], list[str] | None] | None = None
    event: DebugEvent | None = field(default=None, init=False)

    def on_stop(self, event: DebugEvent) -> None:
        """Handle one debugger stop and return after choosing the next action."""
        self.event = event
        self.output_fn(
            f"Stopped at {event.source_name}:{event.line_number} "
            f"({event.reason}, depth {event.function_depth})"
        )
        while True:
            try:
                command = self.input_fn("(yuda) ").strip()
            except EOFError:
                self.debugger.continue_execution()
                return
            action = self._handle_command(command)
            if action is not None:
                action()
                return

    def _handle_command(self, command: str) -> Callable[[], None] | None:
        if not command:
            return self.debugger.step_into
        name, _, argument = command.partition(" ")
        argument = argument.strip()
        name = name.lower()

        if name in ("help", "h", "?"):
            self._show_help()
        elif name in ("continue", "c"):
            return self.debugger.continue_execution
        elif name in ("step", "s"):
            return self.debugger.step_into
        elif name in ("next", "n"):
            return self.debugger.step_over
        elif name in ("finish", "f"):
            return self.debugger.step_out
        elif name in ("quit", "q"):
            raise DebuggerExit()
        elif name in ("stack", "bt", "where"):
            self._show_stack()
        elif name in ("vars", "variables", "p"):
            self._show_variables()
        elif name in ("list", "l"):
            self._show_source(argument)
        elif name in ("break", "b"):
            self._add_breakpoint(argument)
        elif name in ("delete", "d"):
            self._remove_breakpoint(argument)
        elif name in ("breakpoints", "bl"):
            self._show_breakpoints()
        else:
            self.output_fn(
                f"Unknown debugger command '{name}'. Type 'help' for commands."
            )
        return None

    def _show_help(self) -> None:
        for command, description in _HELP.items():
            self.output_fn(f"  {command:<24} {description}")

    def _show_stack(self) -> None:
        if self.event is None:
            return
        for frame in self.event.stack:
            self.output_fn(
                f"  {frame.function} at {frame.source_name}:{frame.line_number}"
            )
        self.output_fn(
            f"  <current> at {self.event.source_name}:{self.event.line_number}"
        )

    def _show_variables(self) -> None:
        if self.event is None:
            return
        if not self.event.variables:
            self.output_fn("  (no visible variables)")
            return
        for name in sorted(self.event.variables):
            self.output_fn(f"  {name} = {self.event.variables[name]!r}")

    def _show_source(self, argument: str) -> None:
        if self.event is None:
            return
        source_name = self.event.source_name
        line_number = self.event.line_number
        parsed = self._parse_location(argument)
        if parsed is not None and parsed[0] is not None:
            source_name = parsed[0]
        if parsed is not None:
            line_number = parsed[1]
        lines = None
        if self.source_loader is not None:
            lines = self.source_loader(source_name)
        if lines is None:
            self.output_fn(f"  Source is not available for {source_name}.")
            return
        start = max(1, line_number - 2)
        end = min(len(lines), line_number + 2)
        for current in range(start, end + 1):
            marker = ">" if current == line_number else " "
            self.output_fn(f"{marker} {current:>4} {lines[current - 1].rstrip()}")

    def _add_breakpoint(self, argument: str) -> None:
        if self.event is None:
            return
        parsed = self._parse_location(argument)
        if parsed is None:
            self.output_fn("Usage: break [source:]line")
            return
        source_name, line_number = parsed
        if source_name is None:
            source_name = self.event.source_name
        self.debugger.add_breakpoint(line_number, source_name)
        self.output_fn(f"Breakpoint set at {source_name}:{line_number}")

    def _remove_breakpoint(self, argument: str) -> None:
        if not argument:
            self.debugger.clear_breakpoints()
            self.output_fn("All breakpoints cleared.")
            return
        parsed = self._parse_location(argument)
        if parsed is None:
            self.output_fn("Usage: delete [source:]line")
            return
        source_name, line_number = parsed
        if source_name is None and self.event is not None:
            source_name = self.event.source_name
        if self.debugger.remove_breakpoint(line_number, source_name):
            self.output_fn(
                f"Breakpoint removed at {source_name or '<current>'}:{line_number}"
            )
        else:
            self.output_fn(f"No breakpoint at {source_name or '<current>'}:{line_number}.")

    def _show_breakpoints(self) -> None:
        breakpoints = self.debugger.breakpoints
        if not breakpoints:
            self.output_fn("No breakpoints.")
            return
        for source_name, line_number in breakpoints:
            self.output_fn(f"  {source_name or '<all files>'}:{line_number}")

    def _parse_location(self, argument: str) -> tuple[str | None, int] | None:
        if not argument:
            return None
        source_name: str | None = None
        line_source = argument
        if ":" in argument:
            candidate, _, remainder = argument.rpartition(":")
            if candidate and remainder:
                source_name, line_source = candidate, remainder
        try:
            line_number = int(line_source)
        except ValueError:
            return None
        if line_number < 1:
            return None
        return source_name, line_number
