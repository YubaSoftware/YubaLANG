# YubaLANG feature backlog

This backlog tracks capability areas beyond the current 1.4 baseline. It is a
planning aid, not a promise or a claim that every programming language needs
every item. The 1.4 release candidates are collected in the
[1.4 roadmap](1.4.md). Select work based on concrete user needs, clear
semantics, compatibility, and maintainability.

## Current baseline

The following capabilities are already present and should remain covered by
regression and conformance tests:

- [x] Command-oriented programs, blocks, expressions, typed variables, typed
  functions, closures, records with defaults and named construction, and
  structured exceptions.
- [x] Static `check` diagnostics alongside runtime type and value checks.
- [x] Local modules, path/Git dependencies, and offline imports of packages
  installed by YubaPKG.
- [x] Bundled `std.*` modules for files, paths, time, randomness, math, JSON,
  encoding, processes, HTTP, CSV, URLs, and hashes.
- [x] REPL, formatter, output-based test runner with opt-in coverage, interactive
  debugger, and stdio language server with a workspace index.
- [x] Narrow C ABI calls and standalone executable releases.

## Core language and type system

- [ ] Specify and add conformance tests for every documented syntax rule,
  built-in, type rule, and diagnostic, including invalid programs.
- [ ] Identify high-value gaps in static inference and diagnostics; improve
  them incrementally without requiring dynamic programs to be fully typed.
- [ ] Define whether records need methods or richer constructors; specify
  receiver, visibility, initialization, aliasing, and equality semantics
  before implementation.
- [ ] Add a language-level resource type or iterator cleanup syntax only if new
  resource-bearing APIs need it beyond the runtime's general resource protocol.

## Concurrency and asynchronous I/O

- [ ] Collect use cases that require concurrent or asynchronous programs.
- [ ] If justified, define task scheduling, cancellation, failure propagation,
  shared-state rules, and interaction with the synchronous runtime.
- [ ] Add concurrency primitives and asynchronous standard-library APIs only
  after those semantics can be covered by deterministic tests.

## Developer tools and testing

- [ ] Verify language-server interoperability in a real desktop editor and
  record the tested client configuration. The stdio protocol and workspace
  index are covered by automated tests.
- [ ] Expand conformance and negative tests alongside each accepted language
  or runtime feature; keep examples runnable in CI.

## Projects, packaging, and native integrations

- [ ] Gather requirements for project build or application-bundle commands,
  especially generated code, native dependencies, platform targets, and
  reproducibility.
- [ ] Keep dependency resolution and downloads in YubaPKG; coordinate
  manifest, lockfile, and installed-layout changes through the published
  compatibility contract.
- [ ] Consider broader FFI types only with explicit ABI, ownership,
  error-handling, and cross-platform safety designs.
- [ ] Consider non-C extension mechanisms only if a concrete integration
  need cannot be met through the documented C ABI.

## Performance and implementation strategy

- [ ] Continue measuring representative workloads before changing interpreter
  architecture.
- [ ] Revisit bytecode, compilation, or caching only when measurements show a
  meaningful benefit and invalidation and distribution can be made reliable.

## Governance and release quality

- [ ] Record motivation, alternatives, compatibility impact, and tests for
  proposed syntax and runtime changes.
- [ ] For each release, maintain versioned reference docs, migration guidance,
  examples, cross-platform tests, and an accurate compatibility matrix.
- [ ] Keep claims about security boundaries, performance, platform support,
  and package compatibility tied to verified behavior.
