"""Enum declarations/construction and type-alias declarations."""

from typing import Any

from .expressions import evaluate_expression
from .patterns import split_top_level
from .runtime import EnumDefinition, EnumValue, EnumVariantDefinition, Runtime
from .type_system import format_type, parse_type


def _split_declarations(source: str) -> list[str]:
    """Split whitespace-separated variant declarations at bracket depth zero."""
    items: list[str] = []
    depth = 0
    current: list[str] = []
    for character in source:
        if character in "([":
            depth += 1
            current.append(character)
        elif character in ")]":
            depth -= 1
            current.append(character)
        elif character.isspace() and depth == 0:
            if current:
                items.append("".join(current))
                current = []
        else:
            current.append(character)
    if current:
        items.append("".join(current))
    return items


def _parse_variant(
    token: str, runtime: Runtime
) -> tuple[str, EnumVariantDefinition]:
    name, separator, payload = token.partition("(")
    if not name.isidentifier():
        raise SyntaxError(
            f"Enum variant '{token}' must start with an identifier."
        )
    if not separator:
        return name, EnumVariantDefinition()
    if not payload.endswith(")"):
        raise SyntaxError(
            f"Enum variant '{name}' has an unclosed payload declaration."
        )
    payload = payload[:-1]
    fields: list[tuple[str, str]] = []
    seen: set[str] = set()
    for declaration in split_top_level(payload):
        field_name, colon, field_type = declaration.partition(":")
        if not colon or not field_name.isidentifier() or not field_type.strip():
            raise SyntaxError(
                "Enum payload fields must use <name>:<type> syntax."
            )
        if field_name in seen:
            raise ValueError(
                f"Enum variant '{name}' has duplicate field '{field_name}'."
            )
        seen.add(field_name)
        try:
            spec = parse_type(field_type)
        except ValueError as error:
            raise ValueError(
                f"Invalid type for enum field '{field_name}': {error}"
            ) from error
        normalized = format_type(spec)
        if not runtime.type_is_known(normalized):
            raise ValueError(f"Unknown type: {normalized}")
        fields.append((field_name, normalized))
    return name, EnumVariantDefinition(fields)


def execute_enum_command(parts: list[str], runtime: Runtime) -> None:
    if len(parts) < 3:
        raise SyntaxError(
            "Usage: enum define <name> <variant>... or "
            "enum create <type>.<variant> <variable> [values]"
        )
    action = parts[1]
    if action == "define":
        if len(parts) < 4:
            raise SyntaxError("An enum must declare at least one variant.")
        name = parts[2]
        if not name.isidentifier():
            raise SyntaxError("Enum name must be an identifier.")
        if (
            name in runtime.enums or name in runtime.records
            or name in runtime.type_aliases or name in runtime.record_type_names
        ):
            raise ValueError(f"Enum type '{name}' is already defined.")
        definitions = _split_declarations(" ".join(parts[3:]))
        variants: dict[str, EnumVariantDefinition] = {}
        for token in definitions:
            variant_name, definition = _parse_variant(token, runtime)
            if variant_name in variants:
                raise ValueError(
                    f"Enum '{name}' has duplicate variant '{variant_name}'."
                )
            variants[variant_name] = definition
        runtime.enums[name] = EnumDefinition(name, variants)
        return

    if action not in ("create", "value"):
        raise SyntaxError(
            "Usage: enum define <name> <variant>... or "
            "enum create <type>.<variant> <variable> [values]"
        )
    if len(parts) < 4:
        raise SyntaxError(
            "Usage: enum create <type>.<variant> <variable> [values]"
        )
    qualified = parts[2]
    enum_type, separator, variant = qualified.partition(".")
    if not separator or enum_type not in runtime.enums:
        raise ValueError(f"Unknown enum type: {qualified}")
    definition = runtime.enums[enum_type]
    if variant not in definition.variants:
        raise ValueError(f"Enum '{enum_type}' has no variant named '{variant}'.")
    fields = definition.variants[variant].fields
    value_source = " ".join(parts[4:])
    values: list[Any] = []
    if value_source:
        for item in split_top_level(value_source):
            if not item:
                continue
            values.append(evaluate_expression(item, runtime))
    if len(values) != len(fields):
        raise TypeError(
            f"Enum variant '{enum_type}.{variant}' expects {len(fields)} "
            f"payload value(s), but got {len(values)}."
        )
    for (field_name, field_type), value in zip(fields, values):
        if not runtime.value_matches_type(field_type, value):
            raise TypeError(
                f"Enum field '{field_name}' requires type '{field_type}', "
                f"got '{Runtime.type_name(value)}'."
            )
    runtime.define_var(
        parts[3], enum_type, EnumValue(enum_type, variant, tuple(values))
    )


def execute_type_command(parts: list[str], runtime: Runtime) -> None:
    if (
        len(parts) < 5
        or parts[1] not in ("define", "alias")
        or "=" not in parts[2:]
    ):
        raise SyntaxError("Usage: type define <name> = <type>")
    equal_index = parts.index("=", 2)
    name = parts[2]
    if not name.isidentifier():
        raise SyntaxError("Type alias name must be an identifier.")
    if name in runtime.type_aliases:
        raise ValueError(f"Type alias '{name}' is already defined.")
    if (
        name in runtime.records or name in runtime.enums
        or name in runtime.record_type_names or name in runtime.enum_type_names
    ):
        raise ValueError(f"Type alias '{name}' conflicts with an existing type.")
    type_source = " ".join(parts[equal_index + 1:])
    try:
        spec = parse_type(type_source)
    except ValueError as error:
        raise ValueError(f"Invalid type alias: {error}") from error
    runtime.type_aliases[name] = spec
    try:
        if not runtime.type_is_known(format_type(spec)):
            raise ValueError(f"Unknown type: {format_type(spec)}")
    except ValueError:
        del runtime.type_aliases[name]
        raise
