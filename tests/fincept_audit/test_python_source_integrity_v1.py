"""Reject non-Python device transcript lines in Fincept source audit tools."""
import ast
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
PATHS = (
    "tests/fincept_audit/test_qt_screen_smoke_contract_v1.py",
    "tools/fincept_audit/qt_screen_smoke_contract_v1.py",
)


class PythonSourceIntegrityTests(unittest.TestCase):
    def test_audit_python_sources_parse(self):
        for relative in PATHS:
            with self.subTest(path=relative):
                source = (ROOT / relative).read_text(encoding="utf-8-sig")
                ast.parse(source, filename=relative)

    def test_device_transcript_injection_is_rejected(self):
        for relative in PATHS:
            with self.subTest(path=relative):
                source = (ROOT / relative).read_text(encoding="utf-8-sig")
                altered = source + "\n[executed on device: fixture-host (synthetic)]\n"
                with self.assertRaises(SyntaxError):
                    ast.parse(altered, filename=relative)


if __name__ == "__main__":
    unittest.main()
