# Diagnostics reference

Every parser, checker, and runtime message in YubaLANG carries a stable
diagnostic code. The code is the final bracketed token on the human-readable
line and the `code` field in LSP and `check --json` output. Codes are stable
within the 1.x line: a code that is published keeps its meaning, and a retired
code stays documented.

Use `YubaLANG explain <code>` for a short description and example. The same
information is available to editor clients from the LSP `code` field.

```text
py YubaLANG.py explain type-mismatch
```

## Severity

| Severity | Meaning | Affects exit status |
| --- | --- | --- |
| `error` | The program or source is invalid. | Yes, always. |
| `warning` | Suspicious but valid code. | Only with `--deny-warnings` or `--strict`. |

Runtime diagnostics are always errors. The checker emits both severities; the
LSP uses severity `1` for errors and `2` for warnings.

## Parser and checker codes

| Code | Severity | Meaning |
| --- | --- | --- |
| `invalid-quoting` | error | Unterminated or unsupported command quoting. |
| `invalid-syntax` | error | A command or block does not match its grammar or arity. |
| `unknown-command` | error | The first word is not a supported command. |
| `unknown-type` | error | A type annotation names an unknown type. |
| `unclosed-block` | error | A block is missing its end command. |
| `import-resolution` | error | An import cannot be resolved for the current project. |
| `type-mismatch` | error | A statically evident type mismatch. |
| `unreachable-code` | warning | A statement follows an unconditional exit in the same block. |
| `shadowed-variable` | warning | A block declaration hides an enclosing variable. |
| `invalid-annotation` | warning | Strict mode found an unknown or unparseable annotation. |
| `non-exhaustive-match` | error | Reserved for match/case exhaustiveness. |
| `invalid-pattern` | error | Reserved for invalid match/case patterns. |

`non-exhaustive-match` and `invalid-pattern` are registered now so editor and
CI configuration can name them before the corresponding milestone 1 syntax
lands. The checker does not emit them yet.

## Runtime codes

| Code | Severity | Meaning |
| --- | --- | --- |
| `undefined-variable` | error | A variable is not declared in scope. |
| `undefined-function` | error | A called function is not defined. |
| `private-function` | error | A private function was called from another module. |
| `unknown-command` | error | The executed line starts with an unsupported command. |
| `unknown-type` | error | A conversion or declaration names an unknown type. |
| `assignment-type` | error | An assignment violates a declared or collection type. |
| `condition-type` | error | `if`, `elseif`, `loop while`, `assert`, or `compare` received a non-boolean. |
| `function-arguments` | error | A call has a wrong arity, duplicate, unknown, or misplaced argument. |
| `function-return` | error | A return value mismatches its annotation or is missing. |
| `collection-type` | error | A collection command received a non-collection or wrong collection type. |
| `index-error` | error | An index is outside the valid range. |
| `key-error` | error | A dictionary key is missing and no default was given. |
| `attribute-error` | error | A record field or dictionary attribute does not exist. |
| `division-by-zero` | error | Division or modulo by zero. |
| `arithmetic-error` | error | Arithmetic received an unsupported value or domain. |
| `conversion-error` | error | `convert` could not produce the requested type. |
| `record-error` | error | A record declaration, construction, or field is invalid. |
| `assertion-failed` | error | An `assert` condition was false. |
| `uncaught-exception` | error | A thrown value reached the top level. |
| `import-cycle` | error | Modules import each other in a cycle. |
| `import-error` | error | A module is invalid, unreadable, or has a namespace conflict. |
| `syntax-error` | error | A command or expression failed syntax validation at runtime. |
| `type-error` | error | A runtime operation received an unsupported type. |
| `value-error` | error | A value is outside an operation's accepted domain. |
| `io-error` | error | A file, path, or stream operation failed. |
| `resource-error` | error | A tracked resource failed to close during cleanup. |
| `limit-error` | error | A configured or runtime limit was exceeded. |
| `stack-overflow` | error | The maximum function call depth was reached. |
| `memory-limit` | error | The host could not allocate memory. |
| `runtime-error` | error | A fallback for runtime failures without a more specific code. |

Runtime messages remain the authoritative detail. The code identifies the
diagnostic category so editors, CI, and suppress/filter rules do not depend on
message wording.

## Check modes

`YubaLANG check` reports errors and warnings. Only errors fail by default.

- `--deny-warnings` fails when a warning is reported.
- `--strict` enables strict-only checks such as `invalid-annotation` and also
  fails when warnings are reported.
- `--json` prints the versioned JSON object described in the
  [1.4 language reference](../1.4-docs.md#json-check-output).

Neither `--deny-warnings` nor `--strict` changes how a program executes. They
affect only the static check command.

## Stability

- Codes are lowercase, hyphenated, and never renamed within 1.x.
- A new check receives a new code.
- Severity is part of the code's contract. A warning does not become an error
  in default mode.
- The JSON `schemaVersion` is `1` for 1.4. New fields may be added; existing
  fields keep their meaning.
