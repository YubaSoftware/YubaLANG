"""Stable diagnostic identifiers, severities, and explanations.

Diagnostic codes are part of the YubaLANG tooling contract. A code never
changes within a language minor version: new diagnostics receive new codes and
retired codes stay documented so editor and CI configuration keeps working.
"""

from dataclasses import dataclass
import re

from .runtime import LanguageException


@dataclass(frozen=True)
class DiagnosticInfo:
    code: str
    severity: str
    title: str
    explanation: str
    example: str


_STATIC = (
    DiagnosticInfo(
        "invalid-quoting",
        "error",
        "Invalid command quoting",
        "A source line has an unterminated quoted string or a quoting pattern "
        "the command tokenizer cannot split.",
        'text output "unterminated',
    ),
    DiagnosticInfo(
        "invalid-syntax",
        "error",
        "Invalid command syntax",
        "A command or block does not match its documented grammar or arity.",
        "if",
    ),
    DiagnosticInfo(
        "unknown-command",
        "error",
        "Unknown command",
        "The first word of a source line is not a supported command.",
        "tex output 'hello'",
    ),
    DiagnosticInfo(
        "unknown-type",
        "error",
        "Unknown type",
        "A type annotation names a type that is not built in or declared in "
        "the same source file.",
        "define var count: integer = 1",
    ),
    DiagnosticInfo(
        "unclosed-block",
        "error",
        "Unclosed block",
        "A block was opened with if, loop, func, or try but its matching end "
        "command is missing.",
        "if true\n    text output 'open'\n",
    ),
    DiagnosticInfo(
        "import-resolution",
        "error",
        "Import cannot be resolved",
        "An import does not name a bundled std module, a project manifest "
        "entry, or a source file relative to the importing file.",
        "import missing_module",
    ),
    DiagnosticInfo(
        "type-mismatch",
        "error",
        "Statically evident type mismatch",
        "The checker proved that a value's type is incompatible with the "
        "declared destination, parameter, field, or return type. Runtime "
        "checks remain authoritative for values the checker cannot infer.",
        'define var label: string = ""\n'
        "define var values: list = [1, 2]\n"
        "list len values label",
    ),
    DiagnosticInfo(
        "unreachable-code",
        "warning",
        "Unreachable statement",
        "A statement follows return, break, continue, or throw in the same "
        "block and can never execute.",
        'func define stop -> int\n    return 0\n    text output "never"\nendfunc',
    ),
    DiagnosticInfo(
        "shadowed-variable",
        "warning",
        "Shadowed variable",
        "A block declares a variable with the same name as an enclosing "
        "variable. The inner declaration hides the outer one for the rest of "
        "the block.",
        'define var count: int = 1\nif true\n    define var count: int = 2\nendif',
    ),
    DiagnosticInfo(
        "invalid-annotation",
        "warning",
        "Invalid type annotation",
        "Strict mode reports parameter or return annotations that are not "
        "valid known types so they cannot silently fall back to dynamic "
        "checking.",
        "func define parse value:mystery\nendfunc",
    ),
    DiagnosticInfo(
        "constant-reassignment",
        "error",
        "Constant reassignment",
        "A variable declared with define const, or an immutable record field, "
        "cannot be reassigned or converted.",
        "define const limit: int = 1\nset limit = 2",
    ),
    DiagnosticInfo(
        "non-exhaustive-match",
        "error",
        "Non-exhaustive match",
        "A match over an enum or union omits cases and has no else branch. "
        "The diagnostic is reserved for the match/case syntax.",
        "match value\ncase Missing\nendmatch",
    ),
    DiagnosticInfo(
        "invalid-pattern",
        "error",
        "Invalid pattern",
        "A match case uses a pattern that does not match the shape or type of "
        "the matched value. The diagnostic is reserved for the match/case "
        "syntax.",
        "match pair\ncase (only_one)\nendmatch",
    ),
)

_RUNTIME = (
    DiagnosticInfo(
        "undefined-variable",
        "error",
        "Undefined variable",
        "A value expression, destination, or assignment names a variable that "
        "is not declared in the current or enclosing scopes.",
        "text output missing",
    ),
    DiagnosticInfo(
        "undefined-function",
        "error",
        "Undefined function",
        "A call names a function that is not defined in the current module or "
        "an imported namespace.",
        "func call missing",
    ),
    DiagnosticInfo(
        "private-function",
        "error",
        "Private function called from another module",
        "Private functions are visible only inside the module that defines "
        "them.",
        "func call library.helper",
    ),
    DiagnosticInfo(
        "unknown-command",
        "error",
        "Unknown command",
        "The first word of a source line is not a supported command.",
        "tex output 'hello'",
    ),
    DiagnosticInfo(
        "unknown-type",
        "error",
        "Unknown type",
        "A conversion, annotation, or record declaration names a type that is "
        "not built in and not declared by the program.",
        "convert count to integer",
    ),
    DiagnosticInfo(
        "assignment-type",
        "error",
        "Assignment type mismatch",
        "A runtime assignment would store a value whose type does not match "
        "the variable's declared type.",
        'define var count: int = 1\nset count = "one"',
    ),
    DiagnosticInfo(
        "condition-type",
        "error",
        "Non-boolean condition",
        "if, elseif, loop while, assert, and compare require boolean values.",
        'if "yes"\nendif',
    ),
    DiagnosticInfo(
        "function-arguments",
        "error",
        "Function argument mismatch",
        "A call supplies the wrong number, names an unknown parameter, repeats "
        "a named argument, or places positional arguments after named ones.",
        "func call add 1 missing=2",
    ),
    DiagnosticInfo(
        "function-return",
        "error",
        "Function return mismatch",
        "A function returns a value that does not match its declared return "
        "type, or a caller requests a value from a function that did not "
        "return one.",
        "func define fail -> int\nendfunc",
    ),
    DiagnosticInfo(
        "collection-type",
        "error",
        "Collection type mismatch",
        "A collection command expected a list, dict, set, tuple, iterator, or "
        "file variable and received another type.",
        "list len count size",
    ),
    DiagnosticInfo(
        "index-error",
        "error",
        "Index out of range",
        "A list, tuple, string, or slice index is outside its valid range.",
        "list get numbers 10 result",
    ),
    DiagnosticInfo(
        "key-error",
        "error",
        "Missing dictionary key",
        "A dictionary lookup used a key that is not present and no default was "
        "provided.",
        'dict get scores "absent" result',
    ),
    DiagnosticInfo(
        "attribute-error",
        "error",
        "Missing attribute",
        "An attribute lookup or mutation names a record field or dictionary key "
        "that does not exist.",
        "getattr point missing result",
    ),
    DiagnosticInfo(
        "division-by-zero",
        "error",
        "Division by zero",
        "An arithmetic division or modulo operation used zero as its divisor.",
        "arith div 10 0 result",
    ),
    DiagnosticInfo(
        "arithmetic-error",
        "error",
        "Arithmetic type error",
        "An arithmetic or numeric built-in received a value outside its "
        "supported numeric domain.",
        'arith add 1 "two" result',
    ),
    DiagnosticInfo(
        "conversion-error",
        "error",
        "Conversion failed",
        "convert could not produce the requested type from the current value.",
        'define var n: string = "x"\nconvert n to int',
    ),
    DiagnosticInfo(
        "record-error",
        "error",
        "Record error",
        "A record declaration, construction, or field access is invalid, for "
        "example a duplicate field, unknown record, or unknown field name.",
        "record create Missing value 1",
    ),
    DiagnosticInfo(
        "assertion-failed",
        "error",
        "Assertion failed",
        "An assert condition evaluated to false.",
        "assert false 'stopped'",
    ),
    DiagnosticInfo(
        "uncaught-exception",
        "error",
        "Uncaught language exception",
        "A thrown value reached the top level without a matching catch block.",
        'throw "broken"',
    ),
    DiagnosticInfo(
        "import-cycle",
        "error",
        "Import cycle",
        "Modules import each other in a cycle that cannot complete.",
        "import a\n# a.yl imports b, b.yl imports a",
    ),
    DiagnosticInfo(
        "import-error",
        "error",
        "Import failed",
        "A module name is invalid, a namespace is rebound, or a module source "
        "cannot be read or parsed.",
        "import missing_module",
    ),
    DiagnosticInfo(
        "syntax-error",
        "error",
        "Syntax error at runtime",
        "A command or expression failed syntax validation while executing.",
        "func call",
    ),
    DiagnosticInfo(
        "type-error",
        "error",
        "Type error at runtime",
        "A runtime operation received a value of an unsupported type. The "
        "message identifies the operation and the accepted type.",
        'len 5 size',
    ),
    DiagnosticInfo(
        "value-error",
        "error",
        "Invalid value at runtime",
        "A value is syntactically valid but outside the accepted domain, such "
        "as an empty argument list or an exhausted iterator.",
        "next iterator result",
    ),
    DiagnosticInfo(
        "io-error",
        "error",
        "Input/output error",
        "A file, path, or standard stream operation failed.",
        'open "missing.txt" "r" handle',
    ),
    DiagnosticInfo(
        "resource-error",
        "error",
        "Resource cleanup error",
        "A tracked resource could not be closed during deterministic cleanup.",
        "close handle",
    ),
    DiagnosticInfo(
        "limit-error",
        "error",
        "Limit exceeded",
        "A configured runtime limit, such as recursion depth or a request "
        "bound, was exceeded.",
        "func call recurse",
    ),
    DiagnosticInfo(
        "stack-overflow",
        "error",
        "Recursion limit exceeded",
        "The maximum function call depth was reached. Check that recursion "
        "eventually stops.",
        "func define recurse\n    func call recurse\nendfunc\nfunc call recurse",
    ),
    DiagnosticInfo(
        "memory-limit",
        "error",
        "Memory exhausted",
        "The host could not allocate memory for a collection or intermediate "
        "value. Reduce the size of the data the program builds.",
        "define var values: list = [1] * 1000000000",
    ),
    DiagnosticInfo(
        "runtime-error",
        "error",
        "Runtime error",
        "An error without a more specific stable code occurred. The message "
        "remains the authoritative description.",
        "text output missing",
    ),
    DiagnosticInfo(
        "regex-error",
        "error",
        "Regular expression error",
        "A regular expression could not be compiled or a pattern exceeded a "
        "documented backtracking or match limit.",
        'func call regex.compile "["',
    ),
    DiagnosticInfo(
        "regex-backtracking",
        "error",
        "Unsafe regular expression",
        "A regular expression contains nested quantifiers that may backtrack "
        "excessively. Rewrite the pattern or pass allow_unsafe=true after "
        "reviewing the input bounds.",
        'func call regex.compile "(a+)+$"',
    ),
    DiagnosticInfo(
        "archive-error",
        "error",
        "Archive error",
        "A ZIP archive could not be read or written, or a member name or size "
        "violated the archive safety rules.",
        'func call archive.list "missing.zip"',
    ),
    DiagnosticInfo(
        "sqlite-error",
        "error",
        "SQLite error",
        "A SQLite connection, statement, transaction, or result limit failed.",
        'func call sqlite.query database "SELECT * FROM missing"',
    ),
    DiagnosticInfo(
        "http-error",
        "error",
        "HTTP client error",
        "An HTTP request failed transport validation, timed out, or exceeded "
        "the configured response limit.",
        'func call http.request "not-a-url"',
    ),
    DiagnosticInfo(
        "process-error",
        "error",
        "Process error",
        "A subprocess could not be launched, timed out, or exceeded the "
        "configured output limit.",
        'func call process.run []',
    ),
    DiagnosticInfo(
        "timeout-error",
        "error",
        "Operation timed out",
        "A network, process, or other blocking operation exceeded its "
        "configured timeout.",
        'func call http.request "https://example.invalid"',
    ),
)

DIAGNOSTICS: dict[str, DiagnosticInfo] = {
    info.code: info for info in (*_STATIC, *_RUNTIME)
}

STATIC_CODES = frozenset(info.code for info in _STATIC)


def diagnostic_info(code: str) -> DiagnosticInfo | None:
    return DIAGNOSTICS.get(code)


def explain_diagnostic(code: str) -> str | None:
    """Return a short human explanation for a diagnostic code."""
    info = diagnostic_info(code)
    if info is None:
        return None
    lines = [
        f"{info.code} ({info.severity})",
        "",
        info.title,
        "",
        info.explanation,
        "",
        "Example:",
    ]
    lines.extend(f"    {line}" for line in info.example.splitlines())
    return "\n".join(lines)


def list_diagnostics() -> list[DiagnosticInfo]:
    return sorted(DIAGNOSTICS.values(), key=lambda info: info.code)


_UNDEFINED_FUNCTION = re.compile(r"^Function '[^']+' is not defined\.")
_UNDEFINED_VARIABLE = re.compile(r"^Variable '[^']+' is not defined\.")
_PRIVATE = re.compile(r"^Function '[^']+' is private to its module\.")
_UNKNOWN_COMMAND = re.compile(r"^Unknown command: [A-Za-z_]\w*")
_UNKNOWN_TYPE = re.compile(r"^Unknown type: [A-Za-z_]\w*")
_LANGUAGE_EXCEPTION = re.compile(r"^Uncaught language exception:")
_FUNCTION_ARGUMENT = re.compile(
    r"^(?:"
    r"Function '[^']+' (?:has no parameter named|got multiple values for|"
    r"expects|does not accept|requires)|"
    r"Named argument '[^']+' was supplied more than once\.|"
    r"Positional arguments must come before named arguments\.|"
    r"Missing value for named argument '[^']+'\.|"
    r"A function call must|"
    r"Usage: func call"
    r")"
)
_FUNCTION_RETURN = re.compile(
    r"^(?:Function '[^']+' did not return a value\.|A function return type)"
)
_ASSIGNMENT = re.compile(
    r"^(?:Cannot assign a .* value to variable|"
    r"Mutation would violate collection type|"
    r"Cannot convert '[^']+' to )"
)
_CONSTANT = re.compile(
    r"^(?:Cannot reassign constant|Cannot redeclare constant|"
    r"Field '[^']+' of record '[^']+' is immutable\.)"
)
_CONDITION = re.compile(
    r"^(?:Condition must evaluate to a boolean\.|"
    r"Assertion condition must be a boolean\.|"
    r"Comparison expression must evaluate to a boolean\.|"
    r"loop for count must evaluate to an integer\.)"
)
_COLLECTION = re.compile(
    r"^(?:Variable '[^']+' is not of type '|"
    r"Variable '[^']+' must be a defined collection\.|"
    r"Variable '[^']+' is not an iterator\.|"
    r"Variable '[^']+' is not a file\.|"
    r"Variable '[^']+' is closed\.)|"
    r"(?:reversed\(\)|sorted\(\)|zip\(\)|slice\(\))"
)
_ARITHMETIC = re.compile(
    r"^(?:Arithmetic requires numbers\.|"
    r"Operation '[^']+' does not support|"
    r"(?:bin|hex|oct|chr|ord)\(\))"
)
_RECORD = re.compile(
    r"^(?:Unknown record type:|Record field|Record '[^']+'|"
    r"Record creation|record )"
)
_MATCH = re.compile(
    r"^(?:match is not exhaustive|Enum .* pattern|"
    r"Case patterns|Invalid case pattern|A case pattern|"
    r"A match block|Missing endmatch)"
)
_IMPORT = re.compile(
    r"^(?:Module '[^']+' was not found|Cannot read module|"
    r"Import namespace|Namespace '[^']+' is already bound|"
    r"Invalid module (?:name|namespace)|Import cycle detected)"
)
_IO = re.compile(
    r"^(?:File |open\(\)|Cannot open|Cannot read|Cannot write|"
    r"Text files require|Binary files require)"
)
_LIMIT = re.compile(
    r"^(?:Maximum .* exceeded|.* exceeds the maximum|.* limit)"
)


def code_for_runtime(error: BaseException) -> str:
    """Return the stable code for a runtime diagnostic."""
    explicit_code = getattr(error, "code", None)
    if isinstance(explicit_code, str) and explicit_code:
        return explicit_code
    message = str(error)
    if isinstance(error, RecursionError):
        return "stack-overflow"
    if isinstance(error, MemoryError):
        return "memory-limit"
    if isinstance(error, LanguageException):
        return "uncaught-exception"
    if isinstance(error, AssertionError):
        return "assertion-failed"
    if isinstance(error, ZeroDivisionError):
        return "division-by-zero"
    if isinstance(error, IndexError):
        return "index-error"
    if isinstance(error, KeyError):
        return "key-error"
    if isinstance(error, AttributeError):
        return "attribute-error"
    if isinstance(error, (OSError, EOFError)):
        return "io-error"
    if isinstance(error, SyntaxError):
        return "syntax-error"
    if _UNDEFINED_FUNCTION.match(message):
        return "undefined-function"
    if _UNDEFINED_VARIABLE.match(message):
        return "undefined-variable"
    if _PRIVATE.match(message):
        return "private-function"
    if _UNKNOWN_COMMAND.match(message):
        return "unknown-command"
    if _UNKNOWN_TYPE.match(message):
        return "unknown-type"
    if _FUNCTION_ARGUMENT.match(message):
        return "function-arguments"
    if _FUNCTION_RETURN.match(message):
        return "function-return"
    if _CONSTANT.match(message):
        return "constant-reassignment"
    if _ASSIGNMENT.match(message):
        return "assignment-type"
    if _CONDITION.match(message):
        return "condition-type"
    if _COLLECTION.match(message):
        return "collection-type"
    if _ARITHMETIC.match(message):
        return "arithmetic-error"
    if _MATCH.match(message):
        return (
            "non-exhaustive-match"
            if "match is not exhaustive" in message
            else "invalid-pattern"
        )
    if _RECORD.match(message):
        return "record-error"
    if _IMPORT.match(message):
        return "import-cycle" if "Import cycle" in message else "import-error"
    if _IO.match(message):
        return "io-error"
    if _LIMIT.match(message):
        return "limit-error"
    if isinstance(error, TypeError):
        return "type-error"
    if isinstance(error, ValueError):
        return "value-error"
    return "runtime-error"
