"""Evaluation of YubaLANG's expression grammar without Python eval."""

import ast
import operator
import re
from typing import Any, Callable

from .runtime import Runtime


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
        if isinstance(node, ast.Dict):
            for key, value in zip(node.keys, node.values):
                if key is None:
                    raise SyntaxError(
                        "Dictionary unpacking is not supported in expressions."
                    )
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
        if isinstance(node, ast.Call):
            name = _callable_name(node.func)
            if name is None:
                raise SyntaxError(
                    "Function calls in expressions require a name or qualified name."
                )
            if name == "range" and (
                node.keywords or not 1 <= len(node.args) <= 3
            ):
                raise SyntaxError(
                    "range() requires one to three positional arguments."
                )
            if any(isinstance(argument, ast.Starred) for argument in node.args):
                raise SyntaxError(
                    "Argument unpacking is not supported in expressions."
                )
            for argument in node.args:
                validate(argument)
            for keyword in node.keywords:
                if keyword.arg is None:
                    raise SyntaxError(
                        "Keyword unpacking is not supported in expressions."
                    )
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
            return [evaluate(item, local_values) for item in node.elts]
        if isinstance(node, ast.Tuple):
            return tuple(evaluate(item, local_values) for item in node.elts)
        if isinstance(node, ast.Set):
            return {evaluate(item, local_values) for item in node.elts}
        if isinstance(node, ast.Dict):
            return {
                evaluate(key, local_values): evaluate(value, local_values)
                for key, value in zip(node.keys, node.values)
            }
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
        if isinstance(node, ast.Call):
            name = _callable_name(node.func)
            assert name is not None
            if name == "set" and not node.args and not node.keywords:
                return set()
            if name == "range":
                if node.keywords:
                    raise TypeError("range() does not accept named arguments.")
                return range(
                    *(evaluate(argument, local_values) for argument in node.args)
                )
            arguments = [
                evaluate(argument, local_values) for argument in node.args
            ]
            keyword_arguments = {
                keyword.arg: evaluate(keyword.value, local_values)
                for keyword in node.keywords
                if keyword.arg is not None
            }
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
