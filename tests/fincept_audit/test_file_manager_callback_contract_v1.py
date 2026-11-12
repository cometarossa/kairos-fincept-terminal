"""Static-only protection of Fincept's original file-manager callback."""
from pathlib import Path
import re
import unittest

SOURCE = Path(__file__).resolve().parents[2] / "fincept-qt/src/app/WindowFrame_Setup.cpp"


def strip_disabled_cpp(text):
    """Fail closed on unsupported inactive preprocessor branches (source-only)."""
    output, depth = [], 0
    for line in text.splitlines(keepends=True):
        if re.match(r"^\s*#\s*if\s+0\s*(?://.*)?$", line.strip()):
            depth += 1
            continue
        if depth:
            if re.match(r"^\s*#\s*(if|ifdef|ifndef)\b", line):
                depth += 1
            elif re.match(r"^\s*#\s*endif\b", line):
                depth -= 1
            elif depth == 1 and re.match(r"^\s*#\s*(else|elif)\b", line):
                raise ValueError("unsupported #if 0 alternate branch")
            continue
        output.append(line)
    if depth:
        raise ValueError("unterminated #if 0")
    return "".join(output)


def preserved(text):
    start = text.find('register_factory("file_manager"')
    end = text.find("register_factory(", start + 1)
    if start < 0 or end < 0:
        return False
    body = text[start:end]
    # Disabled preprocessor branches cannot satisfy a source contract.
    try:
        body = strip_disabled_cpp(body)
    except ValueError:
        return False
    # Mask comments and literals in one lexical pass: // inside a quoted
    # URL or raw string is not a C++ comment and must not erase live code.
    lexical = re.compile(
        r'R"(?P<delimiter>[A-Za-z0-9_]*)\\(.*?\\)(?P=delimiter)"|"(?:\\\\.|[^"\\\\])*"|/\\*.*?\\*/|//[^\\n]*',
        flags=re.DOTALL,
    )
    def mask_non_code(match):
        return "__CODE_EDITOR_LITERAL__" if match.group(0) == '"code_editor"' else " "
    body = lexical.sub(mask_non_code, body)
    tokens = (
        "new screens::FileManagerScreen;",
        "connect(fm, &screens::FileManagerScreen::open_file_in_screen, this,",
        "dock_router_->navigate(route_id);",
        "route_id == __CODE_EDITOR_LITERAL__ && !file_path.isEmpty()",
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

    def test_disconnected_sender_or_receiver_rejected(self):
        original = SOURCE.read_text(encoding="utf-8-sig")
        self.assertTrue(preserved(original))
        for before, after in (
            ("connect(fm, &screens::FileManagerScreen::open_file_in_screen, this,",
             "connect(other, &screens::FileManagerScreen::open_file_in_screen, this,"),
            ("connect(fm, &screens::FileManagerScreen::open_file_in_screen, this,",
             "connect(fm, &screens::FileManagerScreen::open_file_in_screen, other,"),
        ):
            with self.subTest(after=after):
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

    def test_preprocessor_disabled_navigation_rejected(self):
        original = SOURCE.read_text(encoding="utf-8-sig")
        self.assertTrue(preserved(original))
        altered = original.replace(
            "dock_router_->navigate(route_id);",
            "#if 0\n                    dock_router_->navigate(route_id);\n                    #endif",
            1,
        )
        self.assertNotEqual(altered, original)
        self.assertFalse(preserved(altered))

    def test_raw_string_cannot_impersonate_navigation(self):
        original = SOURCE.read_text(encoding="utf-8-sig")
        self.assertTrue(preserved(original))
        token = "dock_router_->navigate(route_id);"
        self.assertIn(token, original)
        for literal in (
            'R"(dock_router_->navigate(route_id);)"',
            'R"sentinel(dock_router_->navigate(route_id);)sentinel"',
        ):
            with self.subTest(literal=literal):
                altered = original.replace(token, "auto inert = " + literal + ";", 1)
                self.assertNotEqual(altered, original)
                self.assertFalse(preserved(altered))

    def test_ordinary_string_cannot_impersonate_navigation(self):
        original = SOURCE.read_text(encoding="utf-8-sig")
        self.assertTrue(preserved(original))
        token = "dock_router_->navigate(route_id);"
        self.assertIn(token, original)
        for literal in (
            '"dock_router_->navigate(route_id);"',
            '"prefix \\" dock_router_->navigate(route_id); suffix"',
        ):
            with self.subTest(literal=literal):
                altered = original.replace(token, "auto inert = " + literal + ";", 1)
                self.assertNotEqual(altered, original)
                self.assertFalse(preserved(altered))

    def test_comment_markers_inside_literals_preserve_live_navigation(self):
        original = SOURCE.read_text(encoding="utf-8-sig")
        self.assertTrue(preserved(original))
        token = "dock_router_->navigate(route_id);"
        self.assertIn(token, original)
        for prefix in (
            'auto url = "https://example.invalid/path"; ',
            'auto raw = R"tag(// not a comment)tag"; ',
            'auto quoted = "/* not a comment */"; ',
        ):
            with self.subTest(prefix=prefix):
                altered = original.replace(token, prefix + token, 1)
                self.assertTrue(preserved(altered))

    def test_opt_in_factory_allowed(self):
        original = SOURCE.read_text(encoding="utf-8-sig")
        self.assertTrue(preserved(original + '\ndock_router_->register_factory("kairos_opt_in", []() { return new screens::OptionalScreen; });\n'))


if __name__ == "__main__":
    unittest.main()
