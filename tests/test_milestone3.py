import contextlib
import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from lang.interpreter import Runtime, execute_lines


class Milestone3Tests(unittest.TestCase):
    def execute(self, source: str, runtime: Runtime | None = None) -> Runtime:
        runtime = runtime or Runtime()
        execute_lines(
            source.strip().splitlines(),
            runtime,
            source_name="milestone3.yl",
        )
        return runtime

    def assert_program_error(
        self, source: str, code: str, runtime: Runtime | None = None
    ) -> str:
        output = io.StringIO()
        with contextlib.redirect_stdout(output), self.assertRaises(SystemExit):
            self.execute(source, runtime)
        self.assertIn(f"[{code}]", output.getvalue())
        return output.getvalue()

    def test_regex_compiled_patterns_matching_and_replacement(self) -> None:
        runtime = self.execute(
            r'''
            import std.regex as regex
            define var compiled: dict = {}
            define var found: list = []
            define var replaced: string = ""
            define var result: dict = {}
            define var parts: list = []
            func call regex.compile "(?P<word>\\w+)-(\\d+)" -> compiled
            func call regex.findall "\\d+" "a1b22c333" -> found
            func call regex.sub "\\d+" "#" "a1b22" -> replaced
            func call regex.search compiled "item-42" -> result
            func call regex.split "-" "a-b-c" -> parts
            '''
        )

        self.assertEqual(runtime.require_var("found")["value"], ["1", "22", "333"])
        self.assertEqual(runtime.require_var("replaced")["value"], "a#b#")
        self.assertEqual(runtime.require_var("parts")["value"], ["a", "b", "c"])
        result = runtime.require_var("result")["value"]
        self.assertEqual(result["match"], "item-42")
        self.assertEqual(result["groups"], ["item", "42"])
        self.assertEqual(result["groupdict"], {"word": "item"})

    def test_regex_rejects_nested_quantifiers_by_default(self) -> None:
        self.assert_program_error(
            """
            import std.regex as regex
            define var compiled: dict = {}
            func call regex.compile "(a+)+$" -> compiled
            """,
            "regex-backtracking",
        )

    def test_glob_matching_filtering_and_walking(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "one.txt").write_text("1", encoding="utf-8")
            (root / "two.log").write_text("2", encoding="utf-8")
            (root / "nested").mkdir()
            (root / "nested" / "three.txt").write_text("3", encoding="utf-8")
            runtime = self.execute(
                f"""
                import std.glob as glob
                define var expanded: list = []
                define var paths: list = ["one.txt", "two.log", "notes.txt"]
                define var filtered: list = []
                define var walked: list = []
                func call glob.expand {json.dumps(str(root / "*.txt"))} -> expanded
                func call glob.filter paths "*.txt" -> filtered
                func call glob.walk {json.dumps(str(root))} "*.txt" recursive=true -> walked
                """
            )

        self.assertEqual(
            runtime.require_var("expanded")["value"],
            [str(root / "one.txt")],
        )
        self.assertEqual(
            runtime.require_var("filtered")["value"], ["notes.txt", "one.txt"]
        )
        self.assertEqual(
            runtime.require_var("walked")["value"],
            [str(root / "nested" / "three.txt"), str(root / "one.txt")],
        )

    def test_tempfile_resources_are_removed_at_runtime_cleanup(self) -> None:
        runtime = self.execute(
            """
            import std.tempfile as tempfile
            define var file_handle: dict = {}
            define var directory_handle: dict = {}
            define var file_path: string = ""
            define var tracked: bool = false
            func call tempfile.file suffix=".txt" text="temporary" -> file_handle
            func call tempfile.directory prefix="yuba-" -> directory_handle
            getattr file_handle "path" file_path
            func call tempfile.is_tracked file_path -> tracked
            """
        )
        file_path = Path(runtime.require_var("file_handle")["value"]["path"])
        directory_path = Path(
            runtime.require_var("directory_handle")["value"]["path"]
        )

        self.assertTrue(file_path.is_file())
        self.assertEqual(file_path.read_text(encoding="utf-8"), "temporary")
        self.assertTrue(directory_path.is_dir())
        self.assertTrue(runtime.require_var("tracked")["value"])

        runtime.close_resources()
        self.assertFalse(file_path.exists())
        self.assertFalse(directory_path.exists())

    def test_archive_round_trip_and_path_traversal_protection(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive_path = root / "bundle.zip"
            source_path = root / "source.txt"
            source_path.write_text("from file", encoding="utf-8")
            runtime = self.execute(
                f"""
                import std.archive as archive
                define var writer: dict = {{}}
                define var names: list = []
                define var entries: list = []
                define var text: string = ""
                define var extracted: list = []
                func call archive.create {json.dumps(str(archive_path))} -> writer
                func call archive.add_text writer "inside.txt" "hello"
                func call archive.add_file writer "source.txt" {json.dumps(str(source_path))}
                func call archive.close writer
                func call archive.list {json.dumps(str(archive_path))} -> names
                func call archive.info {json.dumps(str(archive_path))} -> entries
                func call archive.read_text {json.dumps(str(archive_path))} "inside.txt" -> text
                func call archive.extract {json.dumps(str(archive_path))} {json.dumps(str(root / "out"))} -> extracted
                """
            )

            self.assertEqual(
                runtime.require_var("names")["value"],
                ["inside.txt", "source.txt"],
            )
            self.assertEqual(runtime.require_var("text")["value"], "hello")
            self.assertEqual(
                (root / "out" / "inside.txt").read_text(encoding="utf-8"),
                "hello",
            )
            self.assertEqual(
                (root / "out" / "source.txt").read_text(encoding="utf-8"),
                "from file",
            )
            self.assertEqual(
                len(runtime.require_var("entries")["value"]), 2
            )

            bad_archive = root / "bad.zip"
            with zipfile.ZipFile(bad_archive, "w") as archive:
                archive.writestr("../escape.txt", "bad")
            self.assert_program_error(
                f"""
                import std.archive as archive
                define var extracted: list = []
                func call archive.extract {json.dumps(str(bad_archive))} {json.dumps(str(root / "bad-out"))} -> extracted
                """,
                "archive-error",
            )

    def test_sqlite_parameter_binding_transactions_and_cleanup(self) -> None:
        runtime = self.execute(
            """
            import std.sqlite as sqlite
            define var database: dict = {}
            define var result: dict = {}
            define var rows: list = []
            define var tables: list = []
            define var params: list = ["first"]
            define var second_params: list = ["second"]
            func call sqlite.open ":memory:" -> database
            func call sqlite.execute database "CREATE TABLE items (id INTEGER PRIMARY KEY, name TEXT)" -> result
            func call sqlite.execute database "INSERT INTO items (name) VALUES (?)" params -> result
            func call sqlite.begin database
            func call sqlite.execute database "INSERT INTO items (name) VALUES (?)" second_params -> result
            func call sqlite.rollback database
            func call sqlite.query database "SELECT * FROM items ORDER BY id" -> rows
            func call sqlite.tables database -> tables
            func call sqlite.close database
            func call sqlite.close database
            """
        )

        self.assertEqual(runtime.require_var("rows")["value"], [{"id": 1, "name": "first"}])
        self.assertEqual(runtime.require_var("tables")["value"], ["items"])
        self.assertTrue(runtime.require_var("database")["value"])

    def test_uuid_decimal_and_statistics_helpers(self) -> None:
        runtime = self.execute(
            '''
            import std.uuid as uuid
            import std.decimal as decimal
            import std.statistics as statistics
            define var identifier: string = ""
            define var parsed: dict = {}
            define var valid: bool = false
            define var total: string = ""
            define var quotient: string = ""
            define var values: list = [1, 2, 3, 4]
            define var summary: dict = {}
            define var middle: float = 0.0
            func call uuid.uuid5 "dns" "example.com" -> identifier
            func call uuid.parse identifier -> parsed
            func call uuid.is_valid identifier -> valid
            func call decimal.add "1.1" "2.2" -> total
            func call decimal.divide "1" "3" precision=10 -> quotient
            func call statistics.summary values -> summary
            func call statistics.percentile values 50 -> middle
            '''
        )

        self.assertEqual(
            runtime.require_var("identifier")["value"],
            "cfbff0d1-9375-5685-968c-48ce8b15ae17",
        )
        self.assertTrue(runtime.require_var("valid")["value"])
        self.assertEqual(
            runtime.require_var("parsed")["value"]["version"], 5
        )
        self.assertEqual(runtime.require_var("total")["value"], "3.3")
        self.assertEqual(runtime.require_var("quotient")["value"], "0.3333333333")
        self.assertEqual(runtime.require_var("summary")["value"]["count"], 4)
        self.assertEqual(runtime.require_var("middle")["value"], 2.5)

    def test_logging_terminal_and_environment_modules(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            log_path = Path(directory) / "app.log"
            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                runtime = self.execute(
                    f"""
                    import std.logging as logging
                    import std.terminal as terminal
                    import std.env as environment
                    define var configuration: dict = {{}}
                    define var handler: dict = {{}}
                    define var styled: string = ""
                    define var plain: string = ""
                    define var has_path: bool = false
                    define var arguments: list = []
                    func call logging.configure "info" "stderr" false -> configuration
                    func call logging.add_file {json.dumps(str(log_path))} -> handler
                    func call logging.info "started"
                    func call terminal.style "hello" fg="red" bold=true -> styled
                    func call terminal.strip_ansi styled -> plain
                    func call environment.has "PATH" -> has_path
                    func call environment.args -> arguments
                    """,
                    Runtime(program_args=["first", "second"]),
                )
                runtime.close_resources()

            self.assertIn("INFO started", stderr.getvalue())
            self.assertIn("INFO started", log_path.read_text(encoding="utf-8"))
            self.assertEqual(runtime.require_var("plain")["value"], "hello")
            self.assertIn("\x1b[", runtime.require_var("styled")["value"])
            self.assertTrue(runtime.require_var("has_path")["value"])
            self.assertEqual(
                runtime.require_var("arguments")["value"], ["first", "second"]
            )

    def test_file_seek_tell_readline_iteration_and_binary_io(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            text_path = root / "data.txt"
            text_path.write_text("one\ntwo\nthree\n", encoding="utf-8", newline="")
            binary_path = root / "data.bin"
            runtime = self.execute(
                f"""
                open {json.dumps(str(text_path))} "r" handle
                define var line: string = ""
                define var position: int = 0
                define var prefix: string = ""
                define var first: string = ""
                define var second: string = ""
                file readline handle line
                file tell handle position
                file seek handle 0 0
                file read handle 3 prefix
                file seek handle 0 0
                iter handle lines
                next lines first
                next lines second
                close lines
                close lines
                define var payload: bytes = "binary"
                open {json.dumps(str(binary_path))} "wb" binary_handle
                file write binary_handle payload
                close binary_handle
                open {json.dumps(str(binary_path))} "rb" binary_handle
                define var contents: bytes = ""
                file read binary_handle contents
                close binary_handle
                """
            )
            runtime.close_resources()

        self.assertEqual(runtime.require_var("line")["value"], "one\n")
        self.assertEqual(runtime.require_var("position")["value"], 4)
        self.assertEqual(runtime.require_var("prefix")["value"], "one")
        self.assertEqual(runtime.require_var("first")["value"], "one\n")
        self.assertEqual(runtime.require_var("second")["value"], "two\n")
        self.assertEqual(runtime.require_var("contents")["value"], b"binary")

    def test_atomic_file_replacement(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "atomic.txt"
            target.write_text("old", encoding="utf-8")
            runtime = self.execute(
                f"""
                import std.fs as fs
                func call fs.atomic_write_text {json.dumps(str(target))} "new"
                define var contents: string = ""
                func call fs.read_text {json.dumps(str(target))} -> contents
                """
            )
        self.assertEqual(runtime.require_var("contents")["value"], "new")

    def test_typed_errors_expose_kind_stack_and_cause(self) -> None:
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            runtime = self.execute(
                """
                define var root: dict = {}
                define var outer: dict = {}
                define var caught: dict = {}
                define var cause: dict = {}
                define var stack: list = []
                define var kind: string = ""
                define var cause_kind: string = ""
                define var stack_length: int = 0
                error io "disk full" root
                error archive "zip failed" outer root
                try
                    throw outer
                catch archive as caught
                    getattr caught "kind" kind
                    getattr caught "cause" cause
                    getattr cause "kind" cause_kind
                    getattr caught "stack" stack
                    len stack stack_length
                    text output kind
                    text output cause_kind
                    text output stack_length
                endtry
                """
            )

        self.assertEqual(
            output.getvalue().splitlines(), ["archive", "io", "1"]
        )
        self.assertEqual(runtime.require_var("kind")["value"], "archive")
        self.assertEqual(runtime.require_var("cause_kind")["value"], "io")

    def test_non_matching_catch_kind_rethrows(self) -> None:
        output = io.StringIO()
        with contextlib.redirect_stdout(output), self.assertRaises(SystemExit):
            self.execute(
                """
                define var error_value: dict = {}
                define var caught: dict = {}
                error io "disk full" error_value
                try
                    throw error_value
                catch type as caught
                    text output "wrong"
                endtry
                """
            )
        self.assertIn("disk full", output.getvalue())
        self.assertNotIn("wrong", output.getvalue())

    def test_configured_limits_and_sys_set_limit(self) -> None:
        with self.assertRaises(ValueError):
            Runtime(http_default_max_bytes=10, http_max_bytes=5)

        runtime = Runtime(max_collection_size=2)
        self.assert_program_error(
            """
            define var values: list = [1, 2, 3]
            """,
            "limit-error",
            runtime,
        )

        runtime = self.execute(
            """
            import std.sys as sys
            define var limits: dict = {}
            func call sys.limits -> limits
            func call sys.set_limit "max_call_depth" 256 -> limits
            """
        )
        self.assertEqual(runtime.max_call_depth, 256)
        self.assertEqual(runtime.require_var("limits")["value"]["max_call_depth"], 256)

        self.assert_program_error(
            """
            import std.sys as sys
            define var limits: dict = {}
            func call sys.set_limit "max_call_depth" 0 -> limits
            """,
            "value-error",
        )

    def test_recursion_limit_uses_the_configured_depth(self) -> None:
        self.assert_program_error(
            """
            func define recurse
                func call recurse
            endfunc
            func call recurse
            """,
            "stack-overflow",
            Runtime(max_call_depth=4),
        )

    def test_iterator_resources_close_once_and_cleanup_is_deterministic(self) -> None:
        events: list[str] = []

        class Resource:
            def __init__(self, name: str, fail: bool = False) -> None:
                self.name = name
                self.fail = fail
                self.closed = False

            def close(self) -> None:
                if self.closed:
                    return
                self.closed = True
                events.append(self.name)
                if self.fail:
                    raise OSError(f"{self.name} failed")

        first = Resource("first", fail=True)
        second = Resource("second")
        runtime = Runtime()
        runtime.register_resource(first)
        runtime.register_resource(second)
        runtime.close_resource(second)
        runtime.close_resource(second)

        with self.assertRaises(OSError):
            runtime.close_resources()
        self.assertEqual(events, ["second", "first"])

    def test_dictionary_order_is_insertion_order(self) -> None:
        runtime = self.execute(
            """
            define var values: dict = {"first": 1, "second": 2, "third": 3}
            """
        )
        self.assertEqual(
            list(runtime.require_var("values")["value"]), ["first", "second", "third"]
        )


if __name__ == "__main__":
    unittest.main()
