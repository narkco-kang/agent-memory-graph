"""Adoption may not keep evidence that cannot be observed.

The defect (fixed in v0.38.4): `_keep_evidence_object` called `validate_evidence`, which
checks shape only. An object `{"locator": "url:https://…", "content_sha256": "bbbb…"}`
— digest invented by hand — passed that check, was kept as first-class evidence, the
node's `legacy_evidence` stayed empty, and the node stopped being counted
`done-no-evidence`.

Meanwhile `amg verify-evidence` calls the same item `unverifiable` and prints
"no bytes observed; not a pass". So adoption claimed to be stricter than the verifier
it feeds — the same shape as DECISIONS #58 (`check` read as a truth check): a shape
check standing in for a proof.

The rule this file pins: **only `unverifiable` objects become legacy text.** That status
means there are no bytes to observe at all — `cmd:` and `url:`, and nothing else. Every
other non-ok status (`missing`, `mismatch`, `not_a_file`, `outside_root`, `unreadable`) is
a FINDING about evidence that exists or once existed, and stays in `evidence` so
`amg verify-evidence` can keep reporting *why* it is not ok.

That second sentence is the fix to my own first fix. I keyed on `status != "ok"` and
demoted all of them; Glm attacked it with a deleted file and a directory, both of which
became indistinguishable from "there was never anything to check here" — the ledger kept a
count and dropped the reason. Erasing the reason is exactly what DECISIONS #58 forbids.

So the tests point in both directions, because either one alone invites a wrong "fix":

* keeping `cmd:`/`url:` objects → the first test fails (the original defect)
* demoting every non-ok object → the mismatch test fails (my over-correction)
* dropping *everything* → the surviving-`path:` test fails
"""
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "src"))

CLI = [sys.executable, "-m", "amg.cli"]
FORGED = "b" * 64


def env():
    e = dict(os.environ)
    e["PYTHONPATH"] = os.path.join(ROOT, "src") + os.pathsep + e.get("PYTHONPATH", "")
    return e


def dir_object(locator, digest=FORGED):
    return {"locator": locator, "content_sha256": digest,
            "captured_at": "2026-11-01T10:00:00+08:00"}


def make_legacy(evidence_items, proof_bytes=b"real bytes\n"):
    """A legacy graph whose single node carries `evidence_items` as OBJECTS."""
    base = tempfile.mkdtemp(prefix="amg-adopt-ev-")
    src = os.path.join(base, "legacy")
    os.makedirs(src)
    # Inside the source graph's directory: that is the base legacy locators were written
    # against, and therefore the only base against which "can this be observed" is answerable.
    proof = os.path.join(src, "proof.md")
    with open(proof, "wb") as fh:
        fh.write(proof_bytes)
    real = hashlib.sha256(proof_bytes).hexdigest()
    items = []
    for item in evidence_items:
        if item == "PATH_REAL":
            items.append(dir_object(f"path:{proof}", real))
        else:
            items.append(item)
    doc = {"schema": "group-kg/v1", "group": "t", "nodes": [{
        "id": "n1", "type": "artifact", "label": "L", "status": "done",
        "owner": "x", "source": "cmd:test", "note": "", "evidence": items,
    }], "edges": [], "changes": []}
    with open(os.path.join(src, "graph.json"), "w", encoding="utf-8") as fh:
        json.dump(doc, fh, ensure_ascii=False)
    return base, src


def adopt(src):
    out = os.path.join(os.path.dirname(src), "out")
    res = subprocess.run(CLI + ["adopt", src, out], capture_output=True, text=True,
                         env=env(), cwd=ROOT, timeout=120)
    if res.returncode != 0:
        raise AssertionError(res.stdout + res.stderr)
    with open(os.path.join(out, "graph.json"), encoding="utf-8") as fh:
        return json.load(fh), res.stdout


class UnobservableObjectsBecomeLegacyTest(unittest.TestCase):
    def test_cmd_and_url_objects_are_filed_as_legacy(self):
        """MUTATION GUARD: call validate_evidence alone (shape only) and this fails."""
        for locator in ("cmd:git log --oneline -3", "url:https://kubernetes.io/docs/"):
            with self.subTest(locator=locator):
                _base, src = make_legacy([dir_object(locator)])
                doc, out = adopt(src)
                node = doc["nodes"][0]
                self.assertEqual(node["evidence"], [],
                                 f"{locator} carries no observed bytes; it must not survive as "
                                 f"evidence. adoption said:\n{out}")
                self.assertEqual(len(node["legacy_evidence"]), 1,
                                 "it must be preserved verbatim as legacy, not dropped")
                self.assertIn(locator, node["legacy_evidence"][0])
                self.assertIn("rejected objects 1", out)

    def test_a_node_kept_this_way_is_counted_as_debt(self):
        """A kept-but-unverifiable object used to make the node look evidence-backed."""
        _base, src = make_legacy([dir_object("url:https://example.test/x")])
        _doc, out = adopt(src)
        self.assertIn("done-no-evidence 1/1", out,
                      "the node has no observed evidence, so it is debt:\n" + out)

    def test_a_verifiable_path_object_still_survives(self):
        """MUTATION GUARD: drop every object and this fails — over-correction is also wrong."""
        _base, src = make_legacy(["PATH_REAL"])
        doc, out = adopt(src)
        node = doc["nodes"][0]
        self.assertEqual(len(node["evidence"]), 1,
                         "a path: object whose digest matches must survive intact:\n" + out)
        self.assertEqual(node["legacy_evidence"], [])
        self.assertIn("kept objects 1", out)

    def test_a_path_object_whose_digest_does_not_match_stays_in_evidence(self):
        """`mismatch` is a finding about real bytes, so it stays where `audit` can report it.

        The first version of this fix demoted every status that was not `ok`. Glm attacked
        it with a directory (`not_a_file`) and a deleted file (`missing`): both became
        `legacy_evidence` strings, which keeps a count and drops the reason. `audit` could
        no longer say *which* file disappeared or that a digest disagreed.

        Only `unverifiable` — `cmd:` / `url:`, where there are no bytes to observe at all —
        becomes legacy. `mismatch` stays in `evidence`, and `amg verify-evidence` reports
        the disagreement on every run.
        """
        _base, src = make_legacy(["PATH_FAKE"])
        doc_path = os.path.join(src, "graph.json")
        with open(doc_path, encoding="utf-8") as fh:
            doc = json.load(fh)
        proof = os.path.join(src, "proof.md")
        doc["nodes"][0]["evidence"] = [dir_object(f"path:{proof}", "c" * 64)]
        with open(doc_path, "w", encoding="utf-8") as fh:
            json.dump(doc, fh, ensure_ascii=False)
        out_doc, out = adopt(src)
        node = out_doc["nodes"][0]
        self.assertEqual(len(node["evidence"]), 1,
                         "a mismatched digest is a finding about observable bytes; keeping it "
                         "lets verify-evidence name the disagreement every run:\n" + out)
        self.assertEqual(node["legacy_evidence"], [],
                         "`mismatch` must not be filed as unverifiable text")

    def test_the_two_outcomes_are_counted_separately(self):
        """kept / rejected must be separate numbers; one bucket hides the distinction."""
        _base, src = make_legacy([dir_object("cmd:git status"), "PATH_REAL"])
        _doc, out = adopt(src)
        self.assertIn("kept objects 1", out)
        self.assertIn("rejected objects 1", out)


if __name__ == "__main__":
    unittest.main()
