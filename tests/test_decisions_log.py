"""The decision log is an index plus one page per decision (DECISIONS #43).

Why this file exists: the log used to be one 24 KiB file, which held 34 decisions and then
had 7 B left, so eight versions of decisions were never written down. It is now an index and
43 pages, which makes "did the cut lose anything" a question a machine can answer.

Pre-registered criteria:

1. every number 1..N has exactly one page, and the manifest count equals the count on disk —
   a split script that cuts zero entries and exits 0 is the failure mode this catches
   (`pitfall.split-script-must-assert-entry-count`);
2. no decision text moved or vanished: each page body hashes to the value recorded when it was
   cut from the single file;
3. the index links every page and every link resolves on disk;
4. entries 1–8 carry no invented signature: they say they are signed by the log preamble,
   which is the only record they have (DECISIONS #42);
5. every page is inside the documentation gates — a page in a subdirectory must not escape the
   size budget or the symbol gate (DECISIONS #40, #41).
"""
import hashlib
import json
import os
import re
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DECISIONS_DIR = os.path.join(ROOT, "docs", "decisions")
INDEX = os.path.join(ROOT, "docs", "DECISIONS.md")
MANIFEST = os.path.join(DECISIONS_DIR, "manifest.json")
ROW_RE = re.compile(r"^\|\s*\[(\d+)\]\((decisions/[^)]+)\)\s*\|(.+?)\|(.+?)\|(.+?)\|$")


def load_manifest():
    with open(MANIFEST, encoding="utf-8") as fh:
        return json.load(fh)


def split_page(path):
    """Return (header line, meta line, body) for one decision page."""
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    head, _sep, rest = text.partition("\n\n")
    meta, _sep2, body = rest.partition("\n\n")
    return head, meta, body


class DecisionPageTests(unittest.TestCase):
    def setUp(self):
        self.manifest = load_manifest()
        self.pages = self.manifest["pages"]

    def test_every_number_has_exactly_one_page(self):
        numbers = [p["n"] for p in self.pages]
        self.assertEqual(sorted(numbers), list(range(1, len(numbers) + 1)),
                         "page numbers are not 1..N without gaps or repeats")
        self.assertEqual(self.manifest["count"], len(self.pages))
        on_disk = sorted(name for name in os.listdir(DECISIONS_DIR)
                         if re.match(r"^\d{2}-.+\.md$", name))
        # Two-digit filenames stop at 99; the assertion is the guard, not a wish.
        self.assertEqual(len(on_disk), len(self.pages), "pages on disk != manifest rows")

    def test_no_decision_text_was_lost(self):
        for page in self.pages:
            head, meta, body = split_page(os.path.join(DECISIONS_DIR, page["slug"]))
            self.assertEqual(head, f"# Decision #{page['n']}", page["slug"])
            self.assertTrue(meta.startswith("["), f"{page['slug']}: no index link")
            digest = hashlib.sha256(body.encode()).hexdigest()
            self.assertEqual(digest, page["body_sha256"],
                             f"{page['slug']}: body changed since the cut")
            self.assertGreater(page["body_bytes"], 100, f"{page['slug']}: empty-looking page")

    def test_index_links_every_page_and_every_link_resolves(self):
        with open(INDEX, encoding="utf-8") as fh:
            index = fh.read()
        rows = {}
        for line in index.splitlines():
            m = ROW_RE.match(line.strip())
            if m:
                rows[int(m.group(1))] = m.group(2)
        self.assertEqual(sorted(rows), [p["n"] for p in self.pages],
                         "index rows and pages disagree")
        for number, link in rows.items():
            self.assertTrue(os.path.isfile(os.path.join(ROOT, "docs", link)),
                            f"index row {number} points at a missing page: {link}")

    def test_status_column_is_a_known_value(self):
        with open(INDEX, encoding="utf-8") as fh:
            index = fh.read()
        seen = set()
        for line in index.splitlines():
            m = ROW_RE.match(line.strip())
            if m:
                seen.add(m.group(4).strip())
        allowed = {"active", "superseded", "archived"}
        for status in seen:
            self.assertTrue(status in allowed or status.startswith("amended (#"),
                            f"unknown status in the index: {status!r}")

    def test_early_entries_claim_the_preamble_not_a_signature(self):
        for page in self.pages:
            _head, meta, body = split_page(os.path.join(DECISIONS_DIR, page["slug"]))
            if page["n"] <= 8:
                self.assertNotIn("*Signed", body,
                                 f"{page['slug']}: entries #1-#8 have no per-entry signature")
                self.assertIn("preamble", meta,
                              f"{page['slug']}: must say where its signature comes from")
            else:
                self.assertIn("*Signed", body, f"{page['slug']}: signature line missing")


class DecisionPageGateCoverageTests(unittest.TestCase):
    def test_every_page_is_inside_both_gates(self):
        sys.path.insert(0, os.path.join(ROOT, "tools"))
        try:
            import check_doc_sizes
            import check_doc_symbols
        finally:
            sys.path.pop(0)
        sizes = {p.replace(os.sep, "/") for p in check_doc_sizes.default_targets()}
        symbols = {p.replace(os.sep, "/") for p in check_doc_symbols.default_targets()}
        pages = {"docs/decisions/" + name for name in os.listdir(DECISIONS_DIR)
                 if name.endswith(".md")}
        self.assertTrue(pages)
        self.assertEqual(pages - sizes, set(), "pages escape the size budget")
        self.assertEqual(pages - symbols, set(), "pages escape the symbol gate")

    def test_index_status_matches_manifest(self):
        """The index and the manifest are two copies of one fact, and can drift separately.

        Found by the independent verifier on v0.32.3: the amended-claim test reads the
        *manifest*, so editing only the index row — the copy a human reads — passed every
        test. DECISIONS #22 says one source of truth; this asserts the index agrees with it.
        """
        man = load_manifest()
        by_number = {p["n"]: p for p in man["pages"]}
        with open(INDEX, encoding="utf-8") as fh:
            index = fh.read()
        rows = 0
        for line in index.splitlines():
            m = ROW_RE.match(line.strip())
            if not m:
                continue
            rows += 1
            number = int(m.group(1))
            self.assertIn(number, by_number, f"index row #{number} has no page record")
            self.assertEqual(m.group(4).strip(), by_number[number]["status"],
                             f"#{number}: the index says one status, the manifest another")
            self.assertEqual(m.group(2), "decisions/" + by_number[number]["slug"],
                             f"#{number}: index link and manifest slug disagree")
        self.assertEqual(rows, len(man["pages"]), "index rows != pages")


class ReferenceResolutionTests(unittest.TestCase):
    """`DECISIONS #N` must land on decision N, not on the index (v0.32.2).

    The index says references resolve by number; that promise is only real if a link
    reaches the page. Before this test, `docs/API.md` pointed at the index and a reader
    needed a second click to reach the decision (reported by the independent verifier).
    """

    REF_RE = re.compile(r"\[DECISIONS #(\d+)\]\(([^)]+)\)")
    BARE_RE = re.compile(r"(?<!\]\()DECISIONS(?:\.md)? #\d+")

    def shipped_docs(self):
        files = ["README.md"]
        for current, _dirs, names in os.walk(os.path.join(ROOT, "docs")):
            for name in sorted(names):
                if not name.endswith(".md"):
                    continue
                rel = os.path.relpath(os.path.join(current, name), ROOT).replace(os.sep, "/")
                if rel.startswith("docs/decisions/") or rel == "docs/DECISIONS.md":
                    continue
                files.append(rel)
        return files

    def test_every_reference_link_reaches_its_own_page(self):
        seen = 0
        for rel in self.shipped_docs():
            with open(os.path.join(ROOT, rel), encoding="utf-8") as fh:
                text = fh.read()
            for number, target in self.REF_RE.findall(text):
                seen += 1
                resolved = os.path.normpath(os.path.join(os.path.dirname(rel), target))
                self.assertTrue(os.path.isfile(os.path.join(ROOT, resolved)),
                                f"{rel}: link to DECISIONS #{number} does not resolve: {target}")
                self.assertRegex(os.path.basename(resolved), rf"^{int(number):02d}-",
                                 f"{rel}: link labelled DECISIONS #{number} points at {target}")
        self.assertGreater(seen, 5, "expected the shipped docs to reference the log")

    def test_no_bare_reference_is_left_behind(self):
        leftovers = []
        for rel in self.shipped_docs():
            with open(os.path.join(ROOT, rel), encoding="utf-8") as fh:
                for line_no, line in enumerate(fh, 1):
                    if self.BARE_RE.search(self.REF_RE.sub("", line)):
                        leftovers.append(f"{rel}:{line_no}: {line.strip()[:80]}")
        self.assertEqual(leftovers, [], "bare DECISIONS #N references (make them page links)")


class StatusColumnTests(unittest.TestCase):
    """The two machine-checks the index needs because its column is hand-written.

    The first hand-written version marked #17 `amended (#24)` although #24 never mentions
    it, and the preamble's cost count said 8 where a stem match finds 11 (the pattern it
    used required a word boundary after `cost`, so `costs` did not match). Both were found
    by an attack, not by a test — hence these.
    """

    # Stems, not a prefix match: "payload" is not a cost, and a `pay\w*` pattern
    # counted it once. The index states this exact rule.
    COST_RE = re.compile(r"\bcost\w*|\bprice\w*|\bpays?\b|\bpaid\b|\bpaying\b|\bpayments?\b",
                         re.I)
    COUNT_RE = re.compile(r"hits \*\*(\d+) of the 34\*\*")

    def test_every_amended_claim_is_made_by_the_amending_page(self):
        man = load_manifest()
        pages = {p["n"]: p for p in man["pages"]}
        checked = 0
        for page in man["pages"]:
            m = re.match(r"^amended \(#(\d+)\)$", page["status"])
            if not m:
                continue
            checked += 1
            amender = int(m.group(1))
            self.assertIn(amender, pages, f"#{page['n']} is amended by a page that does not exist")
            _head, meta, _body = split_page(os.path.join(DECISIONS_DIR, pages[amender]["slug"]))
            self.assertIn(f"#{page['n']}", meta,
                          f"#{page['n']} claims it is amended by #{amender}, but #{amender} does "
                          f"not say so in its header")
        self.assertGreater(checked, 0, "expected at least one amended entry")

    def test_preamble_cost_count_matches_a_stem_match(self):
        with open(INDEX, encoding="utf-8") as fh:
            index = fh.read()
        m = self.COUNT_RE.search(index)
        self.assertIsNotNone(m, "the index must state how many entries price themselves")
        stated = int(m.group(1))
        hits = 0
        for page in load_manifest()["pages"]:
            if page["n"] > 34:
                continue
            _head, _meta, body = split_page(os.path.join(DECISIONS_DIR, page["slug"]))
            if self.COST_RE.search(body):
                hits += 1
        self.assertEqual(stated, hits, "the preamble's cost count drifted from measurement")


if __name__ == "__main__":
    unittest.main()
