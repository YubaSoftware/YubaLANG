# YubaLANG language server

YubaLANG includes a lightweight Language Server Protocol (LSP) server for
`.yl` files. It uses the standard input/output JSON-RPC transport and the
Python standard library; it does not execute the open source file.

## Starting the server

From the repository root, configure an LSP-capable editor to start:

```text
py YubaLANG.py --lsp
```

The server communicates over stdin/stdout. Configure the editor's LSP client
to use that command, associate `.yl` files with YubaLANG, and avoid wrapping
the command in a shell that writes banners to stdout. In VS Code, a generic
LSP client extension is required because VS Code does not include a built-in
client for arbitrary language servers.

### Neovim setup

Neovim 0.10 or newer has a built-in LSP client. With YubaLANG on `PATH`, add a
filetype and server configuration to `init.lua`:

```lua
vim.filetype.add({ extension = { yl = "yubalang" } })
vim.lsp.config("yubalang", {
  cmd = { "YubaLANG", "--lsp" },
  filetypes = { "yubalang" },
  root_markers = { "yuba.json", ".git" },
})
vim.lsp.enable("yubalang")
```

Open a project directory so the server receives a workspace root; the index
then discovers `.yl` files under that root. From a source checkout, use
`cmd = { "py", "-3", "YubaLANG.py", "--lsp" }` with the checkout as the working
directory. Neovim's `:LspInfo` shows whether the server attached, and
`:checkhealth vim.lsp` reports client errors.

### VS Code setup

Install the `zsol.vscode-glspc` Generic LSP Client extension (or another
generic client), then add these workspace settings:

```json
{
  "files.associations": { "*.yl": "yubalang" },
  "glspc.server.command": "YubaLANG",
  "glspc.server.commandArguments": ["--lsp"],
  "glspc.server.languageId": ["yubalang"],
  "glspc.trace.server": "messages"
}
```

From a source checkout, set `glspc.server.command` to `py` and
`glspc.server.commandArguments` to `["YubaLANG.py", "--lsp"]`, and open the
checkout as the workspace folder. The server only needs the stdio transport; no
extension configuration is required beyond the command, arguments, language
identifier, and file association. Set the trace option to `off` after
diagnosing startup problems. Reload the window or run
`Generic LSP Client: Restart server` after changing the settings.

The stdio protocol and workspace index are exercised by
`py -m unittest tests.test_lsp` and `py tools/smoke_lsp.py`; real-editor smoke
testing requires a desktop editor session and is not automated in CI.

## Supported features

- Open, full-document and ranged change, and close notifications.
- Syntax diagnostics for malformed quoting, invalid or unknown commands,
  invalid declarations, unclosed or mismatched blocks, and statically evident
  type mismatches.
- Warning diagnostics for unreachable code and shadowed variables, published
  with LSP severity `2`.
- Stable diagnostic `code` values shared with `YubaLANG check --json` and
  `YubaLANG explain`.
- Project import diagnostics using the nearest manifest and checked lockfile;
  dependency resolution is local and does not access the network.
- Go to definition for declared variables, function parameters, and functions.
- Go to definition, hover, completion, signature help, and workspace symbols
  for public functions in imported project dependencies.
- Hover documentation for language commands, built-ins, and types.
- Completion for commands, types, and symbols in open documents and
  namespaced project dependency functions.
- Signature help for user-defined functions and imported project functions.
- Find references and rename for symbols in open documents.
- Workspace index for `.yl` files under initialized workspace folders, so
  workspace symbols, completion, unique definition lookup, references, and
  rename can include unopened files.
- Document and workspace symbol search.
- Quick fixes for misspelled command names.
- Incremental document changes with stale-version rejection.

Diagnostics and symbol lookup are static and intentionally do not execute
programs. Editors may send full or ranged document changes with monotonically
increasing versions. The workspace index is built on demand, cached by file
modification time, and invalidated by open, change, close, and
`workspace/didChangeWatchedFiles` notifications. It skips hidden directories,
`.yuba`, `__pycache__`, `node_modules`, `.venv`, `venv`, `env`, and files larger
than 1 MiB. Workspace-wide references and rename apply only to top-level
variables, functions, and record types; locals and parameters remain limited to
open documents so a rename cannot edit an unrelated binding in another file.
Ambiguous workspace matches are not renamed. Project imports are resolved
against the nearest project's checked lockfile and installed package contents.
Unavailable imports produce diagnostics, and resolution never downloads
packages. Dependency symbols are read-only. Completion and signature help are
best-effort suggestions, not a complete semantic type engine.

## Try it

Open [`examples\functions.yl`](../../examples/functions.yl) in an LSP-capable
editor configured to launch the command above. Hover over `func`, `return`,
or `filter`; try completion, signature help, references, and rename on
`is_positive` or `values`.

To verify the stdio server without an editor, run the automated tests from the
repository root:

```text
py -m unittest tests.test_lsp
```
