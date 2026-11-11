"""Source-level regression checks for the isolated Qt empty-registry fail-closed fix.

These tests do not compile or run Qt and do not claim runtime GUI coverage.
"""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "fincept-qt/src/app/ScreenSmokeTest.cpp"


def inspect_guard(text):
    inventory = text.find("const QStringList ids = router->all_screen_ids();")
    guard = text.find("if (ids.isEmpty())")
    loop = text.find("for (const QString& id : ids)")
    terminal = text.find("if (failures.isEmpty())")
    if min(inventory, guard, loop, terminal) < 0:
        return False
    segment = text[guard:loop]
    return (inventory < guard < loop < terminal
            and bool(re.search(r"if\s*\(ids\.isEmpty\(\)\)\s*\{[^}]*return\s+4\s*;", segment, re.S))
            and '[Smoke] FAIL: no registered screens to test' in segment)


class QtEmptyRegistryFailClosedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = SOURCE.read_text(encoding="utf-8-sig")

    def test_original_harness_rejects_empty_registry_before_loop(self):
        self.assertTrue(inspect_guard(self.source))

    def test_missing_guard_is_rejected(self):
        self.assertFalse(inspect_guard(self.source.replace("if (ids.isEmpty())", "if (false)", 1)))

    def test_success_return_in_empty_guard_is_rejected(self):
        self.assertFalse(inspect_guard(self.source.replace("return 4;", "return 0;", 1)))

    def test_guard_moved_after_iteration_is_rejected(self):
        guard_start = self.source.index("    if (ids.isEmpty())")
        guard_end = self.source.index("    QStringList failures;", guard_start)
        moved = self.source[:guard_start] + self.source[guard_end:]
        self.assertFalse(inspect_guard(moved))


if __name__ == "__main__":
    unittest.main()
