"""Offline regression for Fincept CMake's pinned historical QGeoView commit.

CMake FetchContent with GIT_SHALLOW TRUE does not ensure an old raw commit
is available after cloning the moving upstream default branch. This test:
  * checks the exact original CMake dependency pin and no shallow cloning
  * replays the regression with synthetic two-commit Git history over file://
    (shallow clone misses historical commit; full clone contains it).

No external network, Qt installation, broker or credentials are involved.
"""

from pathlib import Path
import re
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
CMAKE = ROOT / "fincept-qt" / "CMakeLists.txt"
QGEOVIEW_SHA = "4b2c52c80940e1073c259ded1a57df83036ba1c9"


def run(*args, cwd=None, check=True):
    return subprocess.run(
        args, cwd=cwd, text=True, capture_output=True, check=check, timeout=20,
    )


class QGeoViewHistoricalShaPinTest(unittest.TestCase):
    def test_cmake_uses_full_history_for_pinned_qgeoview(self):
        text = CMAKE.read_text(encoding="utf-8")
        block = re.search(
            r"FetchContent_Declare\(\s*QGeoView\s*(.*?)\n\)",
            text, flags=re.DOTALL,
        )
        self.assertIsNotNone(block, "QGeoView declaration missing")
        decl = block.group(1)
        self.assertIn("GIT_REPOSITORY https://github.com/AmonRaNet/QGeoView.git", decl)
        self.assertRegex(decl, r"GIT_TAG\s+" + QGEOVIEW_SHA)
        self.assertRegex(decl, r"GIT_SHALLOW\s+FALSE")
        self.assertNotRegex(decl, r"GIT_SHALLOW\s+TRUE")
        self.assertIn("PATCH_COMMAND", decl)
        self.assertIn("qgeoview_remove_agl.cmake", decl)

    def test_local_git_fixture_shallow_misses_historical_commit(self):
        with tempfile.TemporaryDirectory(prefix="fincept-qgeo-sha-") as tmp:
            root = Path(tmp)
            repo, bare = root / "source", root / "remote.git"
            run("git", "init", "-q", "-b", "main", str(repo))
            for number in ("one", "two"):
                (repo / "sample.txt").write_text(number)
                run("git", "add", "sample.txt", cwd=repo)
                run(
                    "git", "-c", "user.name=Offline QA",
                    "-c", "user.email=qa@example.invalid",
                    "commit", "-qm", number, cwd=repo,
                )
                if number == "one":
                    first_sha = run("git", "rev-parse", "HEAD", cwd=repo).stdout.strip()

            run("git", "clone", "-q", "--bare", str(repo), str(bare))
            uri = bare.as_uri()  # real file:// transport, not optimized local copy
            shallow = root / "shallow"
            full = root / "full"
            run("git", "clone", "-q", "--depth=1", uri, str(shallow))
            self.assertEqual(
                run("git", "rev-parse", "--is-shallow-repository", cwd=shallow)
                .stdout.strip(), "true",
            )
            self.assertNotEqual(
                run("git", "cat-file", "-e", first_sha + "^{commit}",
                    cwd=shallow, check=False).returncode,
                0, "Old SHA unexpectedly available in one-commit shallow clone",
            )
            run("git", "clone", "-q", uri, str(full))
            self.assertEqual(
                run("git", "rev-parse", "--is-shallow-repository", cwd=full)
                .stdout.strip(), "false",
            )
            run("git", "cat-file", "-e", first_sha + "^{commit}", cwd=full)
            run("git", "checkout", "-q", "--detach", first_sha, cwd=full)
            self.assertEqual((full / "sample.txt").read_text(), "one")


if __name__ == "__main__":
    unittest.main()
