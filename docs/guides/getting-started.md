# Getting started with YubaLANG

This short guide takes a new user from a source file to a checked, runnable
program. To install a release, follow the [installation guide](../setup/install.md).

## 1. Create a program

Save the following as `welcome.yl`:

```hl
define var learner: string = "Ada"
define var score: int = 85
define var passed: bool = false

compare score >= 60 passed

if passed
    text output "Welcome!"
    text output learner
else
    text output "Keep practicing."
endif

func define congratulate name
    text output "Good job!"
    text output name
endfunc

func call congratulate learner
```

YubaLANG uses one command per line. Expression-bearing commands accept
literals, variables, arithmetic, comparisons, and function calls; commands such
as `compare` still store their result in a variable. Blocks are closed with
keywords such as `endif` and `endfunc`.

## 2. Check and run it

From a source checkout on Windows:

```powershell
py -3 YubaLANG.py check welcome.yl
py -3 YubaLANG.py welcome.yl
```

With an installed release, use `YubaLANG.exe` on Windows or `YubaLANG` on
macOS and Linux:

```text
YubaLANG check welcome.yl
YubaLANG welcome.yl
```

The check command reports syntax problems and statically detectable type
mismatches without running the program. It is an aid, not a guarantee that
every runtime error will be found. Running the program prints:

```text
Welcome!
Ada
Good job!
Ada
```

The runnable [getting-started example](../../examples/getting-started.yl) is
kept under test with its expected output.

## 3. Continue learning

- Try the interactive interpreter with `YubaLANG repl` (or
  `py -3 YubaLANG.py repl` from the checkout); enter `exit` to leave.
- Debug a program with `YubaLANG debug --break [file:]line <file.yl>` and run
  output tests with `YubaLANG test`; add `--coverage` for executable-line
  coverage.
- Browse the [language reference](../1.4-docs.md) for commands, types, and
  control flow.
- Use the [examples](../../examples/) as complete programs.
- For a project with imports and dependencies, see the
  [project and package guide](../projects/package-manager.md).
