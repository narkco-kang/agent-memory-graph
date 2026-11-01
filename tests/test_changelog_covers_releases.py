"""Every released version must have a CHANGELOG entry, and the order must be descending.

Why this exists (2026-11-01): seven releases (0.37.0 through 0.38.1) were published to
GitHub and never written to CHANGELOG.md. CI was green the whole time. `verify.py` was
9/9 the whole time. Nobody noticed because nothing checked it.

`check_doc_sizes.py:52` lists CHANGELOG.md in OUT_OF_SCOPE with the comment that it is an
append-only log read top-to-bottom-never, so the only rule applied to it was a byte
budget. A record other people read dropped seven versions and no gate moved.

The test is deliberately cheap and offline:

  * the version currently in `pyproject.toml` must have a `## [x.y.z]` entry — this is
    the one that fires if someone bumps the version and runs `gh release create` without
    touching CHANGELOG (exactly the sequence that produced the gap)
  * entries must be in strictly descending order — a misplaced insert makes the history
    unreadable even when every version is present

A `gh release list` check would be stronger, but it needs network and credentials, so it
would be skipped in most runs and prove nothing where it matters. `git tag` is used when
available and silently skipped when not, which keeps the offline contract intact.
"""
import os
import re
import subprocess
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHANGELOG = os.path.join(ROOT, "CHANGELOG.md")
PYPROJECT = os.path.join(ROOT, "pyproject.toml")

ENTRY_RE = re.compile(r"^## \[([0-9]+(?:\.[0-9]+)*)\]", re.M)


def changelog_versions():
    with open(CHANGELOG, encoding="utf-8") as fh:
        return ENTRY_RE.findall(fh.read())


def project_version():
    with open(PYPROJECT, encoding="utf-8") as fh:
        m = re.search(r'^version = "([^"]+)"', fh.read(), re.M)
    assert m, "pyproject.toml has no version line"
    return m.group(1)


def key(v):
    return tuple(int(p) for p in v.split("."))


class ChangelogCoversReleasesTest(unittest.TestCase):
    def test_the_current_version_has_an_entry(self):
        """Bump the version without writing CHANGELOG and this fails.

        This is the exact sequence that produced seven missing releases: bump, build,
        tag, release. The release step was reviewed by hand each time; the CHANGELOG step
        did not exist to be skipped.
        """
        current = project_version()
        self.assertIn(current, changelog_versions(),
                      f"pyproject.toml is at {current} but CHANGELOG.md has no "
                      f"'## [{current}]' entry. A release without its entry is how seven "
                      f"versions went missing on 2026-11-01.")

    def test_entries_are_in_descending_order(self):
        versions = changelog_versions()
        keys = [key(v) for v in versions]
        self.assertEqual(keys, sorted(keys, reverse=True),
                         "CHANGELOG entries must be newest-first; got " + ", ".join(versions[:8]))

    def test_no_duplicate_entries(self):
        versions = changelog_versions()
        dupes = {v for v in versions if versions.count(v) > 1}
        self.assertFalse(dupes, f"duplicate CHANGELOG entries: {sorted(dupes)}")

    def test_every_git_tag_has_an_entry(self):
        """Skipped where tags are unavailable (source tarball, shallow checkout)."""
        try:
            res = subprocess.run(["git", "tag", "--list", "v*"], cwd=ROOT,
                                 capture_output=True, text=True, timeout=10)
        except (OSError, subprocess.SubprocessError):
            self.skipTest("git unavailable")
        if res.returncode != 0:
            self.skipTest("not a git checkout")
        versions = set(changelog_versions())
        tags = [t.strip().lstrip("v") for t in res.stdout.splitlines() if t.strip()]
        missing = [t for t in tags if t not in versions]
        self.assertFalse(missing,
                         f"tags released without a CHANGELOG entry: {sorted(missing)}")


if __name__ == "__main__":
    unittest.main()
