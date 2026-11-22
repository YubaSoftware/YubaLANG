"""Parsing and unpacking for identifier, destructuring, and match patterns."""

import ast
import re
from dataclasses import dataclass
from typing import Any

from .runtime import EnumValue, Runtime


_LITERALS = {"true": "True", "false": "False", "none": "None"}
_ENUM_PATTERN = re.compile(
    r"^(?P<type>[A-Za-z_]\w*)\.(?P<variant>[A-Za-z_]\w*)"
    r"(?:\((?P<payload>.*)\))?$",
    re.S,
)


@dataclass(frozen=True)
class LiteralPattern:
    value: Any


@dataclass(frozen=True)
class WildcardPattern:
    pass


@dataclass(frozen=True)
class TuplePattern:
    items: tuple["Pattern", ...]


@dataclass(frozen=True)
class EnumPattern:
    enum_type: str
    variant: str
    bindings: tuple[str | None, ...]


@dataclass(frozen=True)
class TypePattern:
    type_name: str


@dataclass(frozen=True)
class BindingPattern:
    name: str


Pattern = (
    LiteralPattern | WildcardPattern | TuplePattern | EnumPattern
    | TypePattern | BindingPattern
)


def parse_pattern(source: str, label: str = "pattern") -> ast.expr:
    """Parse an identifier or tuple/list destructuring target."""
    try:
        node = ast.parse(source, mode="eval").body
    except SyntaxError as error:
        raise SyntaxError(f"Invalid {label}: {error.msg}.") from error

    def check(item: ast.expr) -> None:
        if isinstance(item, ast.Name):
            return
        if isinstance(item, (ast.Tuple, ast.List)):
            for element in item.elts:
                check(element)
            return
        raise SyntaxError(
            f"{label.capitalize()} must contain only identifiers."
        )

    check(node)
    return node


def pattern_names(node: ast.expr) -> list[str]:
    if isinstance(node, ast.Name):
        return [node.id]
    if not isinstance(node, (ast.Tuple, ast.List)):
        raise SyntaxError("Destructuring targets must be identifiers or sequences.")
    names: list[str] = []
    for element in node.elts:
        names.extend(pattern_names(element))
    return names


def unpack_pattern(node: ast.expr, value: Any) -> list[tuple[str, Any]]:
    if isinstance(node, ast.Name):
        return [(node.id, value)]
    if not isinstance(node, (ast.Tuple, ast.List)):
        raise SyntaxError("Destructuring targets must be identifiers or sequences.")
    if not isinstance(value, (list, tuple)):
        raise TypeError("Cannot destructure a non-sequence value.")
    if len(value) != len(node.elts):
        raise ValueError(
            f"Cannot unpack {len(node.elts)} value(s) from a sequence of "
            f"length {len(value)}."
        )
    result: list[tuple[str, Any]] = []
    for element, item in zip(node.elts, value):
        result.extend(unpack_pattern(element, item))
    return result


def _normalize_literals(source: str) -> str:
    result: list[str] = []
    quote: str | None = None
    escaped = False
    for character in source:
        if quote is not None:
            result.append(character)
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == quote:
                quote = None
            continue
        if character in ("'", '"'):
            quote = character
            result.append(character)
            continue
        result.append(character)
    normalized = "".join(result)
    for name, replacement in _LITERALS.items():
        normalized = re.sub(rf"\b{name}\b", replacement, normalized)
    return normalized


def split_top_level(source: str) -> list[str]:
    """Split comma-separated items, ignoring nested brackets and quotes."""
    items: list[str] = []
    depth = 0
    current: list[str] = []
    quote: str | None = None
    escaped = False
    for character in source:
        if quote is not None:
            current.append(character)
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == quote:
                quote = None
            continue
        if character in ("'", '"'):
            quote = character
            current.append(character)
        elif character in "([":
            depth += 1
            current.append(character)
        elif character in ")]":
            depth -= 1
            current.append(character)
        elif character == "," and depth == 0:
            items.append("".join(current).strip())
            current = []
        else:
            current.append(character)
    if "".join(current).strip():
        items.append("".join(current).strip())
    return items


def parse_match_pattern(source: str, runtime: Runtime):
    """Parse a ``match``/``case`` pattern against the registered types."""
    source = source.strip()
    if not source:
        raise SyntaxError("A case pattern cannot be empty.")
    if source == "_":
        return WildcardPattern()
    enum_match = _ENUM_PATTERN.match(source)
    if enum_match is not None:
        enum_type = enum_match.group("type")
        variant = enum_match.group("variant")
        if enum_type in runtime.enums:
            definition = runtime.enums[enum_type]
            if variant not in definition.variants:
                raise ValueError(
                    f"Enum '{enum_type}' has no variant named '{variant}'."
                )
            payload = enum_match.group("payload")
            bindings: list[str | None] = []
            if payload is not None:
                for item in split_top_level(payload):
                    if item == "_":
                        bindings.append(None)
                    elif item.isidentifier():
                        bindings.append(item)
                    else:
                        raise SyntaxError(
                            "Enum payload patterns must be identifiers or '_'."
                        )
            declared = definition.variants[variant].fields
            if len(bindings) != len(declared):
                raise ValueError(
                    f"Enum variant '{enum_type}.{variant}' pattern binds "
                    f"{len(bindings)} value(s) but the variant has "
                    f"{len(declared)} field(s)."
                )
            return EnumPattern(enum_type, variant, tuple(bindings))
    if source.isidentifier() and runtime.type_is_known(source):
        return TypePattern(source)
    try:
        node = ast.parse(
            _normalize_literals(source), mode="eval"
        ).body
    except SyntaxError as error:
        raise SyntaxError(f"Invalid case pattern: {error.msg}.") from error

    def build(item: ast.expr) -> Pattern:
        if isinstance(item, ast.Constant):
            return LiteralPattern(item.value)
        if isinstance(item, ast.UnaryOp) and isinstance(item.op, ast.USub):
            operand = item.operand
            if isinstance(operand, ast.Constant) and isinstance(
                operand.value, (int, float)
            ):
                return LiteralPattern(-operand.value)
        if isinstance(item, ast.Name) and item.id == "_":
            return WildcardPattern()
        if isinstance(item, ast.Name) and runtime.type_is_known(item.id):
            return TypePattern(item.id)
        if isinstance(item, ast.Name):
            return BindingPattern(item.id)
        if isinstance(item, (ast.Tuple, ast.List)):
            return TuplePattern(tuple(build(element) for element in item.elts))
        raise SyntaxError(
            "Case patterns support literals, tuples, type names, and enum variants."
        )

    return build(node)


def match_case_pattern(
    pattern: Pattern, value: Any, runtime: Runtime
) -> dict[str, Any] | None:
    """Return bindings when ``value`` matches, otherwise ``None``."""
    if isinstance(pattern, WildcardPattern):
        return {}
    if isinstance(pattern, BindingPattern):
        return {pattern.name: value}
    if isinstance(pattern, LiteralPattern):
        return {} if pattern.value == value else None
    if isinstance(pattern, TypePattern):
        return {} if runtime.value_matches_type(pattern.type_name, value) else None
    if isinstance(pattern, EnumPattern):
        if (
            not isinstance(value, EnumValue)
            or value.enum_type != pattern.enum_type
            or value.variant != pattern.variant
        ):
            return None
        bindings: dict[str, Any] = {}
        for name, item in zip(pattern.bindings, value.fields):
            if name is not None:
                bindings[name] = item
        return bindings
    if isinstance(pattern, TuplePattern):
        if not isinstance(value, (list, tuple)):
            return None
        if len(value) != len(pattern.items):
            return None
        bindings = {}
        for item_pattern, item in zip(pattern.items, value):
            matched = match_case_pattern(item_pattern, item, runtime)
            if matched is None:
                return None
            bindings.update(matched)
        return bindings
    raise TypeError("Unsupported case pattern.")
