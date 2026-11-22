"""Evaluation of YubaLANG's expression grammar without Python eval."""

import ast
import operator
import re
from typing import Any, Callable

from .runtime import RecordValue, Runtime


_STRING_METHODS = frozenset({
    "capitalize", "casefold", "count", "endswith", "find", "format", "index",
    "isalnum", "isalpha", "isdigit", "islower", "isspace", "isupper", "join",
    "lower", "lstrip", "partition", "removeprefix", "removesuffix", "replace",
    "rfind", "rindex", "rpartition", "rsplit", "rstrip", "split", "splitlines",
    "startswith", "strip", "swapcase", "title", "upper", "zfill",
})
_LIST_METHODS = frozenset({
    "append", "clear", "copy", "count", "extend", "index", "insert", "pop",
    "remove", "reverse", "sort",
})
_DICT_METHODS = frozenset({
    "clear", "copy", "get", "items", "keys", "pop", "popitem", "setdefault",
    "update", "values",
})
_SET_METHODS = frozenset({
    "add", "clear", "copy", "difference", "discard", "intersection",
    "isdisjoint", "issubset", "issuperset", "pop", "remove", "symmetric_difference",
    "union", "update",
})
_BYTES_METHODS = frozenset({"decode", "hex", "split", "strip", "replace"})

_OPERATORS: dict[type[ast.operator], Callable[[Any, Any], Any]] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
_COMPARISONS: dict[type[ast.cmpop], Callable[[Any, Any], bool]] = {
    ast.Eq: operator.eq,
    ast.NotEq: operator.ne,
    ast.Lt: operator.lt,
    ast.LtE: operator.le,
    ast.Gt: operator.gt,
    ast.GtE: operator.ge,
}


def _normalize(source: str) -> str:
    result = []
    quote = None
    escaped = False
    index = 0
    replacements = {"true": "True", "false": "False", "none": "None"}
    while index < len(source):
        char = source[index]
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
        match = re.match(r"[A-Za-z_]\w*", source[index:])
        if match is None:
            result.append(char)
            index += 1
            continue
        token = match.group()
        before = source[index - 1] if index else ""
        after_index = index + len(token)
        after = source[after_index] if after_index < len(source) else ""
        if (
            token.lower() in replacements
            and not (before.isalnum() or before == "_")
            and not (after.isalnum() or after == "_")
        ):
            token = replacements[token.lower()]
        result.append(token)
        index = after_index
    return "".join(result)


def _callable_name(node: ast.expr) -> str | None:
    """Return a simple or dotted call target, or None for an unsupported target."""
    parts: list[str] = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if not isinstance(node, ast.Name):
        return None
    parts.append(node.id)
    return ".".join(reversed(parts))


def _read_attribute(value: Any, name: str) -> Any:
    if isinstance(value, RecordValue):
        if name in value.fields:
            return value.fields[name]
        raise AttributeError(
            f"Record '{value.record_type}' has no field named '{name}'."
        )
    if isinstance(value, dict):
        if name in value:
            return value[name]
        raise AttributeError(f"Dictionary has no key named '{name}'.")
    raise AttributeError(
        f"Values of type '{_describe(value)}' have no attribute '{name}'."
    )


def _read_index(value: Any, index: Any) -> Any:
    if isinstance(value, (list, tuple, str, bytes, bytearray)):
        if not isinstance(index, int) or isinstance(index, bool):
            raise TypeError("Collection indices must be integers.")
        try:
            return value[index]
        except IndexError as error:
            raise IndexError("Collection index is out of range.") from error
    if isinstance(value, dict):
        if index not in value:
            raise KeyError(f"Dictionary has no key {index!r}.")
        return value[index]
    raise TypeError(
        f"Values of type '{_describe(value)}' cannot be indexed."
    )


def _read_slice(source: Any, start: Any, stop: Any, step: Any) -> Any:
    if not isinstance(source, (list, tuple, str, bytes, bytearray)):
        raise TypeError(
            f"Values of type '{_describe(source)}' cannot be sliced."
        )
    for value in (start, stop, step):
        if value is not None and (not isinstance(value, int) or isinstance(value, bool)):
            raise TypeError("Slice bounds must be integers or none.")
    return source[slice(start, stop, step)]


def _describe(value: Any) -> str:
    if isinstance(value, RecordValue):
        return value.record_type
    if value is None:
        return "none"
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, dict):
        return "dict"
    for name, python_type in (
        ("string", str), ("int", int), ("float", float), ("list", list),
        ("tuple", tuple), ("set", set), ("bytes", bytes),
        ("bytearray", bytearray),
    ):
        if isinstance(value, python_type):
            return name
    return type(value).__name__


def _method(receiver: Any, name: str) -> Callable[..., Any]:
    if isinstance(receiver, RecordValue):
        raise AttributeError(
            f"Record methods are not supported; '{name}' is not a record field."
        )
    if isinstance(receiver, str):
        allowed = _STRING_METHODS
    elif isinstance(receiver, list):
        allowed = _LIST_METHODS
    elif isinstance(receiver, dict):
        allowed = _DICT_METHODS
    elif isinstance(receiver, set):
        allowed = _SET_METHODS
    elif isinstance(receiver, (bytes, bytearray)):
        allowed = _BYTES_METHODS
    else:
        raise AttributeError(
            f"Values of type '{_describe(receiver)}' have no methods."
        )
    if name not in allowed:
        raise AttributeError(
            f"'{_describe(receiver)}' values have no supported method '{name}'."
        )
    method = getattr(receiver, name)
    if isinstance(receiver, dict) and name in ("keys", "values", "items"):
        return lambda: list(getattr(receiver, name)())
    return method


def _validate_mutation(
    runtime: Runtime, receiver: Any, name: str, arguments: list[Any]
) -> None:
    if name == "append" and arguments:
        runtime.validate_container_mutation(receiver, [*receiver, arguments[0]])
    elif name == "insert" and len(arguments) >= 2:
        candidate = list(receiver)
        candidate.insert(arguments[0], arguments[1])
        runtime.validate_container_mutation(receiver, candidate)
    elif name == "extend" and arguments:
        candidate = [*receiver, *arguments[0]]
        runtime.validate_container_mutation(receiver, candidate)
    elif name == "add" and arguments:
        runtime.validate_container_mutation(receiver, receiver | {arguments[0]})
    elif name == "update" and isinstance(receiver, set) and arguments:
        runtime.validate_container_mutation(
            receiver, receiver | set(arguments[0])
        )


def _sequence_items(elts: list[ast.expr], evaluate) -> list[Any]:
    items: list[Any] = []
    for item in elts:
        if isinstance(item, ast.Starred):
            expanded = evaluate(item.value)
            if not isinstance(expanded, (list, tuple, set)):
                raise TypeError(
                    "Starred values must be a list, tuple, or set."
                )
            items.extend(expanded)
        else:
            items.append(evaluate(item))
    return items


def _call_arguments(node: ast.Call, evaluate) -> tuple[list[Any], dict[str, Any]]:
    arguments: list[Any] = []
    for argument in node.args:
        if isinstance(argument, ast.Starred):
            expanded = evaluate(argument.value)
            if not isinstance(expanded, (list, tuple)):
                raise TypeError(
                    "Starred call arguments must be a list or tuple."
                )
            arguments.extend(expanded)
        else:
            arguments.append(evaluate(argument))
    keyword_arguments: dict[str, Any] = {}
    for keyword in node.keywords:
        if keyword.arg is None:
            expanded = evaluate(keyword.value)
            if not isinstance(expanded, dict):
                raise TypeError("Keyword unpacking requires a dictionary.")
            if not all(isinstance(key, str) for key in expanded):
                raise TypeError("Keyword argument names must be strings.")
            keyword_arguments.update(expanded)
        else:
            keyword_arguments[keyword.arg] = evaluate(keyword.value)
    return arguments, keyword_arguments


def parse_expression(source: str) -> ast.expr:
    try:
        expression = ast.parse(_normalize(source), mode="eval").body
    except SyntaxError as error:
        raise SyntaxError(f"Invalid expression: {error.msg}.") from error

    def validate(node: ast.AST) -> None:
        if isinstance(node, ast.Constant):
            if not isinstance(node.value, (str, int, float, bool, type(None))):
                raise SyntaxError("Unsupported literal in expression.")
            return
        if isinstance(node, ast.Name):
            return
        if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
            for item in node.elts:
                validate(item)
            return
        if isinstance(node, ast.Starred):
            validate(node.value)
            return
        if isinstance(node, ast.Dict):
            for key, value in zip(node.keys, node.values):
                if key is not None:
                    validate(key)
                validate(value)
            return
        if isinstance(node, ast.JoinedStr):
            for value in node.values:
                validate(value)
            return
        if isinstance(node, ast.FormattedValue):
            validate(node.value)
            if node.format_spec is not None:
                validate(node.format_spec)
            if node.conversion not in (-1, ord("s"), ord("r"), ord("a")):
                raise SyntaxError("Unsupported conversion in f-string.")
            return
        if isinstance(node, ast.ListComp):
            if (
                len(node.generators) != 1
                or not isinstance(node.generators[0].target, ast.Name)
                or node.generators[0].is_async
            ):
                raise SyntaxError(
                    "List comprehensions require one synchronous identifier target."
                )
            generator = node.generators[0]
            validate(generator.iter)
            for condition in generator.ifs:
                validate(condition)
            validate(node.elt)
            return
        if isinstance(node, ast.UnaryOp):
            if not isinstance(node.op, (ast.UAdd, ast.USub, ast.Not)):
                raise SyntaxError("Unsupported unary operator in expression.")
            validate(node.operand)
            return
        if isinstance(node, ast.BinOp):
            if type(node.op) not in _OPERATORS:
                raise SyntaxError("Unsupported operator in expression.")
            validate(node.left)
            validate(node.right)
            return
        if isinstance(node, ast.BoolOp):
            if not isinstance(node.op, (ast.And, ast.Or)):
                raise SyntaxError("Unsupported boolean operator in expression.")
            for value in node.values:
                validate(value)
            return
        if isinstance(node, ast.Compare):
            if any(type(operation) not in _COMPARISONS for operation in node.ops):
                raise SyntaxError("Unsupported comparison in expression.")
            validate(node.left)
            for comparator in node.comparators:
                validate(comparator)
            return
        if isinstance(node, ast.Attribute):
            validate(node.value)
            return
        if isinstance(node, ast.Subscript):
            validate(node.value)
            validate(node.slice)
            return
        if isinstance(node, ast.Slice):
            for value in (node.lower, node.upper, node.step):
                if value is not None:
                    validate(value)
            return
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Attribute):
                validate(node.func.value)
            else:
                name = _callable_name(node.func)
                if name is None:
                    raise SyntaxError(
                        "Function calls in expressions require a name, "
                        "qualified name, or method receiver."
                    )
            name = (
                _callable_name(node.func)
                if not isinstance(node.func, ast.Attribute)
                else None
            )
            if name == "range" and (
                node.keywords or not 1 <= len(node.args) <= 3
            ):
                raise SyntaxError(
                    "range() requires one to three positional arguments."
                )
            if any(isinstance(argument, ast.Starred) for argument in node.args):
                for argument in node.args:
                    if isinstance(argument, ast.Starred):
                        validate(argument.value)
                    else:
                        validate(argument)
            else:
                for argument in node.args:
                    validate(argument)
            for keyword in node.keywords:
                validate(keyword.value)
            return
        if isinstance(node, ast.Load):
            return
        raise SyntaxError("Unsupported syntax in expression.")

    validate(expression)
    return expression


def _number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def evaluate_expression(source: str, runtime: Runtime) -> Any:
    expression = parse_expression(source)

    def evaluate(
        node: ast.expr, local_values: dict[str, Any] | None = None
    ) -> Any:
        if isinstance(node, ast.Constant):
            if isinstance(node.value, (str, int, float, bool, type(None))):
                return node.value
            raise SyntaxError("Unsupported literal in expression.")
        if isinstance(node, ast.Name):
            if local_values is not None and node.id in local_values:
                return local_values[node.id]
            variable = runtime.get_var(node.id)
            if variable is None:
                raise ValueError(f"Variable '{node.id}' is not defined.")
            return variable["value"]
        if isinstance(node, ast.List):
            return _sequence_items(node.elts, lambda item: evaluate(item, local_values))
        if isinstance(node, ast.Tuple):
            return tuple(
                _sequence_items(node.elts, lambda item: evaluate(item, local_values))
            )
        if isinstance(node, ast.Set):
            return set(
                _sequence_items(node.elts, lambda item: evaluate(item, local_values))
            )
        if isinstance(node, ast.Dict):
            result: dict[Any, Any] = {}
            for key, value in zip(node.keys, node.values):
                if key is None:
                    expanded = evaluate(value, local_values)
                    if not isinstance(expanded, dict):
                        raise TypeError(
                            "Dictionary unpacking requires a dictionary."
                        )
                    result.update(expanded)
                else:
                    result[evaluate(key, local_values)] = evaluate(
                        value, local_values
                    )
            return result
        if isinstance(node, ast.JoinedStr):
            return "".join(str(evaluate(value, local_values)) for value in node.values)
        if isinstance(node, ast.FormattedValue):
            value = evaluate(node.value, local_values)
            if node.conversion == ord("s"):
                value = str(value)
            elif node.conversion == ord("r"):
                value = repr(value)
            elif node.conversion == ord("a"):
                value = ascii(value)
            elif node.conversion != -1:
                raise SyntaxError("Unsupported conversion in f-string.")
            format_spec = (
                evaluate(node.format_spec, local_values)
                if node.format_spec is not None else ""
            )
            return format(value, format_spec)
        if isinstance(node, ast.ListComp):
            generator = node.generators[0]
            iterable = evaluate(generator.iter, local_values)
            result = []
            for value in iterable:
                comprehension_values = dict(local_values or ())
                comprehension_values[generator.target.id] = value
                include_value = True
                for condition in generator.ifs:
                    condition_value = evaluate(condition, comprehension_values)
                    if not isinstance(condition_value, bool):
                        raise TypeError(
                            "List comprehension conditions must evaluate to booleans."
                        )
                    if not condition_value:
                        include_value = False
                        break
                if include_value:
                    result.append(evaluate(node.elt, comprehension_values))
            return result
        if isinstance(node, ast.Attribute):
            return _read_attribute(
                evaluate(node.value, local_values), node.attr
            )
        if isinstance(node, ast.Subscript):
            source = evaluate(node.value, local_values)
            if isinstance(node.slice, ast.Slice):
                start = (
                    evaluate(node.slice.lower, local_values)
                    if node.slice.lower is not None else None
                )
                stop = (
                    evaluate(node.slice.upper, local_values)
                    if node.slice.upper is not None else None
                )
                step = (
                    evaluate(node.slice.step, local_values)
                    if node.slice.step is not None else None
                )
                return _read_slice(source, start, stop, step)
            return _read_index(source, evaluate(node.slice, local_values))
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Attribute):
                dotted = _callable_name(node.func)
                first = dotted.split(".")[0] if dotted else None
                if dotted is not None and (
                    first is None or runtime.get_var(first) is None
                ):
                    name = dotted
                else:
                    receiver = evaluate(node.func.value, local_values)
                    arguments, keyword_arguments = _call_arguments(
                        node, lambda item: evaluate(item, local_values)
                    )
                    method = _method(receiver, node.func.attr)
                    _validate_mutation(
                        runtime, receiver, node.func.attr, arguments
                    )
                    return method(*arguments, **keyword_arguments)
            else:
                name = _callable_name(node.func)
                assert name is not None
            if name == "set" and not node.args and not node.keywords:
                return set()
            arguments, keyword_arguments = _call_arguments(
                node, lambda item: evaluate(item, local_values)
            )
            if name == "range":
                if keyword_arguments:
                    raise TypeError("range() does not accept named arguments.")
                return range(*arguments)
            invoker = runtime.function_invoker
            if invoker is None:
                from .interpreter import _invoke_function

                invoker = lambda function_name, args, kwargs: _invoke_function(
                    function_name, args, runtime, kwargs
                )
            return invoker(name, arguments, keyword_arguments)
        if isinstance(node, ast.UnaryOp):
            value = evaluate(node.operand, local_values)
            if isinstance(node.op, ast.UAdd) and _number(value):
                return value
            if isinstance(node.op, ast.USub) and _number(value):
                return -value
            if isinstance(node.op, ast.Not) and isinstance(value, bool):
                return not value
            raise TypeError("Unary operators require a number or boolean.")
        if isinstance(node, ast.BinOp):
            operation = _OPERATORS.get(type(node.op))
            left = evaluate(node.left, local_values)
            right = evaluate(node.right, local_values)
            if operation is None:
                raise SyntaxError("Unsupported operator in expression.")
            if not _number(left) or not _number(right):
                raise TypeError("Arithmetic operators require numeric operands.")
            result = operation(left, right)
            if not _number(result):
                raise TypeError("Arithmetic result is outside the supported numeric types.")
            return result
        if isinstance(node, ast.BoolOp):
            if isinstance(node.op, ast.And):
                for item in node.values:
                    value = evaluate(item, local_values)
                    if not isinstance(value, bool):
                        raise TypeError("Boolean operators require boolean operands.")
                    if not value:
                        return False
                return True
            if isinstance(node.op, ast.Or):
                for item in node.values:
                    value = evaluate(item, local_values)
                    if not isinstance(value, bool):
                        raise TypeError("Boolean operators require boolean operands.")
                    if value:
                        return True
                return False
            raise SyntaxError("Unsupported boolean operator in expression.")
        if isinstance(node, ast.Compare):
            left = evaluate(node.left, local_values)
            for operation_node, comparator in zip(node.ops, node.comparators):
                right = evaluate(comparator, local_values)
                operation = _COMPARISONS.get(type(operation_node))
                if operation is None:
                    raise SyntaxError("Unsupported comparison in expression.")
                if not operation(left, right):
                    return False
                left = right
            return True
        raise SyntaxError("Unsupported value in expression.")

    return evaluate(expression)
