"""Conservative static type checks for values with statically known types."""

import ast
import re
from collections import ChainMap
from dataclasses import dataclass

from .runtime import TYPES
from .syntax import tokenize_line
from .enums import _split_declarations
from .type_system import TypeSpec, format_type, is_known_type, parse_type


_FUNCTION = re.compile(r"^func (?:private )?define ")
_IDENTIFIER = re.compile(r"^[A-Za-z_]\w*$")


@dataclass(frozen=True)
class CheckDiagnostic:
    """One checker or parser diagnostic with a stable code and severity."""

    line: int
    message: str
    code: str
    severity: str = "error"


def _literal_type(value: str) -> str | None:
    value = value.strip()
    try:
        parsed = ast.literal_eval(_normalize_literals(value))
    except (SyntaxError, ValueError):
        return None
    return _python_type(parsed)


def _normalize_literals(value: str) -> str:
    result = []
    quote = None
    escaped = False
    index = 0
    replacements = {"true": "True", "false": "False", "none": "None"}
    while index < len(value):
        char = value[index]
        if quote is not None:
            result.append(char)
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
            index += 1
            continue
        if char in ("'", '"'):
            quote = char
            result.append(char)
            index += 1
            continue
        match = re.match(r"[A-Za-z_]\w*", value[index:])
        if match:
            token = match.group()
            before = value[index - 1] if index else ""
            after_index = index + len(token)
            after = value[after_index] if after_index < len(value) else ""
            if token.lower() in replacements and not (
                before.isalnum() or before == "_" or after.isalnum() or after == "_"
            ):
                token = replacements[token.lower()]
            result.append(token)
            index = after_index
        else:
            result.append(char)
            index += 1
    return "".join(result)


def _merge_types(types: list[str]) -> str | None:
    if not types:
        return None
    options = []
    for type_name in types:
        spec = parse_type(type_name)
        options.extend(spec.arguments if spec.name == "union" else (spec,))
    return format_type(TypeSpec("union", tuple(dict.fromkeys(options))))


def _python_type(value: object) -> str | None:
    if value is None:
        return "none"
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "float"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        item_types = [_python_type(item) for item in value]
        item_type = _merge_types([item for item in item_types if item])
        return f"list[{item_type}]" if item_type else "list"
    if isinstance(value, set):
        item_types = [_python_type(item) for item in value]
        item_type = _merge_types([item for item in item_types if item])
        return f"set[{item_type}]" if item_type else "set"
    if isinstance(value, dict):
        key_types = [_python_type(item) for item in value]
        item_types = [_python_type(item) for item in value.values()]
        key_type = _merge_types([item for item in key_types if item])
        value_type = _merge_types([item for item in item_types if item])
        return f"dict[{key_type}, {value_type}]" if key_type and value_type else "dict"
    if isinstance(value, tuple):
        item_types = [_python_type(item) for item in value]
        return (
            f"tuple[{', '.join(item_types)}]"
            if item_types and all(item_types)
            else "tuple"
        )
    return None


def _union_members(type_name: str) -> list[TypeSpec]:
    spec = parse_type(type_name)
    return list(spec.arguments) if spec.name == "union" else [spec]


def _format_members(members: list[TypeSpec]) -> str | None:
    unique = tuple(dict.fromkeys(members))
    if not unique:
        return None
    if len(unique) == 1:
        return format_type(unique[0])
    return format_type(TypeSpec("union", unique))


def _merge_facts(
    first: dict[str, str | None], second: dict[str, str | None]
) -> dict[str, str | None]:
    merged = dict(first)
    for name, value in second.items():
        if name in merged:
            if merged[name] != value:
                del merged[name]
        else:
            merged[name] = value
    return merged


def _matching_members(
    type_name: str, literal_type: str
) -> tuple[list[TypeSpec], list[TypeSpec]]:
    matching: list[TypeSpec] = []
    remaining: list[TypeSpec] = []
    for member in _union_members(type_name):
        if _compatible(format_type(member), literal_type, False):
            matching.append(member)
        else:
            remaining.append(member)
    return matching, remaining


def _truth_facts(
    name: str, variables: dict[str, str | None]
) -> tuple[dict[str, str | None], dict[str, str | None]]:
    type_name = variables.get(name)
    if type_name is None:
        return {}, {}
    members = _union_members(type_name)
    if not any(member.name == "none" for member in members):
        return {}, {}
    truthy = _format_members(
        [member for member in members if member.name != "none"]
    )
    true_facts = {name: truthy} if truthy is not None else {}
    return true_facts, {name: "none"}


def _comparison_facts(
    left: ast.expr,
    operation: ast.cmpop,
    right: ast.expr,
    variables: dict[str, str | None],
) -> tuple[dict[str, str | None], dict[str, str | None]]:
    if isinstance(operation, (ast.Eq, ast.NotEq)):
        pass
    else:
        return {}, {}
    name: str | None = None
    literal: ast.expr | None = None
    if isinstance(left, ast.Name) and isinstance(right, ast.Constant):
        name, literal = left.id, right
    elif isinstance(right, ast.Name) and isinstance(left, ast.Constant):
        name, literal = right.id, left
    if name is None or literal is None:
        return {}, {}
    type_name = variables.get(name)
    if type_name is None:
        return {}, {}
    literal_type = _python_type(literal.value)
    if literal_type is None:
        return {}, {}
    matching, remaining = _matching_members(type_name, literal_type)
    if len(matching) == len(_union_members(type_name)):
        return {}, {}
    true_type = _format_members(matching)
    false_type = _format_members(remaining)
    true_facts = {name: true_type} if true_type is not None else {}
    false_facts = {name: false_type} if false_type is not None else {}
    if isinstance(operation, ast.NotEq):
        true_facts, false_facts = false_facts, true_facts
    return true_facts, false_facts


def _condition_facts(
    source: str, variables: dict[str, str | None]
) -> tuple[dict[str, str | None], dict[str, str | None]]:
    try:
        node = ast.parse(_normalize_literals(source), mode="eval").body
    except SyntaxError:
        return {}, {}

    def facts(
        expression: ast.expr,
    ) -> tuple[dict[str, str | None], dict[str, str | None]]:
        if isinstance(expression, ast.Name):
            return _truth_facts(expression.id, variables)
        if isinstance(expression, ast.UnaryOp) and isinstance(
            expression.op, ast.Not
        ):
            true_facts, false_facts = facts(expression.operand)
            return false_facts, true_facts
        if isinstance(expression, ast.Compare) and len(expression.ops) == 1:
            return _comparison_facts(
                expression.left,
                expression.ops[0],
                expression.comparators[0],
                variables,
            )
        if isinstance(expression, ast.BoolOp):
            if isinstance(expression.op, ast.And):
                true_facts: dict[str, str | None] = {}
                for value in expression.values:
                    true_facts = _merge_facts(true_facts, facts(value)[0])
                return true_facts, {}
            if isinstance(expression.op, ast.Or):
                false_facts: dict[str, str | None] = {}
                for value in expression.values:
                    false_facts = _merge_facts(false_facts, facts(value)[1])
                return {}, false_facts
        return {}, {}

    return facts(node)


def _iterated_type(type_name: str | None) -> str | None:
    if type_name is None:
        return None
    spec = parse_type(type_name)
    if spec.name in ("list", "set", "tuple", "iterator") and spec.arguments:
        return _format_members(list(spec.arguments))
    if spec.name == "string":
        return "string"
    return None


def _indexed_type(type_name: str | None, index: str) -> str | None:
    if type_name is None:
        return None
    spec = parse_type(type_name)
    if spec.name in ("list", "set", "dict", "iterator") and spec.arguments:
        return format_type(spec.arguments[0])
    if spec.name == "tuple" and spec.arguments:
        if len(spec.arguments) == 1:
            return format_type(spec.arguments[0])
        try:
            position = int(index)
        except ValueError:
            return _format_members(list(spec.arguments))
        if 0 <= position < len(spec.arguments):
            return format_type(spec.arguments[position])
    if spec.name == "string":
        return "string"
    return None


def _value_type(type_name: str | None) -> str | None:
    if type_name is None:
        return None
    spec = parse_type(type_name)
    if spec.name == "dict" and len(spec.arguments) == 2:
        return format_type(spec.arguments[1])
    return None


def _type_of(
    value: str,
    variables: dict[str, str | None],
    functions: dict[str, str | None] | None = None,
) -> str | None:
    value = value.strip()
    if value in variables:
        return variables[value]
    if functions and value in functions:
        return functions[value]
    return _expression_type(value, variables, functions)


def _expression_type(
    source: str,
    variables: dict[str, str | None],
    functions: dict[str, str | None] | None,
) -> str | None:
    try:
        expression = ast.parse(_normalize_literals(source), mode="eval").body
    except SyntaxError:
        return None

    def infer(
        node: ast.expr, environment: dict[str, str | None]
    ) -> str | None:
        if isinstance(node, ast.Constant):
            return _python_type(node.value)
        if isinstance(node, ast.JoinedStr):
            return "string"
        if isinstance(node, ast.Name):
            return environment.get(node.id) or (functions or {}).get(node.id)
        if isinstance(node, ast.List):
            item_types = [infer(item, environment) for item in node.elts]
            merged = _merge_types([item for item in item_types if item])
            return f"list[{merged}]" if merged else "list"
        if isinstance(node, ast.ListComp):
            generator = node.generators[0]
            item_type = _iterated_type(infer(generator.iter, environment))
            local = dict(environment)
            if isinstance(generator.target, ast.Name):
                local[generator.target.id] = item_type
            for condition in generator.ifs:
                true_facts, _ = _condition_facts(
                    ast.unparse(condition), local
                )
                for name, narrowed in true_facts.items():
                    if narrowed is not None:
                        local[name] = narrowed
            element_type = infer(node.elt, local)
            return f"list[{element_type}]" if element_type else "list"
        if isinstance(node, ast.Set):
            item_types = [infer(item, environment) for item in node.elts]
            merged = _merge_types([item for item in item_types if item])
            return f"set[{merged}]" if merged else "set"
        if isinstance(node, ast.Tuple):
            item_types = [infer(item, environment) for item in node.elts]
            return (
                f"tuple[{', '.join(item_types)}]"
                if item_types and all(item_types) else "tuple"
            )
        if isinstance(node, ast.Dict):
            key_types = [
                infer(item, environment) for item in node.keys if item is not None
            ]
            value_types = [infer(item, environment) for item in node.values]
            key_type = _merge_types([item for item in key_types if item])
            value_type = _merge_types([item for item in value_types if item])
            return (
                f"dict[{key_type}, {value_type}]"
                if key_type and value_type else "dict"
            )
        if isinstance(node, ast.UnaryOp):
            operand = infer(node.operand, environment)
            if isinstance(node.op, ast.Not):
                return "bool" if operand == "bool" else None
            return operand if operand in ("int", "float") else None
        if isinstance(node, ast.BinOp):
            left = infer(node.left, environment)
            right = infer(node.right, environment)
            if (
                isinstance(node.op, ast.Add)
                and left == "string"
                and right == "string"
            ):
                return "string"
            if left not in ("int", "float") or right not in ("int", "float"):
                return None
            if isinstance(node.op, ast.Div) or "float" in (left, right):
                return "float"
            if (
                isinstance(node.op, ast.Pow)
                and isinstance(node.right, ast.UnaryOp)
                and isinstance(node.right.op, ast.USub)
            ):
                return "float"
            return "int"
        if isinstance(node, (ast.BoolOp, ast.Compare)):
            return "bool"
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                if node.func.id == "set" and not node.args and not node.keywords:
                    return "set"
                if node.func.id == "range":
                    return "list[int]"
                function_type = (functions or {}).get(node.func.id)
                if function_type is not None:
                    spec = parse_type(function_type)
                    if spec.name == "function" and spec.arguments:
                        return format_type(spec.arguments[-1])
            return None
        return None

    return infer(expression, variables)


def _compatible(
    actual: str | None, expected: str, top_level: bool = True
) -> bool:
    if actual is None:
        return True
    actual_spec, expected_spec = parse_type(actual), parse_type(expected)
    if expected_spec.name == "union":
        return any(
            _compatible(actual, format_type(option), top_level)
            for option in expected_spec.arguments
        )
    if actual_spec.name == "union":
        if top_level:
            return any(
                _compatible(format_type(option), expected, False)
                for option in actual_spec.arguments
            )
        return all(
            _compatible(format_type(option), expected, False)
            for option in actual_spec.arguments
        )
    if actual_spec.name == "int" and expected_spec.name == "float":
        return True
    if actual_spec.name != expected_spec.name:
        return False
    if not expected_spec.arguments:
        return True
    if not actual_spec.arguments:
        return True
    if len(actual_spec.arguments) != len(expected_spec.arguments):
        return False
    return all(
        _compatible(format_type(actual_item), format_type(expected_item), False)
        and _compatible(format_type(expected_item), format_type(actual_item), False)
        for actual_item, expected_item in zip(
            actual_spec.arguments, expected_spec.arguments
        )
    )


def _result_type(
    parts: list[str],
    variables: dict[str, str | None],
    functions: dict[str, str | None],
    record_types: dict[str, dict[str, str]],
) -> tuple[str, str | None] | None:
    command = parts[0]
    fixed = {
        "all": ("bool", 2), "any": ("bool", 2), "ascii": ("string", 2),
        "bool": ("bool", 2), "bytearray": ("bytearray", 2), "bytes": ("bytes", 2),
        "callable": ("bool", 2), "chr": ("string", 2), "hasattr": ("bool", 2),
        "id": ("int", 2), "len": ("int", 2), "ord": ("int", 2),
        "repr": ("string", 2), "type": ("string", 2),
    }
    if command in fixed and len(parts) >= 3:
        result_type, destination_index = fixed[command]
        return parts[destination_index], result_type
    if command in ("enumerate", "filter", "map", "range", "reversed", "sorted", "zip"):
        if len(parts) >= 3:
            if command == "range":
                destination_index = {3: 2, 4: 3, 5: 3}.get(len(parts))
                if destination_index is not None:
                    return parts[destination_index], "list[int]"
            if command == "enumerate":
                item_type = _iterated_type(
                    _type_of(parts[1], variables, functions)
                )
                element = (
                    f"tuple[int, {item_type}]" if item_type else "tuple"
                )
                return parts[2], f"list[{element}]"
            if command == "filter":
                if len(parts) >= 4:
                    item_type = _iterated_type(
                        _type_of(parts[2], variables, functions)
                    )
                    return parts[3], f"list[{item_type}]" if item_type else "list"
                return None
            if command == "map":
                if len(parts) >= 4:
                    function_type = _type_of(parts[1], variables, functions)
                    result_type = None
                    if function_type is not None:
                        spec = parse_type(function_type)
                        if spec.name == "function" and spec.arguments:
                            result_type = format_type(spec.arguments[-1])
                    return (
                        parts[3],
                        f"list[{result_type}]" if result_type else "list",
                    )
                return None
            if command in ("reversed", "sorted"):
                item_type = _iterated_type(
                    _type_of(parts[1], variables, functions)
                )
                return parts[2], f"list[{item_type}]" if item_type else "list"
            if command == "zip":
                source_types = [
                    _type_of(part, variables, functions)
                    for part in parts[1:-1]
                ]
                members = [
                    _iterated_type(source_type) or "unknown"
                    for source_type in source_types
                ]
                element = f"tuple[{', '.join(members)}]"
                return parts[-1], f"list[{element}]"
    if command == "iter" and len(parts) == 3:
        return parts[2], "iterator"
    if command == "format" and len(parts) in (3, 4):
        return parts[-1], "string"
    if command == "compare" and len(parts) >= 4:
        return parts[-1], _type_of(" ".join(parts[1:-1]), variables, functions)
    if command == "text" and len(parts) == 3 and parts[1] == "input":
        return parts[2], "string"
    if command == "list" and len(parts) == 4 and parts[1] == "len":
        return parts[3], "int"
    if command in ("list", "tuple") and len(parts) == 5 and parts[1] == "get":
        return parts[4], _indexed_type(
            _type_of(parts[2], variables, functions), parts[3]
        )
    if command == "dict" and len(parts) == 5 and parts[1] == "get":
        return parts[4], _value_type(
            _type_of(parts[2], variables, functions)
        )
    if command == "getattr" and len(parts) == 4:
        container_type = _type_of(parts[1], variables, functions)
        field_type = None
        if container_type in record_types:
            field_type = record_types[container_type].get(parts[2])
        if field_type is None:
            field_type = _value_type(container_type)
        return parts[3], field_type
    if command == "open" and len(parts) == 4:
        return parts[3], "file"
    if command == "record" and len(parts) >= 4 and parts[1] == "create":
        return parts[3], parts[2]
    if command == "slice" and len(parts) in (5, 6):
        return parts[4], variables.get(parts[1])
    if command == "ffi" and len(parts) >= 7 and "->" in parts:
        result_types = {"i32": "int", "i64": "int", "f64": "float", "bool": "bool"}
        if parts[4] in result_types:
            return parts[parts.index("->") + 1], result_types[parts[4]]
    if command == "func" and len(parts) >= 5 and parts[1] == "call" and "->" in parts:
        function_type = _type_of(parts[2], variables, functions)
        if function_type is not None:
            spec = parse_type(function_type)
            if spec.name == "function":
                return parts[parts.index("->") + 1], format_type(spec.arguments[-1])
        return parts[parts.index("->") + 1], None
    return None


def _record_definition(
    declarations: list[str], known_records: set[str]
) -> tuple[dict[str, str], set[str]]:
    fields: dict[str, str] = {}
    defaults: set[str] = set()
    for declaration in declarations:
        if ":" not in declaration:
            continue
        field_name, _, type_source = declaration.partition(":")
        type_source, default_separator, _ = type_source.partition("=")
        try:
            spec = parse_type(type_source)
        except ValueError:
            continue
        if is_known_type(spec, known_records):
            fields[field_name] = format_type(spec)
            if default_separator:
                defaults.add(field_name)
    return fields, defaults


def _match_case_patterns(
    lines: list[str], start: int
) -> tuple[list[str], bool]:
    """Collect patterns and whether an else covers a match block."""
    patterns: list[str] = []
    has_else = False
    depth = 1
    index = start + 1
    while index < len(lines):
        stripped = lines[index].strip()
        if not stripped or stripped.startswith("#"):
            index += 1
            continue
        try:
            parts = list(tokenize_line(stripped))
        except SyntaxError:
            index += 1
            continue
        command = parts[0] if parts else ""
        if command == "match":
            depth += 1
        elif command == "endmatch":
            depth -= 1
            if depth == 0:
                break
        elif depth == 1 and command == "case":
            pattern = " ".join(parts[1:])
            if pattern in ("else", "_"):
                has_else = True
            elif pattern:
                patterns.append(pattern)
        elif depth == 1 and command == "else":
            has_else = True
        index += 1
    return patterns, has_else


def check_types_detailed(
    lines: list[str], strict: bool = False
) -> list[CheckDiagnostic]:
    """Return checker diagnostics, including warnings, for a source file."""
    diagnostics: list[CheckDiagnostic] = []
    globals_: dict[str, str | None] = {}
    scopes = [globals_]
    narrowings: list[dict[str, str | None]] = [{}]
    exit_states: list[bool] = [False]
    record_types: dict[str, dict[str, str]] = {}
    record_defaults: dict[str, set[str]] = {}
    function_types: dict[str, str | None] = {}
    function_parameters: dict[str, list[tuple[str, str | None]]] = {}
    function_returns: list[str | None] = []
    function_depth = 0
    block_stack: list[str] = []
    block_info: list[dict[str, object]] = []

    def report(
        line_number: int,
        message: str,
        code: str = "type-mismatch",
        severity: str = "error",
    ) -> None:
        diagnostics.append(CheckDiagnostic(line_number, message, code, severity))

    def visible_variables() -> ChainMap[str, str | None]:
        mappings: list[dict[str, str | None]] = []
        for scope, narrow in zip(reversed(scopes), reversed(narrowings)):
            mappings.append(narrow)
            mappings.append(scope)
        return ChainMap(*mappings)

    def declared_type(name: str) -> str | None:
        for scope in reversed(scopes):
            if name in scope:
                return scope[name]
        return None

    def set_declared_type(name: str, type_name: str) -> None:
        for scope in reversed(scopes):
            if name in scope:
                scope[name] = type_name
                return
        scopes[-1][name] = type_name

    def narrow_override(name: str, type_name: str | None) -> None:
        for narrowing in reversed(narrowings):
            if name in narrowing:
                if type_name is not None:
                    narrowing[name] = type_name
                return

    def clear_narrow(name: str) -> None:
        for narrowing in narrowings:
            narrowing.pop(name, None)

    # Collect record names first so forward record annotations resolve, then
    # parse every declaration against the complete set of record names.
    record_declarations: list[tuple[str, list[str]]] = []
    enum_names: set[str] = set()
    enum_variants: dict[str, set[str]] = {}
    for line in lines:
        stripped_line = line.strip()
        if not stripped_line or stripped_line.startswith("#"):
            continue
        try:
            parts = list(tokenize_line(stripped_line))
        except SyntaxError:
            continue
        if len(parts) >= 3 and parts[:2] == ["record", "define"]:
            record_declarations.append((parts[2], parts[3:]))
        elif (
            len(parts) >= 3 and parts[:2] == ["enum", "define"]
            and parts[2].isidentifier()
        ):
            enum_names.add(parts[2])
            variants = {
                token.partition("(")[0]
                for token in _split_declarations(" ".join(parts[3:]))
                if token.partition("(")[0].isidentifier()
            }
            enum_variants[parts[2]] = variants
    record_names = {name for name, _ in record_declarations}
    for name, declarations in record_declarations:
        fields, defaults = _record_definition(
            declarations, record_names | enum_names
        )
        record_types[name] = fields
        record_defaults[name] = defaults

    for line_number, line in enumerate(lines):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        try:
            parts = list(tokenize_line(stripped))
        except SyntaxError:
            continue
        if not parts:
            continue
        command = parts[0]
        branch_blocks = {
            "elseif": "if",
            "else": "if",
            "catch": "try",
            "finally": "try",
        }
        end_blocks = {
            "endif": "if", "endloop": "loop", "endtry": "try",
            "endmatch": "match",
        }

        is_branch = (
            (
                command in branch_blocks
                and block_stack
                and block_stack[-1] == branch_blocks[command]
            )
            or (
                command in ("case", "else")
                and block_stack
                and block_stack[-1] == "match"
            )
        )
        is_end = (
            command in end_blocks
            and block_stack
            and block_stack[-1] == end_blocks[command]
        )

        previous_exit = exit_states[-1]
        if (
            previous_exit
            and not is_branch
            and not is_end
            and command not in (
                "elseif", "else", "catch", "finally", "endfunc", "case",
            )
        ):
            report(
                line_number,
                "Unreachable statement: the preceding command always exits "
                "this block.",
                "unreachable-code",
                "warning",
            )
        exit_states[-1] = False

        if is_branch:
            info = block_info[-1]
            if command in ("elseif", "else"):
                if not previous_exit:
                    info["all_exit"] = False
            scopes.pop()
            scopes.append({})
            narrowings.pop()
            exit_states.pop()
            exit_states.append(False)
            if command == "elseif":
                previous = visible_variables()
                enclosing_facts: dict[str, str | None] = dict(
                    info.get("false_accum", {})  # type: ignore[arg-type]
                )
                facts_variables = ChainMap(enclosing_facts, previous)
                true_facts, false_facts = _condition_facts(
                    " ".join(parts[1:]), facts_variables
                )
                narrowings.append(dict(true_facts))
                info["branch_false"] = false_facts
                info["false_accum"] = false_facts
            elif command == "else":
                narrowings.append(
                    dict(info.get("false_accum", {}))  # type: ignore[arg-type]
                )
                info["has_else"] = True
            else:
                narrowings.append({})

        if is_end:
            info = block_info[-1] if block_info else {}
            post: dict[str, str | None] = {}
            if command == "endif" and info.get("kind") == "if":
                if info.get("has_else"):
                    if not previous_exit:
                        post = dict(
                            info.get("false_accum", {})  # type: ignore[arg-type]
                        )
                elif previous_exit and info.get("all_exit", True):
                    post = dict(
                        info.get("false_accum", {})  # type: ignore[arg-type]
                    )
            block_stack.pop()
            block_info.pop()
            scopes.pop()
            narrowings.pop()
            exit_states.pop()
            if post:
                narrowings[-1].update(post)

        if _FUNCTION.match(stripped):
            function_depth += 1
            scopes.append({})
            narrowings.append({})
            exit_states.append(False)
            block_stack.append("func")
            block_info.append({"kind": "func"})
            name_index = 3 if parts[1] == "private" else 2
            function_name = parts[name_index]
            declarations = parts[name_index + 1:]
            return_type = None
            if "->" in declarations:
                return_index = declarations.index("->")
                return_type = " ".join(declarations[return_index + 1:])
                declarations = declarations[:return_index]
            normalized_return_type = None
            if return_type:
                try:
                    return_spec = parse_type(return_type)
                    if is_known_type(return_spec, set(record_types) | enum_names):
                        normalized_return_type = format_type(return_spec)
                except ValueError:
                    pass
                if strict and normalized_return_type is None:
                    report(
                        line_number,
                        f"Invalid annotation: unknown return type '{return_type}'.",
                        "invalid-annotation",
                        "warning",
                    )
            function_returns.append(normalized_return_type)
            parameter_types = []
            named_parameter_types = []
            for declaration in declarations:
                parameter = declaration.lstrip("*").partition("=")[0]
                name, separator, annotation = parameter.partition(":")
                if separator:
                    try:
                        spec = parse_type(annotation)
                        scopes[-1][name] = (
                            format_type(spec)
                            if is_known_type(spec, set(record_types) | enum_names)
                            else None
                        )
                        parameter_types.append(format_type(spec))
                        named_parameter_types.append((name, format_type(spec)))
                        if strict and not is_known_type(
                            spec, set(record_types) | enum_names
                        ):
                            report(
                                line_number,
                                f"Invalid annotation: unknown type "
                                f"'{annotation}' for parameter '{name}'.",
                                "invalid-annotation",
                                "warning",
                            )
                    except ValueError:
                        scopes[-1][name] = None
                        parameter_types.append(None)
                        named_parameter_types.append((name, None))
                        if strict:
                            report(
                                line_number,
                                f"Invalid annotation: cannot parse type "
                                f"'{annotation}' for parameter '{name}'.",
                                "invalid-annotation",
                                "warning",
                            )
                else:
                    scopes[-1][name] = None
                    parameter_types.append(None)
                    named_parameter_types.append((name, None))
            function_parameters[function_name] = named_parameter_types
            if (
                return_type
                and all(parameter_types)
                and all(not declaration.startswith("*") for declaration in declarations)
            ):
                try:
                    function_spec = parse_type(
                        f"({', '.join(parameter_types)}) -> {normalized_return_type}"
                    )
                    if is_known_type(function_spec, set(record_types) | enum_names):
                        function_types[function_name] = format_type(function_spec)
                    else:
                        function_types[function_name] = None
                except ValueError:
                    function_types[function_name] = None
            else:
                function_types[function_name] = None
            continue
        if parts[0] == "endfunc" and function_depth:
            if block_stack and block_stack[-1] == "func":
                block_stack.pop()
                block_info.pop()
            scopes.pop()
            narrowings.pop()
            exit_states.pop()
            function_depth -= 1
            function_returns.pop()
            continue
        variables = visible_variables()

        def update_type(name: str, type_name: str) -> None:
            target = next(
                (scope for scope in reversed(scopes) if name in scope),
                scopes[-1],
            )
            target[name] = type_name

        if parts[0] == "record" and len(parts) >= 3 and parts[1] == "define":
            fields, defaults = _record_definition(parts[3:], record_names)
            record_types[parts[2]] = fields
            record_defaults[parts[2]] = defaults
            continue
        if parts[0] == "record" and len(parts) >= 4 and parts[1] == "create":
            record_name, variable_name = parts[2], parts[3]
            fields = record_types.get(record_name)
            if fields is not None:
                field_names = list(fields)
                positional: list[str] = []
                named: dict[str, str] = {}
                saw_named = False
                for token in parts[4:]:
                    field_name, separator, value = token.partition("=")
                    if separator and field_name.isidentifier():
                        saw_named = True
                        named[field_name] = value
                    else:
                        if saw_named:
                            report(
                                line_number,
                                "Type mismatch: positional record field values "
                                "must come before named fields.",
                            )
                        positional.append(token)
                if len(positional) > len(field_names):
                    report(
                        line_number,
                        f"Record '{record_name}' expects {len(field_names)} field "
                        f"value(s), but got {len(positional)}.",
                    )
                assigned: dict[str, str] = dict(zip(field_names, positional))
                for field_name, value in named.items():
                    if field_name not in fields:
                        report(
                            line_number,
                            f"Record '{record_name}' has no field named "
                            f"'{field_name}'.",
                        )
                    elif field_name in assigned:
                        report(
                            line_number,
                            f"Record '{record_name}' got field '{field_name}' "
                            "more than once.",
                        )
                    else:
                        assigned[field_name] = value
                defaults = record_defaults.get(record_name, set())
                missing = [
                    field_name for field_name in field_names
                    if field_name not in assigned and field_name not in defaults
                ]
                if missing:
                    report(
                        line_number,
                        f"Record '{record_name}' is missing required field(s): "
                        f"{', '.join(missing)}.",
                    )
                for field_name, token in assigned.items():
                    expected = fields[field_name]
                    actual = _type_of(token, variables, function_types)
                    if actual is not None and not _compatible(actual, expected):
                        report(
                            line_number,
                            f"Type mismatch: field '{field_name}' requires '{expected}' "
                            f"but value has type '{actual}'.",
                        )
                scopes[-1][variable_name] = record_name
                narrowings[-1].pop(variable_name, None)
            continue
        if (
            parts[0] == "define" and len(parts) >= 6 and parts[1] == "var"
            and parts[2].endswith(":") and "=" in parts
        ):
            equal_index = parts.index("=")
            name = parts[2][:-1]
            declared = " ".join(parts[3:equal_index])
            if any(name in scope for scope in scopes[:-1]):
                report(
                    line_number,
                    f"Variable '{name}' shadows a variable in an enclosing scope.",
                    "shadowed-variable",
                    "warning",
                )
            try:
                declared_spec = parse_type(declared)
            except ValueError:
                continue
            if not is_known_type(declared_spec, set(record_types) | enum_names):
                continue
            declared = format_type(declared_spec)
            actual = _type_of(
                " ".join(parts[equal_index + 1:]), variables, function_types
            )
            if actual is not None and not _compatible(actual, declared):
                report(
                    line_number,
                    f"Type mismatch: variable '{name}' declares '{declared}' "
                    f"but its initial value has type '{actual}'.",
                )
            scopes[-1][name] = declared
            narrowings[-1].pop(name, None)
            continue

        if parts[0] == "convert":
            if len(parts) == 4 and parts[2] == "to" and parts[3] in TYPES:
                update_type(parts[1], parts[3])
                set_declared_type(parts[1], parts[3])
                clear_narrow(parts[1])
            elif len(parts) == 3 and parts[2] in TYPES:
                update_type(parts[1], parts[2])
                set_declared_type(parts[1], parts[2])
                clear_narrow(parts[1])
            continue
        if parts[0] == "assert":
            if len(parts) >= 2:
                condition_type = _type_of(parts[1], variables, function_types)
                if (
                    condition_type is not None
                    and not _compatible(condition_type, "bool")
                ):
                    report(
                        line_number,
                        f"Type mismatch: assert condition has type '{condition_type}', "
                        "expected 'bool'.",
                    )
            if len(parts) == 3 and parts[1].lower() != "true":
                message_type = _type_of(parts[2], variables, function_types)
                if (
                    message_type is not None
                    and not _compatible(message_type, "string")
                ):
                    report(
                        line_number,
                        f"Type mismatch: assert message has type '{message_type}', "
                        "expected 'string'.",
                    )
            continue
        if parts[0] in ("if", "elseif") and len(parts) > 1:
            condition_source = " ".join(parts[1:])
            actual = _type_of(condition_source, variables, function_types)
            if actual is not None and not _compatible(actual, "bool"):
                report(
                    line_number,
                    f"Type mismatch: condition has type '{actual}', expected 'bool'.",
                )
        if parts[0] == "loop" and len(parts) > 2 and parts[1] == "while":
            actual = _type_of(" ".join(parts[2:]), variables, function_types)
            if actual is not None and not _compatible(actual, "bool"):
                report(
                    line_number,
                    f"Type mismatch: loop condition has type '{actual}', expected 'bool'.",
                )
        if command == "match":
            subject_type = _type_of(
                " ".join(parts[1:]), variables, function_types
            )
            patterns, has_else = _match_case_patterns(lines, line_number - 1)
            if subject_type is not None and not has_else:
                try:
                    subject_spec = parse_type(subject_type)
                except ValueError:
                    subject_spec = None
                if subject_spec is not None:
                    if subject_spec.name in enum_variants:
                        seen: set[str] = set()
                        for pattern_source in patterns:
                            if pattern_source == subject_spec.name:
                                seen.update(enum_variants[subject_spec.name])
                                continue
                            enum_pattern = re.match(
                                r"^([A-Za-z_]\w*)\.([A-Za-z_]\w*)",
                                pattern_source,
                            )
                            if (
                                enum_pattern is not None
                                and enum_pattern.group(1) == subject_spec.name
                            ):
                                seen.add(enum_pattern.group(2))
                        missing = enum_variants[subject_spec.name] - seen
                        if missing:
                            report(
                                line_number,
                                "Non-exhaustive match: missing enum variant(s): "
                                f"{', '.join(sorted(missing))}.",
                                "non-exhaustive-match",
                            )
                    elif subject_spec.name == "union":
                        required = {
                            format_type(member)
                            for member in subject_spec.arguments
                            if member.name != "none"
                            or "none" in {
                                format_type(option)
                                for option in subject_spec.arguments
                            }
                        }
                        covered: set[str] = set()
                        for pattern_source in patterns:
                            if pattern_source == "_" or pattern_source == "else":
                                covered.update(required)
                                continue
                            literal_type = _literal_type(pattern_source)
                            if literal_type is not None:
                                covered.add(literal_type)
                                continue
                            try:
                                pattern_spec = parse_type(pattern_source)
                            except ValueError:
                                continue
                            covered.add(format_type(pattern_spec))
                        missing = required - covered
                        if missing:
                            report(
                                line_number,
                                "Non-exhaustive match: missing union member(s): "
                                f"{', '.join(sorted(missing))}.",
                                "non-exhaustive-match",
                            )
        block_openers = {
            "if": "if", "loop": "loop", "try": "try", "match": "match",
        }
        if command in block_openers:
            block_stack.append(block_openers[command])
            scopes.append({})
            exit_states.append(False)
            if command == "if":
                true_facts, false_facts = _condition_facts(
                    " ".join(parts[1:]), variables
                )
                narrowings.append(dict(true_facts))
                all_exit = True
                block_info.append({
                    "kind": "if",
                    "false_accum": dict(false_facts),
                    "branch_false": dict(false_facts),
                    "all_exit": all_exit,
                    "has_else": False,
                })
            else:
                narrowings.append({})
                block_info.append({"kind": command})
            continue
        if parts[0] == "set" and len(parts) >= 4 and parts[2] == "=":
            destination = parts[1]
            expected = declared_type(destination)
            if expected is None:
                expected = variables.get(destination)
            actual = _type_of(" ".join(parts[3:]), variables, function_types)
            if actual is not None and expected is not None and not _compatible(actual, expected):
                report(
                    line_number,
                    f"Type mismatch: assignment has type '{actual}' but variable "
                    f"'{destination}' has type '{expected}'.",
                )
            if actual is not None:
                narrow_override(destination, actual)
            continue
        if parts[0] == "return" and function_returns:
            expected = function_returns[-1]
            actual = _type_of(
                " ".join(parts[1:]) if len(parts) > 1 else "none",
                variables,
                function_types,
            )
            if (
                expected is not None and actual is not None
                and not _compatible(actual, expected)
            ):
                report(
                    line_number,
                    f"Type mismatch: function return has type '{actual}' "
                    f"but annotation requires '{expected}'.",
                )
            exit_states[-1] = True
            continue
        if parts[0] in ("break", "continue", "throw"):
            exit_states[-1] = True
            continue
        if len(parts) >= 3 and parts[:2] == ["func", "call"]:
            function_type = _type_of(parts[2], variables, function_types)
            if function_type is not None:
                spec = parse_type(function_type)
                if spec.name == "function":
                    call_arguments = parts[3:]
                    if "->" in call_arguments:
                        call_arguments = call_arguments[:call_arguments.index("->")]
                    named_parameters = function_parameters.get(parts[2], [])
                    for argument_index, argument in enumerate(call_arguments):
                        parameter_name, separator, value = argument.partition("=")
                        if separator and parameter_name.isidentifier():
                            matching = next(
                                (
                                    parameter_type for name, parameter_type in named_parameters
                                    if name == parameter_name
                                ),
                                None,
                            )
                            if matching is None:
                                continue
                            expected_argument = matching
                        else:
                            if argument_index >= len(spec.arguments) - 1:
                                continue
                            expected_argument = format_type(spec.arguments[argument_index])
                            value = argument
                        actual_argument = _type_of(value, variables, function_types)
                        if (
                            actual_argument is not None
                            and not _compatible(actual_argument, expected_argument)
                        ):
                            report(
                                line_number,
                                f"Type mismatch: argument '{value}' has type "
                                f"'{actual_argument}' but parameter requires "
                                f"'{expected_argument}'.",
                            )

        result = _result_type(
            parts, variables, function_types, record_types
        )
        if result is None:
            continue
        destination, actual = result
        expected = declared_type(destination)
        if expected is None:
            expected = variables.get(destination)
        if actual is not None and expected is not None and not _compatible(actual, expected):
            report(
                line_number,
                f"Type mismatch: command result has type '{actual}' but destination "
                f"'{destination}' has type '{expected}'.",
            )
        if destination not in variables and _IDENTIFIER.fullmatch(destination):
            scopes[-1][destination] = actual
            narrowings[-1].pop(destination, None)
        elif actual is not None:
            narrow_override(destination, actual)
    return diagnostics


def check_types(lines: list[str]) -> list[tuple[int, str]]:
    """Return (zero-based line, diagnostic) pairs for definite type mismatches."""
    return [
        (diagnostic.line, diagnostic.message)
        for diagnostic in check_types_detailed(lines)
        if diagnostic.severity == "error"
    ]
