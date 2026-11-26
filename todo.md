# YubaLANG 1.4 roadmap

Status: **in progress.** This checklist is the working 1.4 plan and the canonical
list of 1.4 work. Checked items are delivered in the repository today. Unchecked
items are scheduled for 1.4 and may still change as their proposals land. Keep
YubaLANG runtime responsibilities separate from YubaPKG package resolution and
installation.

The narrative roadmap, sequencing, and exit criteria are in
[docs/roadmap/1.4.md](docs/roadmap/1.4.md). The 1.4 release notes describe only
the delivered subset; the long-term candidates that remain outside 1.4 and 1.5
are in the [feature backlog](docs/roadmap/features.md).

## Delivered so far

- [x] Expression function calls: simple and qualified names, positional and named
  arguments, nested calls, with receiver/index and unpacking limits documented.
- [x] Record field defaults and named construction, including per-construction
  defaults and construction diagnostics.
- [x] Forward record field types, resolved against records declared later in the
  same source file.
- [x] Static analysis for forward records, record construction, union values,
  optional conditions, expression-call results, and multi-token annotations.
- [x] Deterministic resource protocol with reverse-order cleanup, every-resource
  attempts, first-error reporting, and automatic file tracking.
- [x] Interactive `YubaLANG debug` frontend with breakpoints, stepping, stack,
  variables, source listing, and quit.
- [x] Opt-in `YubaLANG test --coverage` with a side channel and additive JSON.
- [x] Cached LSP workspace index with safe top-level references and rename.
- [x] Editor setup documentation and automated LSP protocol/index tests.
- [x] Manifest compatibility for runtime 1.2, 1.3, and 1.4; new projects target
  1.4; compatibility matrix and package tests updated.
- [x] Initial versioned reference, master reference, migration notes, release
  notes, installation guide, and tool guides updated for delivered work.
- [x] Milestone 1 language ergonomics: expression access, indexing, slicing, and
  methods; `loop for` iteration and destructuring; enums, `match`/`case`, type
  aliases, lambdas, `define const`, immutable record fields, compound
  assignment, optional chaining, null-coalescing, and `*`/`**` unpacking.
  Generics, record methods, generators, and cleanup/defer remain deferred with
  documented rationale.

## Milestone 1 - Language ergonomics

- [x] Support attribute access, index access, and method calls in expressions,
  including chained receivers, with source-located diagnostics for unsupported
  receivers.
- [x] Add `loop for <name> in <iterable>` iteration, including tuple
  destructuring and `break`/`continue` behavior, and keep the count and `while`
  forms unchanged.
- [x] Add destructuring declarations and assignments for tuples and lists,
  including mismatched-arity and type diagnostics.
- [x] Add `match`/`case` with literal, tuple, type, and enum patterns plus an
  optional `else`, and diagnose non-exhaustive matches over enums and unions.
- [x] Add enums and sum types with payload variants, construction, equality,
  display, and runtime type checks.
- [x] Add type aliases usable in annotations, records, and function signatures.
  Generic parameters and generic aliases remain unsupported in 1.4.
- [ ] Add user-defined generic functions and records with explicit type
  parameters, inference at call sites, and documented variance rules. Deferred:
  requires a variance and inference proposal.
- [x] Add lambdas/anonymous functions usable as `map`/`filter`/`sorted`
  callbacks and as values of function types.
- [x] Add `define const` and immutable record fields, with reassignment
  diagnostics in both the checker and the runtime.
- [x] Add compound assignment operators (`set x += y` and the other arithmetic
  and bitwise forms) with the same type rules as `set`.
- [x] Add optional chaining and null-coalescing (`?.`, `?:`) with option-type
  narrowing.
- [x] Add argument and literal unpacking (`*`/`**`) to expression calls and
  collection literals.
- [ ] Write and accept a proposal for record methods and constructors covering
  receiver semantics, mutation, visibility, equality, and compatibility.
  Deferred: needs a separate receiver/mutation proposal.
- [ ] Implement record methods and code-running constructors per the accepted
  proposal. Deferred with the proposal.
- [ ] Add generators/`yield` and lazy iterators, and define how they interact
  with the resource protocol and early loop exit. Deferred: cleanup and early
  exit semantics need a proposal.
- [ ] Add a language-level cleanup/defer form for resource-bearing values only
  if the general runtime resource protocol proves insufficient. Deferred: the
  runtime protocol currently covers tracked resources.

## Milestone 2 - Types and diagnostics

- [x] Narrow optionals and unions in `if`, `elseif`, and early-return branches
  so checked code does not require repeated conversions. `match` narrowing
  waits for the milestone 1 `match`/`case` syntax.
- [x] Infer comprehension filters, collection/index/`getattr` results, and
  simple alias chains in static analysis. Pattern, lambda, and method
  inference wait for the milestone 1 pattern, lambda, and method syntax.
- [x] Assign stable diagnostic codes and severities to every checker, parser,
  and runtime diagnostic.
- [x] Add `--strict` and `--deny-warnings` modes that keep default execution
  behavior unchanged.
- [x] Add `YubaLANG check --json` with stable fields for editors and CI.
- [x] Add `YubaLANG explain <code>` with a short explanation and example.
- [x] Audit high-value static-inference gaps and document the remaining dynamic
  cases; close the gaps that have crisp rules.
- [x] Add negative fixtures for every new diagnostic, including invalid
  annotation, arity, and narrowing cases. Exhaustiveness fixtures wait for
  `match`/enum syntax.

## Milestone 3 - Runtime and standard library

- [ ] Add `std.regex` with compiled patterns, matching, replacement, and
  documented backtracking limits.
- [ ] Add `std.glob` and path-expansion helpers built on `std.fs`.
- [ ] Add `std.tempfile` with deterministic cleanup through the resource
  protocol.
- [ ] Add `std.archive` for zip read/write with path-traversal protection.
- [ ] Add `std.sqlite` with parameter binding, transactions, and resource
  cleanup.
- [ ] Add `std.uuid`, `std.decimal`, `std.statistics`, `std.logging`,
  `std.terminal`, and `std.env` (environment variables, arguments, and
  working directory) modules.
- [ ] Extend file I/O with `seek`, `tell`, `readline`, line iteration, buffered
  reads/writes, binary standard streams, and atomic file replacement.
- [ ] Add typed error values: catch by error kind, expose stack traces as data,
  and support error causes without exposing Python tracebacks.
- [ ] Make recursion depth, collection size, HTTP bounds, and process limits
  configurable, with documented defaults.
- [ ] Extend the resource protocol to iterators and native handles, and document
  double-close and failure behavior.
- [ ] Document ordering and hashing guarantees for dictionaries, sets, and
  iteration so programs can rely on deterministic behavior.

## Milestone 4 - Documentation and developer experience

### Documentation

- [ ] Add `###` doc comments with parameter, return, and error sections, and
  surface them in hover.
- [ ] Add `YubaLANG doc` generating Markdown and HTML API documentation for a
  file, directory, or project.
- [ ] Add a diagnostic reference page and a syntax/built-in cheat sheet.
- [ ] Keep the versioned reference, master reference, migration notes, release
  notes, installation guide, and examples current as each item lands.

### REPL and formatter

- [ ] Add REPL history, completion, `:type`, `:doc`, and `:load`/`:save`.
- [ ] Add a formatter configuration file for indentation, line width, and
  comment handling.
- [ ] Format doc comments and define stable comment-attachment rules.
- [ ] Add formatter idempotence and fuzz tests over the example catalog.

### Language server

- [ ] Add `textDocument/formatting` and `textDocument/rangeFormatting`.
- [ ] Add semantic tokens, folding ranges, document highlights, and inlay hints.
- [ ] Add call hierarchy and completion snippets.
- [ ] Add doc-comment hover and signature-help documentation.
- [ ] Add code actions and refactors: add import, extract variable/function, and
  implement record.
- [ ] Add multi-root workspace support and workspace-wide record-field rename.

### Debugger

- [ ] Add conditional breakpoints and watch expressions.
- [ ] Add expression evaluation in a stopped frame.
- [ ] Add exception breakpoints and a machine-readable event stream.
- [ ] Allow the debugger to attach to test runs and the REPL.

### Test runner

- [ ] Add an in-language `test`/`expect` block format alongside output-based
  tests.
- [ ] Add name filtering, `--jobs` parallel runs, and per-test timeouts.
- [ ] Add setup/teardown hooks scoped to a file and to a directory.
- [ ] Add JUnit XML and TAP output.
- [ ] Add `--min-coverage` thresholds and branch coverage, keeping the default
  report shape unchanged.

### Command line

- [ ] Add `YubaLANG init [directory]` for a minimal runnable project.
- [ ] Add `YubaLANG version --json`.
- [ ] Add `--color`/`NO_COLOR` handling for diagnostics and reports.

## Milestone 5 - Projects and distribution

- [ ] Record a manifest `features` list so projects can declare required
  capabilities.
- [ ] Validate `yubalang` version ranges such as `>=1.4 <2.0` and report clear
  incompatibility errors.
- [ ] Add offline `YubaLANG package verify` for lockfile and artifact hashes.
- [ ] Generate project API documentation from doc comments.
- [ ] Update the YubaLANG/YubaPKG compatibility matrix and package tests for the
  1.4 manifest changes.
- [ ] Coordinate any lockfile format change with YubaPKG before implementation.

## Milestone 6 - Quality and release

- [ ] Add a conformance suite covering every documented grammar rule, built-in,
  type rule, and diagnostic, including invalid programs.
- [ ] Add runnable examples and documentation links for every new feature.
- [ ] Run CI on Windows, Linux, and macOS with Python 3.10 through 3.13.
- [ ] Add benchmark regression thresholds to CI using representative workloads.
- [ ] Add parser, formatter, and evaluator fuzz tests with minimized failure
  cases.
- [ ] Complete a manual desktop-editor LSP smoke test and record the tested
  client configuration.
- [ ] Finalize 1.4 release notes, the 1.3-to-1.4 migration guide, and the
  compatibility matrix only after the release gates pass.
- [ ] Confirm the documentation index, README, and roadmap links match the
  shipped release.

## Deferred with documented rationale

- Concurrency and asynchronous I/O: scheduled for 1.5, where cancellation, error
  propagation, scheduling, and shared-state rules can be tested together.
- Interpreter speed work, bytecode/VM targets, and profiling: scheduled for 1.5,
  gated on measured benchmarks.
- Broader native FFI types and non-C extension mechanisms: FFI v2 is planned for
  1.5; non-C extensions remain gated on a concrete integration need.
- Build/bundle commands: moved to 1.6 after representative generated-code and
  native dependency use cases are collected.
- Class-based inheritance and object orientation: require a separate proposal
  and compatibility plan.
- Registry resolution and installation: remain a YubaPKG responsibility.

## Completion criteria

A 1.4 change is complete only when its behavior is specified, tested,
documented in the versioned and master references, covered by migration
guidance when compatibility is affected, and validated on the platforms
required by its scope.

See [docs/roadmap/1.4.md](docs/roadmap/1.4.md) for sequencing and
[docs/roadmap/1.5.md](docs/roadmap/1.5.md) for the next release.
