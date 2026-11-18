# YubaLANG 1.4 roadmap

This checklist records the accepted 1.4 work and the candidates that remain
deferred. Keep YubaLANG runtime responsibilities separate from YubaPKG package
resolution and installation. The full roadmap is in
[docs/roadmap/1.4.md](docs/roadmap/1.4.md).

## Shipped

- [x] Expression function calls: simple/qualified names, positional and named
  arguments, nested calls, with receiver/index and unpacking limits documented.
- [x] Record field defaults and named construction, including per-construction
  defaults and construction diagnostics.
- [x] Forward record field types, resolved against records declared later in
  the same source file.
- [x] Static analysis for forward records, record construction, union values,
  optional conditions, expression-call results, and multi-token annotations.
- [x] Deterministic resource protocol with reverse-order cleanup, every-resource
  attempts, first-error reporting, and automatic file tracking.
- [x] `YubaLANG debug` frontend with breakpoints, stepping, stack, variables,
  source listing, and quit.
- [x] Opt-in `YubaLANG test --coverage` with a side channel and additive JSON.
- [x] Cached LSP workspace index with safe top-level references and rename.
- [x] Editor setup documentation and automated LSP protocol/index tests.
- [x] Manifest compatibility for runtime 1.2, 1.3, and 1.4; new projects target
  1.4; compatibility matrix and package tests updated.
- [x] Versioned reference, master reference, migration notes, release notes,
  installation and tool guides updated.
- [ ] Manual desktop-editor LSP smoke test (automated stdio tests pass).

## Deferred with documented rationale

- [ ] Record methods, inheritance, and code-running constructors: require a
  receiver, mutation, visibility, equality, and compatibility proposal.
- [ ] Concurrency and asynchronous I/O: require cancellation, error
  propagation, scheduling, and shared-state semantics.
- [ ] Build/bundle command: requires concrete generated-code and native
  dependency use cases plus reproducibility and platform requirements.
- [ ] Bytecode or compiler targets: require representative benchmarks or
  distribution needs.
- [ ] Class-based inheritance, non-C plugins, and broader native FFI: require
  concrete use cases, ABI/ownership rules, platform support, and process-safety
  limits.
- [ ] Registry resolution and installation: remain a YubaPKG responsibility.

## Completion criteria

A 1.4 change is complete only when its behavior is specified, tested,
documented in the versioned and master references, covered by migration
guidance when compatibility is affected, and validated on the platforms
required by its scope.
