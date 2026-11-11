"""Static-only protection of Fincept's original file-manager callback."""
from pathlib import Path
import re
import unittest

SOURCE = Path(__file__).resolve().parents[2] / "fincept-qt/src/app/WindowFrame_Setup.cpp"


def preserved(text):
    start = text.find('register_factory("file_manager"')
    end = text.find("register_factory(", start + 1)
    if start < 0 or end < 0:
        return False
    body = text[start:end]
    # Comments cannot satisfy a source-preservation contract.
    body = re.sub(r"/\*.*?\*/|//[^\n]*", "", body, flags=re.DOTALL)
    tokens = (
        "new screens::FileManagerScreen;",
        "&screens::FileManagerScreen::open_file_in_screen",
        "dock_router_->navigate(route_id);",
        'route_id == "code_editor" && !file_path.isEmpty()',
        "dock_router_->materialize_now(route_id);",
        "nb->open_notebook_path(file_path);",
    )
    return all(t in body for t in tokens) and all(
        body.index(a) < body.index(b) for a, b in zip(tokens, tokens[1:])
    )


class FileManagerSourceContractTests(unittest.TestCase):
    def test_original_callback(self):
        self.assertTrue(preserved(SOURCE.read_text(encoding="utf-8-sig")))

    def test_negative_mutations(self):
        original = SOURCE.read_text(encoding="utf-8-sig")
        for before, after in (
            ("dock_router_->navigate(route_id);", 'dock_router_->navigate("dashboard");'),
            ("dock_router_->materialize_now(route_id);", "// removed"),
            ("nb->open_notebook_path(file_path);", "nb->close();"),
        ):
            with self.subTest(before=before):
                self.assertIn(before, original)
                self.assertFalse(preserved(original.replace(before, after, 1)))

    def test_commented_out_navigation_rejected(self):
        original = SOURCE.read_text(encoding="utf-8-sig")
        self.assertTrue(preserved(original))
        altered = original.replace(
            "dock_router_->navigate(route_id);",
            "// dock_router_->navigate(route_id);",
            1,
        )
        self.assertNotEqual(altered, original)
        self.assertFalse(preserved(altered))

    def test_opt_in_factory_allowed(self):
        original = SOURCE.read_text(encoding="utf-8-sig")
        self.assertTrue(preserved(original + '\ndock_router_->register_factory("kairos_opt_in", []() { return new screens::OptionalScreen; });\n'))


if __name__ == "__main__":
    unittest.main()
