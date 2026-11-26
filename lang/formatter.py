"""Formatting utilities for YubaLANG source files."""

from .syntax import tokenize_line

class FormatError(ValueError):
    """Raised when source structure cannot be formatted safely."""


def format_source(source: str) -> str:
    """Return source formatted with four-space block indentation and one final newline."""
    blocks: list[tuple[str, int]] = []
    formatted: list[str] = []

    for line_number, line in enumerate(source.splitlines(), start=1):
        content = line.strip()
        if not content:
            formatted.append("")
            continue

        try:
            parts = tokenize_line(content)
        except SyntaxError as error:
            raise FormatError(f"line {line_number}: invalid command quoting: {error}") from error

        command = parts[0] if parts else ""
        is_exact_end = content in (
            "endfunc", "endloop", "endtry", "endmatch"
        )
        closing = command if command == "endif" or is_exact_end else ""

        if command in ("else", "elseif", "catch", "finally"):
            if command == "else" and blocks and blocks[-1][0] == "case":
                blocks.pop()
                if not blocks or blocks[-1][0] != "match":
                    raise FormatError(
                        f"line {line_number}: else without a matching block"
                    )
                indent = len(blocks)
                formatted.append("    " * indent + content)
                blocks.append(("case", line_number))
                continue
            expected = "try" if command in ("catch", "finally") else "if"
            if not blocks or blocks[-1][0] != expected:
                raise FormatError(f"line {line_number}: {command} without a matching {expected}")

        if command == "case":
            if blocks and blocks[-1][0] == "case":
                blocks.pop()
            if not blocks or blocks[-1][0] != "match":
                raise FormatError(
                    f"line {line_number}: case without a matching match"
                )
            formatted.append("    " * len(blocks) + content)
            blocks.append(("case", line_number))
            continue

        if closing:
            if closing == "endmatch" and blocks and blocks[-1][0] == "case":
                blocks.pop()
            expected = {
                "endif": "if", "endfunc": "func", "endloop": "loop",
                "endtry": "try", "endmatch": "match",
            }[closing]
            if not blocks or blocks[-1][0] != expected:
                raise FormatError(f"line {line_number}: {closing} without a matching block")
            blocks.pop()

        indent = len(blocks) - int(command in ("else", "elseif", "catch", "finally"))
        formatted.append("    " * max(indent, 0) + content)

        if command == "if":
            blocks.append(("if", line_number))
        elif command == "match":
            blocks.append(("match", line_number))
        elif command == "func" and (
            (len(parts) >= 3 and parts[1] == "define")
            or (
                len(parts) >= 4
                and parts[1:3] == ("private", "define")
            )
        ):
            blocks.append(("func", line_number))
        elif command == "loop" and len(parts) >= 3 and parts[1] in ("for", "while"):
            blocks.append(("loop", line_number))
        elif command == "try":
            blocks.append(("try", line_number))

    if blocks:
        block, line_number = blocks[-1]
        ending = {
            "if": "endif", "func": "endfunc", "loop": "endloop",
            "try": "endtry", "match": "endmatch", "case": "endmatch",
        }[block]
        raise FormatError(f"line {line_number}: missing {ending}")

    return "\n".join(formatted).rstrip("\n") + "\n"
