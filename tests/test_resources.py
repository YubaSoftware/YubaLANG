import unittest

from lang.runtime import Runtime


class FakeResource:
    def __init__(self, name: str, log: list[str], fail: bool = False) -> None:
        self.name = name
        self.log = log
        self.fail = fail
        self.closed = False

    def close(self) -> None:
        self.closed = True
        self.log.append(self.name)
        if self.fail:
            raise OSError(f"{self.name} failed to close")


class ResourceLifecycleTests(unittest.TestCase):
    def test_resources_close_in_reverse_registration_order(self):
        log: list[str] = []
        runtime = Runtime()
        first = FakeResource("first", log)
        second = FakeResource("second", log)
        runtime.register_resource(first)
        runtime.register_resource(second)

        runtime.close_resources()

        self.assertEqual(log, ["second", "first"])
        self.assertTrue(first.closed)
        self.assertTrue(second.closed)
        self.assertEqual(runtime.resources, [])

    def test_duplicate_registration_closes_each_object_once(self):
        log: list[str] = []
        runtime = Runtime()
        resource = FakeResource("only", log)
        runtime.register_resource(resource)
        runtime.register_resource(resource)

        runtime.close_resources()

        self.assertEqual(log, ["only"])

    def test_every_resource_is_attempted_and_the_first_error_is_raised(self):
        log: list[str] = []
        runtime = Runtime()
        first = FakeResource("first", log)
        failing = FakeResource("failing", log, fail=True)
        runtime.register_resource(first)
        runtime.register_resource(failing)

        with self.assertRaisesRegex(OSError, "failing failed to close"):
            runtime.close_resources()

        self.assertEqual(log, ["failing", "first"])
        self.assertTrue(first.closed)
        self.assertEqual(runtime.resources, [])

    def test_close_resource_untracks_and_is_idempotent(self):
        log: list[str] = []
        runtime = Runtime()
        resource = FakeResource("file", log)
        runtime.register_resource(resource)

        runtime.close_resource(resource)
        runtime.close_resource(resource)

        self.assertEqual(log, ["file"])
        with self.assertRaises(TypeError):
            runtime.register_resource(object())

    def test_close_resource_is_idempotent_without_closed_attribute(self):
        log: list[str] = []

        class Handle:
            def close(self) -> None:
                log.append("closed")

        runtime = Runtime()
        handle = Handle()
        runtime.register_resource(handle)

        runtime.close_resource(handle)
        runtime.close_resource(handle)

        self.assertEqual(log, ["closed"])


if __name__ == "__main__":
    unittest.main()
