"""A corrected page must keep both its original sentence and its correction (DECISIONS #53).

The failure this prevents: #48 published "restricting coverage to content words only returns 0.615
(+0.077)" while its code filtered query tokens to the *original corpus vocabulary*. The numbers were
right; the name was wrong, and the next direction was inferred from the wrong arm. A later cleanup
could either delete the wrong sentence (losing the record) or delete the correction (restoring the
wrong inference). Both are failures here.

Checks:
1. #48 still contains the original sentence **and** a dated correction that names the vocabulary
   filter and `orig_vocab`;
2. #53 exists, says the +0.077 was not a content-word estimate, and does not weaken #49;
3. the manifest digest for #48 matches the current body (so the correction is inside the hashed text,
   not appended outside it).
"""
import hashlib
import json
import os
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DECISIONS = os.path.join(ROOT, "docs", "decisions")
ORIGINAL_48 = "Restricting\ncoverage to content words only returns N2 to 0.615"
CORRECTION_48 = "**Correction 2026-10-31, after independent verification (DECISIONS #53).**"


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def split_page(path):
    text = read(path)
    head, _sep, rest = text.partition("\n\n")
    meta, _sep2, body = rest.partition("\n\n")
    return head, meta, body


class ArmNameMatchesCodeTests(unittest.TestCase):
    def setUp(self):
        with open(os.path.join(DECISIONS, "manifest.json"), encoding="utf-8") as fh:
            self.manifest = json.load(fh)
        self.pages = {page["n"]: page for page in self.manifest["pages"]}

    def test_page_48_keeps_both_original_and_correction(self):
        _head, _meta, body = split_page(os.path.join(DECISIONS, self.pages[48]["slug"]))
        self.assertIn("content words only", body, "the original sentence was deleted, not marked")
        self.assertIn("(+0.077", body, "the original number must stay visible")
        self.assertIn(CORRECTION_48, body)
        self.assertIn("`orig_vocab`", body, "the correction must name the actual filter")
        self.assertIn("vocabulary filter", body)

    def test_manifest_digest_covers_the_correction(self):
        page = self.pages[48]
        _head, _meta, body = split_page(os.path.join(DECISIONS, page["slug"]))
        self.assertEqual(hashlib.sha256(body.encode()).hexdigest(), page["body_sha256"],
                         "the correction is outside the hashed body; the manifest was not updated")
        self.assertIn(CORRECTION_48, body)

    def test_decision_53_records_the_inference_and_keeps_49(self):
        page = self.pages[53]
        _head, _meta, body = split_page(os.path.join(DECISIONS, page["slug"]))
        self.assertIn("vocabulary filter", body)
        self.assertIn("not a part-of-speech filter", body)
        self.assertIn("+0.077", body)
        self.assertIn("#49", body, "the entry must keep #49's conclusion in view")
        self.assertIn("unchanged", body)

    def test_no_page_claims_content_word_weighting_for_that_arm(self):
        """The old sentence may stay as history; a *new* page may not repeat it as fact."""
        for number, page in self.pages.items():
            if number <= 48:
                continue
            _head, _meta, body = split_page(os.path.join(DECISIONS, page["slug"]))
            if "content words only returns N2 to 0.615" not in body:
                continue
            # Quoting the sentence to correct it is required; quoting it as fact is not.
            self.assertIn("vocabulary filter", body,
                          f"#{number} repeats the mislabelled arm without correcting it")


if __name__ == "__main__":
    unittest.main()
