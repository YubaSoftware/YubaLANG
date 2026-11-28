import ast
import operator
from typing import Any, Callable

from . import arith, iteration, string_builtins, utilities
from .collection_commands import execute_collection_command
from .conversion import convert_value, parse_value
from .enums import execute_enum_command, execute_type_command
from .expressions import evaluate_expression
from .ffi import execute_ffi
from .io_commands import execute_io_command
from .patterns import parse_pattern, pattern_names, unpack_pattern
from .runtime import (
    LambdaValue,
    RecordDefinition,
    RecordValue,
    Runtime,
    TYPES,
)
from .string_builtins import resolve
from .type_system import FunctionReference, format_type, parse_type


def _assign(runtime: Runtime, name: str, value: Any) -> None:
    runtime.assign_var(name, value)


_COMPOUND_ASSIGN = {
    "+=": operator.add,
    "-=": operator.sub,
    "*=": operator.mul,
    "/=": operator.truediv,
    "//=": operator.floordiv,
    "%=": operator.mod,
    "**=": operator.pow,
    "&=": operator.and_,
    "|=": operator.or_,
    "^=": operator.xor,
    "<<=": operator.lshift,
    ">>=": operator.rshift,
}


def _destructuring_types(
    type_source: str, names: list[str]
) -> list[str]:
    spec = parse_type(type_source)
    if spec.name == "tuple" and spec.arguments:
        if len(spec.arguments) == 1:
            return [format_type(spec.arguments[0]) for _ in names]
        if len(spec.arguments) != len(names):
            raise ValueError(
                f"Destructuring declaration has {len(names)} target(s) but "
                f"the tuple type has {len(spec.arguments)} element type(s)."
            )
        return [format_type(argument) for argument in spec.arguments]
    if spec.name == "list" and spec.arguments:
        return [format_type(spec.arguments[0]) for _ in names]
    raise TypeError(
        "Destructuring declarations require a tuple or list type."
    )



def evaluate_condition(condition: str, runtime: Runtime) -> bool:
    value = evaluate_expression(condition, runtime)
    if not isinstance(value, bool):
        raise TypeError("Condition must evaluate to a boolean.")
    return value


def _builtin_callable(name: str, value: Any) -> Any:
    if name == "abs":
        return abs(value)
    if name == "bool":
        return bool(value)
    if name == "chr":
        return string_builtins.character(value)
    if name == "int":
        return convert_value(value, "int")
    if name == "float":
        return convert_value(value, "float")
    if name == "str":
        return convert_value(value, "string")
    if name == "ord":
        return string_builtins.ordinal(value)
    if name == "round":
        return round(value)
    if name == "ascii":
        return string_builtins.ascii_value(value)
    if name == "repr":
        return string_builtins.representation(value)
    if name == "len":
        return utilities.length(value)
    raise ValueError(f"Unknown built-in callable: {name}")


def execute_command(
    parts: list[str],
    runtime: Runtime,
    invoke_function: Callable[[str, list[Any]], Any],
    source_name: str = "<memory>",
) -> None:
    command = parts[0]

    if command == "set":
        compound_index = next(
            (
                index for index in range(2, len(parts))
                if parts[index] in _COMPOUND_ASSIGN
            ),
            None,
        )
        if compound_index is not None:
            target_source = " ".join(parts[1:compound_index])
            value_source = " ".join(parts[compound_index + 1:])
            if (
                not target_source.isidentifier()
                or not value_source
                or compound_index != 2
            ):
                raise SyntaxError(
                    "Usage: set <name> <operator>= <value>"
                )
            variable = runtime.require_var(target_source)
            operation = _COMPOUND_ASSIGN[parts[compound_index]]
            value = evaluate_expression(value_source, runtime)
            try:
                result = operation(variable["value"], value)
            except TypeError as error:
                raise TypeError(
                    f"Operator '{parts[compound_index]}' cannot be applied "
                    f"to '{variable['type']}' and "
                    f"'{Runtime.type_name(value)}'."
                ) from error
            _assign(runtime, target_source, result)
            return

    if command == "set" and "=" in parts[1:]:
        equal_index = parts.index("=", 1)
        target_source = " ".join(parts[1:equal_index])
        value_source = " ".join(parts[equal_index + 1:])
        if not target_source or not value_source:
            raise SyntaxError("Usage: set <name> = <value>")
        if not any(character in target_source for character in "([,"):
            if not target_source.isidentifier():
                raise SyntaxError("Assignment target must be an identifier.")
        target = parse_pattern(target_source, "assignment target")
        value = evaluate_expression(value_source, runtime)
        for name, item in unpack_pattern(target, value):
            _assign(runtime, name, item)
        return

    if command == "ffi":
        execute_ffi(parts, runtime, source_name)
        return

    if command == "define":
        if (
            len(parts) < 5
            or parts[1] not in ("var", "const")
            or "=" not in parts[2:]
        ):
            raise SyntaxError(
                "Usage: define var <name>: <type> = <value> "
                "(or define const for an immutable value)"
            )
        is_constant = parts[1] == "const"
        equal_index = parts.index("=", 2)
        declaration = " ".join(parts[2:equal_index])
        if ":" not in declaration:
            raise SyntaxError("Usage: define var <name>: <type> = <value>")
        target_source, type_source = declaration.split(":", 1)
        target_source, type_source = target_source.strip(), type_source.strip()
        if not target_source or not type_source:
            raise SyntaxError("Usage: define var <name>: <type> = <value>")
        if not any(character in target_source for character in "([,"):
            if not target_source.isidentifier():
                raise SyntaxError("Variable name must be an identifier.")
        value_type = format_type(parse_type(type_source))
        if not runtime.type_is_known(value_type):
            raise ValueError(f"Unknown type: {value_type}")
        value_source = " ".join(parts[equal_index + 1:])
        define = runtime.define_const if is_constant else runtime.define_var
        if target_source.isidentifier():
            if value_type in runtime.records:
                variable = runtime.get_var(value_source)
                if variable is None or variable["type"] != value_type:
                    raise TypeError(f"Expected a '{value_type}' record variable.")
                value = variable["value"]
            else:
                value = parse_value(value_source, value_type, runtime)
            define(target_source, value_type, value)
            return
        target = parse_pattern(target_source, "declaration target")
        names = pattern_names(target)
        element_types = _destructuring_types(value_type, names)
        try:
            value = parse_value(value_source, value_type, runtime)
        except (TypeError, ValueError) as error:
            raise TypeError(
                f"Cannot destructure a value that does not match type "
                f"'{value_type}'."
            ) from error
        pairs = unpack_pattern(target, value)
        if len(pairs) != len(element_types):
            raise ValueError("Destructuring declaration type does not match its targets.")
        for (name, item), item_type in zip(pairs, element_types):
            define(name, item_type, item)
        return

    if command == "record":
        if len(parts) < 3 or parts[1] != "define":
            if len(parts) >= 2 and parts[1] == "create":
                _create_record(parts, runtime)
                return
            raise SyntaxError(
                "Usage: record define <name> <field>:<type>[=<default>]... or "
                "record create <type> <variable> <field-value>..."
            )
        name = parts[2]
        if not name.isidentifier() or name in TYPES or name in runtime.records:
            raise ValueError(f"Invalid or already defined record type '{name}'.")
        if len(parts) < 4:
            raise SyntaxError("A record must define at least one field.")
        fields: dict[str, str] = {}
        defaults: dict[str, str] = {}
        constants: set[str] = set()
        constant_next = False
        for declaration in parts[3:]:
            if declaration in ("const", "mutable"):
                constant_next = declaration == "const"
                continue
            if ":" not in declaration:
                raise SyntaxError(
                    "Record fields must use <field>:<type>[=<default>] syntax."
                )
            field_name, field_type = declaration.split(":", 1)
            field_type, default_separator, default_source = field_type.partition("=")
            if not field_name.isidentifier() or field_name in fields:
                raise ValueError(f"Invalid or duplicate record field '{field_name}'.")
            if default_separator and not default_source:
                raise SyntaxError(
                    f"Default value for record field '{field_name}' is missing."
                )
            if not runtime.type_is_known(field_type):
                raise ValueError(f"Unknown type: {field_type}")
            fields[field_name] = format_type(parse_type(field_type))
            if constant_next:
                constants.add(field_name)
                constant_next = False
            if default_separator:
                defaults[field_name] = default_source
        runtime.records[name] = RecordDefinition(fields, defaults, constants)
        return

    if command == "enum":
        execute_enum_command(parts, runtime)
        return

    if command == "type" and len(parts) >= 2 and parts[1] in ("define", "alias"):
        execute_type_command(parts, runtime)
        return

    if command == "assert":
        if len(parts) not in (2, 3):
            raise SyntaxError("Usage: assert <boolean> [message]")
        condition = resolve(parts[1], runtime)
        if not isinstance(condition, bool):
            raise TypeError("Assertion condition must be a boolean.")
        if not condition:
            message = resolve(parts[2], runtime) if len(parts) == 3 else "Assertion failed."
            if not isinstance(message, str):
                raise TypeError("Assertion message must be a string.")
            raise AssertionError(f"Assertion failed: {message}")
        return

    if command == "convert":
        if len(parts) == 4 and parts[2] == "to":
            name, target_type = parts[1], parts[3]
        elif len(parts) == 3:
            name, target_type = parts[1], parts[2]
        else:
            raise SyntaxError("Usage: convert <variable> to <type>")
        variable = runtime.require_var(name)
        try:
            converted = convert_value(variable["value"], target_type)
        except (TypeError, ValueError, OverflowError) as error:
            raise ValueError(f"Cannot convert '{name}' to {target_type}: {error}") from error
        runtime.update_var(name, target_type, converted)
        return

    if command == "arith":
        single_ops = {"abs", "round", "sum", "bin", "hex", "oct"}
        if len(parts) == 3 and parts[1] in single_ops | {"max", "min"}:
            result = arith.arith(parts[1], parts[2], None, runtime)
        elif len(parts) == 4 and parts[1] not in single_ops:
            result = arith.arith(parts[1], parts[2], parts[3], runtime)
        else:
            raise SyntaxError(
                "Usage: arith <abs|round|sum|bin|hex|oct> <value> "
                "OR arith <operation> <value1> <value2>"
            )
        print(result)
        return

    if command == "compare":
        if len(parts) < 4:
            raise SyntaxError("Usage: compare <expression> <bool_variable>")
        destination_name = parts[-1]
        destination = runtime.require_var(destination_name)
        if destination["type"] != "bool":
            raise TypeError(
                f"Destination variable '{destination_name}' must be a defined boolean."
            )
        result = evaluate_expression(" ".join(parts[1:-1]), runtime)
        if not isinstance(result, bool):
            raise TypeError("Comparison expression must evaluate to a boolean.")
        runtime.assign_var(destination_name, result)
        return

    if command in ("list", "dict", "set", "tuple"):
        execute_collection_command(parts, runtime)
        return

    if command in ("text", "open", "close", "file"):
        execute_io_command(parts, runtime)
        return

    if command in ("getattr", "hasattr", "setattr"):
        _execute_attribute_command(parts, runtime)
        return

    if command in ("bytes", "bytearray"):
        if len(parts) != 3:
            raise SyntaxError(f"Usage: {command} <value_or_var> <dest_var>")
        value = resolve(parts[1], runtime)
        result = value if isinstance(value, TYPES[command]) else str(value).encode("utf-8")
        if command == "bytearray":
            result = bytearray(result)
        _assign(runtime, parts[2], result)
        return

    if command in ("all", "any"):
        if len(parts) != 3:
            raise SyntaxError(f"Usage: {command} <collection> <dest_bool_var>")
        collection = runtime.require_var(parts[1])
        if collection["type"] not in ("list", "tuple", "set", "dict"):
            raise TypeError(f"Variable '{parts[1]}' must be a defined collection.")
        _assign(
            runtime, parts[2],
            utilities.all_values(collection["value"]) if command == "all"
            else utilities.any_values(collection["value"]),
        )
        return

    if command in ("ascii", "repr"):
        if len(parts) != 3:
            raise SyntaxError(f"Usage: {command} <value_or_var> <dest_string_var>")
        value = resolve(parts[1], runtime)
        result = (
            string_builtins.ascii_value(value) if command == "ascii"
            else string_builtins.representation(value)
        )
        _assign(runtime, parts[2], result)
        return

    if command == "chr":
        if len(parts) != 3:
            raise SyntaxError("Usage: chr <integer_or_var> <dest_string_var>")
        _assign(runtime, parts[2], string_builtins.character(resolve(parts[1], runtime)))
        return

    if command == "ord":
        if len(parts) != 3:
            raise SyntaxError("Usage: ord <character_or_var> <dest_int_var>")
        _assign(runtime, parts[2], string_builtins.ordinal(resolve(parts[1], runtime)))
        return

    if command == "format":
        if len(parts) not in (3, 4):
            raise SyntaxError("Usage: format <value_or_var> <format_spec> <dest_string_var>")
        value, spec, destination = resolve(parts[1], runtime), parts[2], parts[-1]
        if len(parts) == 3:
            value, spec, destination = resolve(parts[1], runtime), "", parts[2]
        else:
            spec = resolve(spec, runtime)
        _assign(runtime, destination, string_builtins.format_value(value, str(spec)))
        return

    if command == "enumerate":
        if len(parts) not in (3, 4):
            raise SyntaxError("Usage: enumerate <iterable> <dest_list> [start]")
        values = resolve(parts[1], runtime)
        start = int(resolve(parts[3], runtime)) if len(parts) == 4 else 0
        _assign(runtime, parts[2], iteration.enumerate_values(values, start))
        return

    if command in ("map", "filter"):
        if len(parts) != 4:
            raise SyntaxError(f"Usage: {command} <function> <iterable> <dest_list>")
        function_name, iterable, destination = parts[1], resolve(parts[2], runtime), parts[3]
        callback_variable = runtime.get_var(function_name)
        lambda_callback = None
        if (
            callback_variable is not None
            and isinstance(callback_variable["value"], LambdaValue)
        ):
            lambda_callback = callback_variable["value"]
        elif (
            callback_variable is not None
            and isinstance(callback_variable["value"], FunctionReference)
        ):
            function_name = callback_variable["value"].name

        def callback(value: Any) -> Any:
            if lambda_callback is not None:
                return lambda_callback(value)
            if runtime.resolve_function(function_name) is not None:
                result = invoke_function(function_name, [value])
                if result is None:
                    raise ValueError(
                        f"Function '{function_name}' must return a value when used by {command}."
                    )
                return result
            return _builtin_callable(function_name, value)

        result = (
            iteration.map_values(callback, iterable) if command == "map"
            else iteration.filter_values(callback, iterable)
        )
        _assign(runtime, destination, result)
        return

    if command == "iter":
        if len(parts) != 3:
            raise SyntaxError("Usage: iter <iterable> <dest_iterator_var>")
        iterator_value = iter(resolve(parts[1], runtime))
        if hasattr(iterator_value, "close"):
            runtime.register_resource(iterator_value)
        if runtime.get_var(parts[2]) is None:
            runtime.define_var(parts[2], "iterator", iterator_value)
        else:
            _assign(runtime, parts[2], iterator_value)
        return

    if command == "next":
        if len(parts) not in (3, 4):
            raise SyntaxError("Usage: next <iterator> <destination> [default]")
        iterator_value = runtime.require_var(parts[1])
        if iterator_value["type"] != "iterator":
            raise TypeError(f"Variable '{parts[1]}' is not an iterator.")
        default = resolve(parts[3], runtime) if len(parts) == 4 else ...
        try:
            result = next(iterator_value["value"]) if default is ... else next(iterator_value["value"], default)
        except StopIteration as error:
            raise ValueError("next() called on an exhausted iterator.") from error
        _assign(runtime, parts[2], result)
        return

    if command == "range":
        if len(parts) not in (3, 4, 5):
            raise SyntaxError("Usage: range <stop> <dest_list> OR range <start> <stop> <dest_list> [step]")
        if len(parts) == 3:
            start, stop, step, destination = 0, int(resolve(parts[1], runtime)), 1, parts[2]
        elif len(parts) == 4:
            start, stop, step, destination = (
                int(resolve(parts[1], runtime)), int(resolve(parts[2], runtime)), 1, parts[3]
            )
        else:
            start, stop, step, destination = (
                int(resolve(parts[1], runtime)), int(resolve(parts[2], runtime)),
                int(resolve(parts[4], runtime)), parts[3],
            )
        if step == 0:
            raise ValueError("range() arg 3 must not be zero.")
        _assign(runtime, destination, list(range(start, stop, step)))
        return

    if command == "reversed":
        if len(parts) != 3:
            raise SyntaxError("Usage: reversed <iterable> <dest_list>")
        _assign(runtime, parts[2], iteration.reversed_values(resolve(parts[1], runtime)))
        return

    if command == "slice":
        if len(parts) not in (5, 6):
            raise SyntaxError("Usage: slice <iterable> <start> <stop> <dest> [step]")
        source = runtime.require_var(parts[1])
        start, stop = int(resolve(parts[2], runtime)), int(resolve(parts[3], runtime))
        step = int(resolve(parts[5], runtime)) if len(parts) == 6 else None
        result = iteration.slice_values(source["value"], start, stop, step)
        destination = parts[4]
        runtime.assign_var(destination, result)
        return

    if command == "sorted":
        if len(parts) not in (3, 4):
            raise SyntaxError("Usage: sorted <iterable> <dest_list> [reverse]")
        reverse = resolve(parts[3], runtime) if len(parts) == 4 else False
        if not isinstance(reverse, bool):
            raise TypeError("sorted() reverse option must be boolean.")
        _assign(runtime, parts[2], iteration.sorted_values(resolve(parts[1], runtime), reverse))
        return

    if command == "zip":
        if len(parts) < 4:
            raise SyntaxError("Usage: zip <iterable1> <iterable2> [...] <dest_list>")
        values = [resolve(name, runtime) for name in parts[1:-1]]
        _assign(runtime, parts[-1], iteration.zip_values(*values))
        return

    if command in ("bool", "callable", "id", "len", "type", "vars", "wait"):
        _execute_utility_command(parts, runtime)
        return

    raise SyntaxError(f"Unknown command: {command}")


def _execute_attribute_command(parts: list[str], runtime: Runtime) -> None:
    command = parts[0]
    if len(parts) != 4:
        raise SyntaxError(f"Usage: {command} <variable> <attribute> <destination>")
    obj_name, attribute_token, destination = parts[1], parts[2], parts[3]
    variable = runtime.require_var(obj_name)
    obj = variable["value"]
    if isinstance(obj, RecordValue):
        quoted = (
            len(attribute_token) >= 2
            and attribute_token[0] == attribute_token[-1]
            and attribute_token[0] in ("'", '"')
        )
        attr_name = resolve(attribute_token, runtime) if quoted else attribute_token
        if attr_name not in obj.fields:
            if command == "hasattr":
                _assign(runtime, destination, False)
                return
            raise AttributeError(
                f"Record '{variable['type']}' has no field '{attr_name}'."
            )
        if command == "getattr":
            runtime.assign_var(destination, obj.fields[attr_name])
        elif command == "hasattr":
            _assign(runtime, destination, True)
        else:
            field_type = runtime.records[variable["type"]].fields[attr_name]
            if attr_name in runtime.records[variable["type"]].constants:
                raise TypeError(
                    f"Field '{attr_name}' of record '{variable['type']}' "
                    "is immutable."
                )
            value = resolve(parts[3], runtime)
            if not runtime.value_matches_type(field_type, value):
                raise TypeError(
                    f"Field '{attr_name}' of record '{variable['type']}' "
                    f"requires type '{field_type}'."
                )
            if field_type == "float":
                value = float(value)
            obj.fields[attr_name] = value
    else:
        attr_name = resolve(attribute_token, runtime)
        if command == "getattr":
            value = obj[attr_name] if isinstance(obj, dict) else getattr(obj, attr_name)
            runtime.assign_var(destination, value)
        elif command == "hasattr":
            _assign(runtime, destination, attr_name in obj if isinstance(obj, dict) else hasattr(obj, attr_name))
        elif isinstance(obj, dict):
            value = resolve(parts[3], runtime)
            obj[attr_name] = value
        else:
            value = resolve(parts[3], runtime)
            setattr(obj, attr_name, value)


def _create_record(parts: list[str], runtime: Runtime) -> None:
    if len(parts) < 4:
        raise SyntaxError(
            "Usage: record create <type> <variable> <field-value>..."
        )
    if parts[2] not in runtime.records:
        raise ValueError(f"Unknown record type: {parts[2]}")
    record_type, variable_name = parts[2], parts[3]
    definition = runtime.records[record_type]
    field_names = list(definition.fields)

    positional: list[str] = []
    named: dict[str, str] = {}
    saw_named = False
    for token in parts[4:]:
        field_name, separator, value = token.partition("=")
        if separator and field_name.isidentifier():
            if not value:
                raise SyntaxError(
                    f"Missing value for named record field '{field_name}'."
                )
            saw_named = True
            if field_name in named:
                raise TypeError(
                    f"Record '{record_type}' got field '{field_name}' more than once."
                )
            named[field_name] = value
        else:
            if saw_named:
                raise SyntaxError(
                    "Positional record field values must come before named fields."
                )
            positional.append(token)

    if len(positional) > len(field_names):
        raise TypeError(
            f"Record '{record_type}' expects {len(field_names)} field value(s), "
            f"but got {len(positional)} positional value(s)."
        )
    assigned: dict[str, str] = dict(zip(field_names, positional))
    for field_name in named:
        if field_name not in definition.fields:
            raise TypeError(
                f"Record '{record_type}' has no field named '{field_name}'."
            )
        if field_name in assigned:
            raise TypeError(
                f"Record '{record_type}' got field '{field_name}' more than once."
            )
        assigned[field_name] = named[field_name]
    missing = [
        field_name for field_name in field_names
        if field_name not in assigned and field_name not in definition.defaults
    ]
    if missing:
        raise TypeError(
            f"Record '{record_type}' is missing required field(s): "
            f"{', '.join(missing)}."
        )

    values: dict[str, Any] = {}
    for field_name, token in assigned.items():
        values[field_name] = resolve(token, runtime)
    for field_name in field_names:
        if field_name in values:
            continue
        try:
            values[field_name] = parse_value(
                definition.defaults[field_name],
                definition.fields[field_name],
                runtime,
            )
        except (TypeError, ValueError) as error:
            raise TypeError(
                f"Field '{field_name}' of record '{record_type}' "
                f"requires type '{definition.fields[field_name]}'."
            ) from error

    fields: dict[str, Any] = {}
    for field_name in field_names:
        value = values[field_name]
        expected_type = definition.fields[field_name]
        if not runtime.value_matches_type(expected_type, value):
            raise TypeError(
                f"Field '{field_name}' of record '{record_type}' "
                f"requires type '{expected_type}'."
            )
        if expected_type == "float":
            value = float(value)
        fields[field_name] = value
    runtime.define_var(variable_name, record_type, RecordValue(record_type, fields))


def _execute_utility_command(parts: list[str], runtime: Runtime) -> None:
    command = parts[0]
    if command == "bool" and len(parts) == 3:
        _assign(runtime, parts[2], bool(resolve(parts[1], runtime)))
    elif command == "callable" and len(parts) == 3:
        variable = runtime.get_var(parts[1])
        result = runtime.resolve_function(parts[1]) is not None or parts[1] in {
            "abs", "ascii", "bool", "chr", "float", "int", "len", "ord",
            "repr", "round", "str",
        }
        result = result or (
            variable is not None and isinstance(variable["value"], FunctionReference)
        )
        _assign(runtime, parts[2], result)
    elif command == "id" and len(parts) == 3:
        _assign(runtime, parts[2], id(runtime.require_var(parts[1])["value"]))
    elif command == "len" and len(parts) == 3:
        _assign(runtime, parts[2], utilities.length(runtime.require_var(parts[1])["value"]))
    elif command == "type" and len(parts) == 3:
        variable = runtime.require_var(parts[1])
        _assign(runtime, parts[2], utilities.type_name(variable["value"], variable["type"]))
    elif command == "vars" and len(parts) == 1:
        merged = {}
        for scope in runtime.scopes:
            merged.update(scope)
        print("--- Active Scope Variables ---")
        for name, variable in merged.items():
            print(f"{name}: {variable['type']} = {variable['value']}")
        print("--- Defined Functions ---")
        for name in runtime.functions:
            print(f"func {name}")
    elif command == "wait" and len(parts) == 2:
        import time
        time.sleep(float(resolve(parts[1], runtime)))
    else:
        raise SyntaxError(f"Invalid {command} command or arguments.")
