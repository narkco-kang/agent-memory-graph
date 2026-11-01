"""MANIFEST.in must still ship every file `check_dist.py` expects in the sdist.

The defect this locks: v0.37.0 added `docs/AUDIT.md` and decision pages 56/57. The
`dist/` on disk was a stale 0.36.1 build, so `tools/check_dist.py` reported three
missing documents. Rebuilding fixed the symptom, but a rebuild is not a guard. When
the guard was finally mutated — commenting out `recursive-include docs *.md *.json` —
`tools/check_dist.py` did go red (75 problems). That red was the only thing standing
between this repository and an sdist that silently drops every document.

It went red only because someone ran the mutation by hand. Nothing in the suite
would have noticed, so the next person to "tidy up" MANIFEST.in gets no warning
until a release artifact is already wrong. These tests notice.

Two things are asserted, and they are different questions:

1. `MANIFEST.in` actually contains the `recursive-include` lines the tree needs, and
   `check_dist.py` still derives its document list from the working tree rather than a
   hard-coded list that would go stale the moment a page is added.
2. Every file currently under `docs/` is matched by one of those lines. This is a
   narrow re-implementation of sdist's own glob rules — enough to catch a deleted or
   mistyped pattern, and deliberately not a claim to reproduce setuptools exactly.

What is *not* checked here: that a built tarball contains the files. That is
`tools/check_dist.py`'s job, run against real artifacts by `tools/verify.py`. A fast
unit test cannot replace it, and the day it tries to is the day it starts lying.
"""
import fnmatch
import os
import pathlib
import re
import unittest

REPO = pathlib.Path(__file__).resolve().parents[1]
MANIFEST = REPO / "MANIFEST.in"


def manifest_rules():
    """Return the `recursive-include` and `include` rules, in order, as (kind, args)."""
    rules = []
    for raw in MANIFEST.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if parts[0] == "recursive-include":
            rules.append(("recursive", parts[1], parts[2:]))
        elif parts[0] == "include":
            rules.append(("include", parts[1], []))
    return rules


def covered_by_rules(rel, rules):
    """Does any rule match this repo-relative POSIX path?"""
    for rule in rules:
        if rule[0] == "include":
            if fnmatch.fnmatch(rel, rule[1]):
                return True
            continue
        _, directory, patterns = rule
        prefix = directory.rstrip("/") + "/"
        if not rel.startswith(prefix):
            continue
        tail = rel[len(prefix):]
        for pattern in patterns:
            # recursive-include matches at any depth
            if fnmatch.fnmatch(tail, pattern) or fnmatch.fnmatch(os.path.basename(tail), pattern):
                return True
    return False


def tree_under_docs():
    files = []
    for current, _dirs, names in os.walk(REPO / "docs"):
        for name in names:
            if name.endswith(".pyc") or "__pycache__" in current:
                continue
            path = pathlib.Path(current) / name
            files.append(path.relative_to(REPO).as_posix())
    return sorted(files)


class ManifestStillCoversDocsTest(unittest.TestCase):
    def test_manifest_in_exists(self):
        self.assertTrue(MANIFEST.is_file(), "MANIFEST.in is how the sdist gets its documents")

    def test_manifest_has_a_recursive_include_for_docs(self):
        """The exact line whose removal turned check_dist.py red. Pin it."""
        rules = manifest_rules()
        directories = [rule[1] for rule in rules if rule[0] == "recursive"]
        self.assertIn(
            "docs", directories,
            "MANIFEST.in dropped `recursive-include docs`; the sdist will lose every "
            "document and tools/check_dist.py will report ~75 problems",
        )
        doc_rule = next(rule for rule in rules if rule[0] == "recursive" and rule[1] == "docs")
        patterns = doc_rule[2]
        self.assertTrue(
            any(fnmatch.fnmatch("x.md", pattern) for pattern in patterns),
            f"the docs rule {patterns!r} no longer matches .md files",
        )
        self.assertTrue(
            any(fnmatch.fnmatch("x.json", pattern) for pattern in patterns),
            f"the docs rule {patterns!r} no longer matches .json (decisions/manifest.json)",
        )

    def test_the_three_documents_that_broke_the_037_sdist_are_covered(self):
        """Named, because these are the ones that actually shipped missing."""
        rules = manifest_rules()
        named = [
            "docs/AUDIT.md",
            "docs/decisions/56-audit-evidence-root.md",
            "docs/decisions/57-graph-file-is-shared.md",
        ]
        for rel in named:
            self.assertTrue((REPO / rel).is_file(), f"{rel} is missing from the working tree")
            self.assertTrue(
                covered_by_rules(rel, rules),
                f"MANIFEST.in does not ship {rel}; the sdist would be incomplete",
            )

    def test_every_file_under_docs_is_covered(self):
        """The general form: a new page must not need a MANIFEST edit to be shipped."""
        rules = manifest_rules()
        uncovered = [rel for rel in tree_under_docs() if not covered_by_rules(rel, rules)]
        self.assertEqual(
            uncovered, [],
            "these files under docs/ are matched by no MANIFEST.in rule, so the sdist "
            f"would drop them: {uncovered}",
        )

    def test_check_dist_derives_its_document_list_from_the_tree(self):
        """check_dist must walk docs/, not hold a list that goes stale."""
        source = (REPO / "tools" / "check_dist.py").read_text(encoding="utf-8")
        self.assertIn("os.walk", source, "check_dist.py must walk docs/ to build its expectations")
        self.assertRegex(
            source, r"def expected_docs\(",
            "check_dist.py must keep a derived expected_docs(), not an inline list",
        )
        # A hard-coded decision page number would be the regression: pages are numbered forever.
        listed_pages = re.findall(r"docs/decisions/\d+[-a-z0-9]*\.md", source)
        self.assertEqual(
            listed_pages, [],
            f"check_dist.py hard-codes decision pages {listed_pages}; derive them instead",
        )


if __name__ == "__main__":
    unittest.main()
