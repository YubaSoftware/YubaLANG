import io
from io import IOBase

from .expressions import evaluate_expression
from .runtime import Runtime
from .string_builtins import resolve


def _file_variable(runtime: Runtime, name: str) -> tuple[dict, IOBase]:
    variable = runtime.require_var(name)
    file_obj = variable["value"]
    if variable["type"] != "file" or not isinstance(file_obj, IOBase):
        raise TypeError(f"Variable '{name}' is not a file.")
    if file_obj.closed:
        raise ValueError(f"File '{name}' is closed.")
    return variable, file_obj


def _integer(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{label} must be an integer.")
    return value


def _write_value(file_obj: IOBase, content: object) -> None:
    if "b" in file_obj.mode:
        if not isinstance(content, (bytes, bytearray)):
            raise TypeError("Binary files require a bytes or bytearray value.")
    elif not isinstance(content, str):
        raise TypeError("Text files require a string value.")
    file_obj.write(content)


def execute_io_command(parts: list[str], runtime: Runtime) -> None:
    if parts[0] == "text":
        if len(parts) < 3:
            raise SyntaxError("Usage: text <input/output> <value>")
        action = parts[1]
        if action == "output":
            value = " ".join(parts[2:])
            try:
                result = evaluate_expression(value, runtime)
            except SyntaxError:
                if any(operator in value for operator in ("+", "-", "*", "/", "%", "(", ")", "<", ">", "==", "!=")):
                    raise
                result = resolve(value, runtime)
            print(result)
            return
        if action == "input" and len(parts) == 3:
            variable = runtime.require_var(parts[2])
            if variable["type"] != "string":
                raise TypeError(f"Variable '{parts[2]}' must be a string for text input.")
            runtime.assign_var(parts[2], input())
            return
        raise SyntaxError("Usage: text <input/output> <value>")

    if parts[0] == "open" and len(parts) == 4:
        path, mode, destination = (resolve(parts[1], runtime), resolve(parts[2], runtime), parts[3])
        if not isinstance(path, str) or not isinstance(mode, str):
            raise TypeError("open() path and mode must be strings.")
        existing = runtime.get_var(destination)
        if existing is not None and existing["type"] != "file":
            raise TypeError(f"Variable '{destination}' must be a file destination.")
        file_obj = open(path, mode, encoding=None if "b" in mode else "utf-8")
        runtime.register_file(file_obj)
        if existing is None:
            runtime.define_var(destination, "file", file_obj)
        else:
            runtime.assign_var(destination, file_obj)
        return

    if parts[0] == "close" and len(parts) == 2:
        variable = runtime.require_var(parts[1])
        value = variable["value"]
        if variable["type"] not in ("file", "iterator") and not hasattr(value, "close"):
            raise TypeError(
                f"Variable '{parts[1]}' is not an open file, iterator, or handle."
            )
        if not hasattr(value, "close"):
            raise TypeError(f"Variable '{parts[1]}' is not an open file or handle.")
        runtime.close_resource(value)
        return

    if parts[0] != "file":
        raise SyntaxError(f"Invalid {parts[0]} command or arguments.")

    if len(parts) < 3:
        raise SyntaxError(
            "Usage: file <read|write|readline|readlines|writelines|seek|tell|"
            "flush|truncate> <file_variable> [arguments]"
        )
    action = parts[1]
    _, file_obj = _file_variable(runtime, parts[2])
    binary = "b" in file_obj.mode

    if action == "read" and len(parts) in (4, 5):
        destination_name = parts[-1]
        destination = runtime.require_var(destination_name)
        expected_type = "bytes" if binary else "string"
        if destination["type"] != expected_type and not (
            binary and destination["type"] == "bytearray"
        ):
            raise TypeError(
                f"Reading this file requires a '{expected_type}' destination."
            )
        count = -1
        if len(parts) == 5:
            count = _integer(resolve(parts[3], runtime), "Read count")
            if count < 0:
                raise ValueError("Read count must not be negative.")
        content = file_obj.read(count)
        if destination["type"] == "bytearray":
            content = bytearray(content)
        runtime.assign_var(destination_name, content)
        return

    if action == "readline" and len(parts) == 4:
        destination_name = parts[3]
        destination = runtime.require_var(destination_name)
        expected_type = "bytes" if binary else "string"
        if destination["type"] != expected_type and not (
            binary and destination["type"] == "bytearray"
        ):
            raise TypeError(
                f"Reading this file requires a '{expected_type}' destination."
            )
        content = file_obj.readline()
        if destination["type"] == "bytearray":
            content = bytearray(content)
        runtime.assign_var(destination_name, content)
        return

    if action == "readlines" and len(parts) == 4:
        destination_name = parts[3]
        destination = runtime.require_var(destination_name)
        expected_type = "list"
        if destination["type"] != expected_type:
            raise TypeError("Reading file lines requires a 'list' destination.")
        lines = file_obj.readlines()
        if not binary:
            lines = [str(line) for line in lines]
        runtime.assign_var(destination_name, lines)
        return

    if action == "write" and len(parts) == 4:
        content = resolve(parts[3], runtime)
        _write_value(file_obj, content)
        return

    if action == "writelines" and len(parts) == 4:
        values = resolve(parts[3], runtime)
        if not isinstance(values, (list, tuple)):
            raise TypeError("writelines requires a list or tuple.")
        for content in values:
            _write_value(file_obj, content)
        return

    if action == "seek" and len(parts) in (4, 5):
        offset = _integer(resolve(parts[3], runtime), "Seek offset")
        whence = 0
        if len(parts) == 5:
            whence = _integer(resolve(parts[4], runtime), "Seek whence")
            if whence not in (0, 1, 2):
                raise ValueError("Seek whence must be 0, 1, or 2.")
        try:
            file_obj.seek(offset, whence)
        except (OSError, io.UnsupportedOperation) as error:
            raise ValueError(f"Cannot seek in this file: {error}") from error
        return

    if action == "tell" and len(parts) == 4:
        destination_name = parts[3]
        destination = runtime.require_var(destination_name)
        if destination["type"] != "int":
            raise TypeError("File position destination must be an integer.")
        runtime.assign_var(destination_name, file_obj.tell())
        return

    if action == "flush" and len(parts) == 3:
        file_obj.flush()
        return

    if action == "truncate" and len(parts) in (3, 4):
        size = (
            _integer(resolve(parts[3], runtime), "Truncate size")
            if len(parts) == 4 else None
        )
        if size is not None and size < 0:
            raise ValueError("Truncate size must not be negative.")
        file_obj.truncate(size)
        return

    raise SyntaxError(
        "Usage: file read <file> [count] <destination> | "
        "file write <file> <value> | "
        "file readline <file> <destination> | "
        "file readlines <file> <list_destination> | "
        "file writelines <file> <list> | "
        "file seek <file> <offset> [whence] | "
        "file tell <file> <int_destination> | "
        "file flush <file> | "
        "file truncate <file> [size]"
    )
