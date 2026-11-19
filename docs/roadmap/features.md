# YubaLANG feature backlog

This backlog tracks capability areas that are not scheduled in the current
release plans. It is a planning aid, not a promise, and not every programming
language needs every item. Scheduled work lives in the [1.4 roadmap](1.4.md)
and the [1.5 roadmap](1.5.md); the canonical 1.4 checklist is
[todo.md](../../todo.md). Select new work based on concrete user needs, clear
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

Items scheduled elsewhere are intentionally not repeated here:

- Language ergonomics, types and diagnostics, standard-library expansion, and
  tooling completeness: [1.4 roadmap](1.4.md).
- Interpreter speed, bytecode execution, profiling, concurrency and async I/O,
  and FFI v2: [1.5 roadmap](1.5.md).
- Application build/bundle commands: deferred to 1.6, after the 1.5 performance
  and FFI work is measured.

## Core language and type system

- [ ] Evaluate class-based inheritance and richer object models only after the
  1.4 record-method and constructor work has real usage data.
- [ ] Extend pattern matching with guards, map/record patterns, and binding
  patterns once the 1.4 base is established.
- [ ] Define metaprogramming or macro facilities only for concrete
  code-generation needs that cannot be met by generators or functions.
- [ ] Consider multiple return values or richer destructuring if real programs
  repeatedly pack tuples.
- [ ] Separate a formal language specification from the implementation reference
  and keep conformance fixtures as the executable source of truth.
- [ ] Consider deep immutability or freeze operations if shared mutable records
  cause recurring defects.

## Concurrency and distributed execution

- [ ] Evaluate shared-memory parallelism only after single-threaded async
  semantics are stable and measured.
- [ ] Consider multi-process or distributed runtimes only with a concrete
  workload, failure model, and serialization design.
- [ ] Consider async server frameworks only after core async I/O and lifecycle
  limits are proven.
- [ ] Evaluate transactional or actor-style state management if shared mutable
  state remains the common source of async bugs.

## Developer tools and testing

- [ ] Verify the language server across a wider editor matrix (VS Code, Neovim,
  Helix, and a JetBrains client) and record each tested configuration.
- [ ] Add remote or attach debugging for long-running processes if embedding
  hosts require it.
- [ ] Consider record/replay or time-travel debugging only with a deterministic
  runtime trace format.
- [ ] Consider incremental test selection or impact analysis for large projects.
- [ ] Add richer snapshot-testing workflows beyond golden output if real suites
  need them.

## Projects, packaging, and native integrations

- [ ] Implement application build/bundle commands in 1.6 for generated code,
  native dependencies, assets, reproducible inputs, and platform artifacts.
- [ ] Generate C bindings from headers or a declaration file once FFI v2 types
  are stable.
- [ ] Add signed artifact and provenance checks for packages and release
  binaries; coordinate metadata and registry behavior with YubaPKG.
- [ ] Evaluate non-C extension mechanisms only if a concrete integration need
  cannot be met through the extended C ABI.
- [ ] Keep dependency resolution, downloads, and registry metadata ownership in
  YubaPKG; coordinate manifest and lockfile changes through the published
  compatibility contract.
- [ ] Consider package documentation hosting or generated API indexes for the
  ecosystem; registry storage remains YubaPKG's responsibility.

## Performance and implementation strategy

- [ ] Evaluate a JIT only if the 1.5 bytecode engine saturates and measurements
  show a further repeatable win.
- [ ] Parallelize bytecode compilation for multi-file projects if build latency
  becomes the dominant cost.
- [ ] Add incremental compilation artifacts for large projects if the 1.5 cache
  design does not cover them.
- [ ] Continue reducing interpreter memory and allocation churn after the 1.5
  speed work, with tracked workloads and no unmeasured rewrites.
- [ ] Revisit runtime data-structure choices only with profiles that show a
  specific bottleneck.

## Ecosystem and governance

- [ ] Build a versioned documentation site with search and per-release archives.
- [ ] Publish a security policy, vulnerability reporting process, and supported
  version window.
- [ ] Execute the deprecation policy consistently: name replacements, document
  migration, and remove only after the promised window.
- [ ] Automate release packaging, smoke tests, and checksum publication for every
  supported platform.
- [ ] Define a long-term-support cadence if commercial or institutional users
  require one.
- [ ] Keep claims about security boundaries, performance, platform support, and
  package compatibility tied to verified behavior.
- [ ] For each release, maintain versioned reference docs, migration guidance,
  examples, cross-platform tests, and an accurate compatibility matrix.
