from lang.interpreter import execute_lines
from lang.runtime import Runtime

src = [
    'enum define Result ok(value: int) error(message: string)',
    'type define Number = int | float',
    'define const limit: int = 10',
    'define var total: Number = 0',
    'set total += 5',
    'enum create Result.ok result 42',
    'match result',
    '    case Result.ok(value)',
    '        text output f"ok {value}"',
    '    case Result.error(message)',
    '        text output f"error {message}"',
    '    else',
    '        text output "never"',
    'endmatch',
    'match (1, 2)',
    '    case (a, b)',
    '        text output a + b',
    'endmatch',
    'match "x"',
    '    case "y"',
    '        text output "no"',
    '    else',
    '        text output "fallback"',
    'endmatch',
    'define var xs: list[int] = [1, 2, 3]',
    'text output [*xs, 4]',
    'text output {**{"a": 1}, "b": 2}',
    'match result',
    '    case Result.ok(value)',
    '        text output value',
    'endmatch',
]
runtime = Runtime()
execute_lines(src, runtime, "manual.yl")
print("limit", runtime.get_var("limit"))
try:
    execute_lines(["set limit = 3"], runtime, "manual.yl")
except SystemExit as e:
    print("const blocked", e.code)
