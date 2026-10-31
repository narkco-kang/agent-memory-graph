"""The realtext artifacts must say what they were measured on, and must re-derive.

The whole point of these tests is a defect that already happened: `sensitivity_window.json` was
committed at one corpus state and re-ran to different numbers (whole paragraphs r@5 0.673 -> 0.654)
because the distractor prose is taken from this repository's live `README.md` and `docs/*.md`.
Nothing failed then, because nothing checked. These tests check.
"""
import hashlib
import contextlib
import importlib.util
import io
import json
import os
import pathlib
import re
import subprocess
import sys
import tempfile
import unittest

REPO = pathlib.Path(__file__).resolve().parents[1]
ART = REPO / "experiments" / "retrieval_noise_realtext"


def corpus_files():
    paths = [REPO / "README.md"]
    paths += sorted((REPO / "docs").glob("*.md"))
    paths += sorted((REPO / "docs" / "decisions").glob("*.md"))
    return [path for path in paths if path.is_file()]


def excerpt_paragraphs():
    """The same extraction the harness does: paragraphs of six or more folded words."""
    paragraphs = []
    for path in corpus_files():
        for block in re.split(r"\n\s*\n", path.read_text(encoding="utf-8")):
            words = " ".join(block.split()).split()
            if len(words) >= 6:
                paragraphs.append(words)
    return paragraphs


def load(name):
    with open(ART / name, encoding="utf-8") as fh:
        return json.load(fh)


class CorpusPinTest(unittest.TestCase):
    def test_snapshot_describes_the_pinned_corpus(self):
        """The numbers belong to the pin. Editing docs must not move a published measurement.

        Drift between the shipped prose and the pin is reported by
        `run_realtext.py --check-corpus` (exit 1) rather than by a failing test: the corpus is the
        input, and only `--rebuild-corpus` may change it -- together with every quoted number.
        """
        import hashlib

        snapshot = load("corpus_snapshot.json")
        with open(ART / "corpus_pin.json", encoding="utf-8") as fh:
            pin = json.load(fh)
        paragraphs = [block.split() for block in pin["text"].split("\n\n") if block.strip()]
        text = "\n\n".join(" ".join(words) for words in paragraphs).encode("utf-8")
        self.assertEqual(pin["paragraphs"], len(paragraphs))
        self.assertEqual(pin["paragraphs"], snapshot["paragraphs"],
                         "the pin and the run disagree about the corpus")
        self.assertEqual(pin["extracted_sha256"], snapshot["extracted_sha256"])
        self.assertEqual(snapshot["extracted_sha256"], hashlib.sha256(text).hexdigest(),
                         "the pin text does not hash to the digest the run recorded")
        self.assertEqual(pin["files"], snapshot["files"])

    def test_rerun_is_byte_identical(self):
        """Same corpus, same seed, same bytes -- otherwise the artifacts are not evidence."""
        with tempfile.TemporaryDirectory() as tmp:
            env = dict(os.environ, REALTEXT_OUT_DIR=tmp)
            completed = subprocess.run([sys.executable, str(ART / "run_realtext.py")],
                                       env=env, capture_output=True, text=True, timeout=600)
            self.assertEqual(completed.returncode, 0, completed.stderr[-2000:])
            for name in ("result.json", "ledger.json", "corpus_snapshot.json"):
                with open(os.path.join(tmp, name), "rb") as fh:
                    rerun = fh.read()
                with open(ART / name, "rb") as fh:
                    committed = fh.read()
                self.assertEqual(committed, rerun,
                                 f"{name} does not reproduce; the committed artifact is stale")


    def test_corpus_digest_ignores_line_endings(self):
        """A Windows checkout must not report stale corpus for the same text (CI windows-latest)."""
        sys.path.insert(0, str(ART))
        import run_realtext as rt

        lf = b"first paragraph here\nsecond paragraph here\n"
        crlf = lf.replace(b"\n", b"\r\n")
        self.assertEqual(rt._normalised_sha256(lf), rt._normalised_sha256(crlf),
                         "the digest must be a property of the text, not of the checkout")
        self.assertNotEqual(hashlib.sha256(lf).hexdigest(), hashlib.sha256(crlf).hexdigest(),
                            "this test is vacuous unless raw hashing actually differs")


class LedgerTest(unittest.TestCase):
    def test_ledger_is_self_consistent_with_the_scores(self):
        result = load("result.json")
        ledger = load("ledger.json")
        rows = ledger["rows"]
        self.assertEqual(ledger["n"], len(rows))
        self.assertEqual(ledger["rank_base"], 1)
        self.assertEqual(set(ledger["metric"]),
                         {"fractional_r5", "hit_or_miss", "best_gold_rank"})
        arm = result["arms"]["realtext"]
        self.assertEqual(ledger["fractional_r5"], arm["recall@5"])
        self.assertAlmostEqual(ledger["hit_or_miss"],
                               round(sum(1 for row in rows if row["recall@5"] > 0) / len(rows), 4))
        self.assertAlmostEqual(ledger["ceiling"],
                               round((len(rows) - len(ledger["out_of_reach"])) / len(rows), 4))
        self.assertEqual(sorted(ledger["out_of_reach"]),
                         sorted(row["id"] for row in rows if not row["gold_reachable_in_top_k"]))
        for row in rows:
            if row["gold_reachable_in_top_k"]:
                self.assertIsInstance(row["best_gold_rank"], int)
                self.assertGreaterEqual(row["best_gold_rank"], 1)
                self.assertLessEqual(row["best_gold_rank"], ledger["top_k"])
            else:
                self.assertIsNone(row["best_gold_rank"])

    def test_both_metric_conventions_are_published(self):
        """0.692 fractional and 0.731 hit-or-miss are the same run; publishing one hides a dispute."""
        ledger = load("ledger.json")
        verdicts = load("result.json")["verdicts"]
        self.assertEqual(ledger["fractional_r5"], verdicts["realtext_r5"])
        self.assertEqual(ledger["hit_or_miss"], verdicts["realtext_hit_or_miss@5"])
        self.assertNotEqual(ledger["fractional_r5"], ledger["hit_or_miss"])


class PairedFalsifierTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location("paired_test", ART / "paired_test.py")
        cls.paired = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.paired)

    def _ledger(self, path, ids, hits):
        rows = [{"id": qid, "recall@5": 1.0 if hit else 0.0} for qid, hit in zip(ids, hits)]
        payload = {"schema": "realtext-ledger/1", "rank_base": 1, "n": len(rows), "rows": rows}
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(payload, fh)
        return path

    def test_zero_regression_passes_and_reports_integer_pairs(self):
        with tempfile.TemporaryDirectory() as tmp:
            ids = ["q1", "q2", "q3", "q4"]
            base = self._ledger(os.path.join(tmp, "base.json"), ids, [0, 1, 0, 1])
            cand = self._ledger(os.path.join(tmp, "cand.json"), ids, [1, 1, 0, 1])
            code = self.paired.main([base, cand, "--json"])
            self.assertEqual(code, 0)
            baseline, _ = self.paired.load_rows(base)
            candidate, _ = self.paired.load_rows(cand)
            diff = self.paired.compare(baseline, candidate)
            self.assertEqual((diff["fixed_count"], diff["broke_count"]), (1, 0))
            self.assertEqual(diff["verdict"], "PASS_NO_REGRESSION")

    def test_a_single_regression_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            ids = ["q1", "q2", "q3"]
            base = self._ledger(os.path.join(tmp, "base.json"), ids, [1, 1, 1])
            cand = self._ledger(os.path.join(tmp, "cand.json"), ids, [1, 0, 1])
            baseline, _ = self.paired.load_rows(base)
            candidate, _ = self.paired.load_rows(cand)
            diff = self.paired.compare(baseline, candidate)
            self.assertEqual(diff["broke"], ["q2"])
            self.assertEqual(diff["verdict"], "FAIL_REGRESSION")

    def test_a_single_fix_is_never_significant(self):
        """The structural fact that shapes the design: 1 fixed / 0 broke is p = 1.0 at n=26."""
        self.assertEqual(self.paired.exact_mcnemar_p(1, 0), 1.0)
        self.assertEqual(self.paired.exact_mcnemar_p(6, 0), round(2 * 0.5 ** 6, 6))
        self.assertGreater(self.paired.exact_mcnemar_p(5, 0), 0.05)

    def test_length_sweep_pins_the_same_corpus(self):
        """Two artifacts, one corpus: the sweep and the pre-registered run must agree on the input."""
        main_corpus = load("result.json")["inputs"]["corpus"]
        sweep_corpus = load("sensitivity_window.json")["corpus"]
        self.assertEqual(sweep_corpus["extracted_sha256"], main_corpus["extracted_sha256"],
                         "the length sweep was measured on a different corpus; re-run it")
        self.assertEqual(sweep_corpus["files"], main_corpus["files"])


class DecouplingAcceptanceTest(unittest.TestCase):
    """The four gates agreed in the group discussion for decoupling the corpus from live docs."""

    def test_corpus_src_reproduces_the_pin_digests(self):
        """Gate 1: concatenate corpus_src in `files[]` order and match the pin, order included."""
        import hashlib

        with open(ART / "corpus_pin.json", encoding="utf-8") as fh:
            pin = json.load(fh)
        names = [entry["path"] for entry in pin["files"]]
        concat = b""
        paragraphs = []
        for name in names:
            data = (ART / "corpus_src" / name).read_bytes()
            concat += data.replace(b"\r\n", b"\n")
            paragraphs.extend(block.split()
                              for block in re.split(r"\n\s*\n", data.decode("utf-8")))
        self.assertEqual(hashlib.sha256(concat).hexdigest(), pin["source_sha256"],
                         "corpus_src and pin.text disagree; the two copies have drifted")
        text = "\n\n".join(" ".join(words) for words in paragraphs if len(words) >= 6)
        self.assertEqual(hashlib.sha256(text.encode("utf-8")).hexdigest(),
                         pin["extracted_sha256"],
                         "paragraph extraction from corpus_src does not reproduce the pin")

    def test_representativeness_is_required_not_merely_documented(self):
        """Gate 2: deleting the declaration must fail a check, not a comment."""
        result = load("result.json")
        declaration = result["representativeness"]
        for key in ("kind", "measures", "does_not_measure", "known_leak", "comparability",
                    "corpus_version"):
            self.assertIn(key, declaration)
        self.assertEqual(declaration["kind"], "same-domain regression set")
        self.assertEqual(declaration["corpus_version"], result["inputs"]["corpus"]["corpus_version"])

        def validate(payload):
            payload = dict(payload)
            decl = payload.get("representativeness")
            if not decl:
                raise ValueError("result.json without a representativeness declaration")
            missing = {"kind", "measures", "does_not_measure", "known_leak",
                       "comparability"} - set(decl)
            if missing:
                raise ValueError(f"representativeness missing {sorted(missing)}")

        validate(result)
        mutated = dict(result)
        mutated.pop("representativeness")
        with self.assertRaises(ValueError):
            validate(mutated)
        partial = dict(result)
        partial["representativeness"] = {"kind": "same-domain regression set"}
        with self.assertRaises(ValueError):
            validate(partial)

    def test_check_corpus_is_an_audit_that_never_fails(self):
        """Gate 3: drift is reported with an age and exit 0; a red gate would always be red."""
        spec = importlib.util.spec_from_file_location("run_realtext", ART / "run_realtext.py")
        module = importlib.util.module_from_spec(spec)
        sys.modules["run_realtext"] = module
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as tmp:
            live = pathlib.Path(tmp) / "live.md"
            live.write_text("# changed\n\nthis prose is not in the frozen corpus at all\n",
                            encoding="utf-8")
            module.live_paths = lambda: [live]
            buffer = io.StringIO()
            with contextlib.redirect_stdout(buffer):
                code = module.check_corpus([])
            output = buffer.getvalue()
        self.assertEqual(code, 0, "check-corpus must not fail a build for documentation drift")
        self.assertIn("changed", output)
        self.assertIn("day(s) old", output)

    def test_frozen_corpus_is_a_fixture_outside_the_documentation_budget(self):
        """Gate 4: corpus_src is a fixture: in the sdist, out of the docs size gate."""
        self.assertNotIn("docs", (ART / "corpus_src").relative_to(REPO).parts,
                         "the frozen corpus must not live under docs/ (that is the doc budget scope)")
        source = (REPO / "tools" / "check_dist.py").read_text(encoding="utf-8")
        self.assertIn("retrieval_noise_realtext/corpus_src/manifest.json", source,
                      "check_dist must require the frozen corpus in the sdist")
        scope_source = (REPO / "tools" / "doc_scope.py").read_text(encoding="utf-8")
        self.assertNotIn("experiments", scope_source,
                         "the documentation budget must not scan experiments/ fixtures")


if __name__ == "__main__":
    unittest.main()
