"""A decision entry must name the group discussion that produced it.

The rule this enforces (group notice #8, user 2026-10-31): every direction, mechanism claim, decision
page and release must first have (a) a member's proposed variant or attack and (b) another member's
independent verification. The CEO signs; the CEO does not author the plan alone.

Measured failure this prevents: v0.33.0–v0.33.4 and DECISIONS #49–#53 were all authored, run and
signed by one agent, with the group only informed afterwards. Every number was right and the process
was still wrong.

The gate is deliberately mechanical: pages numbered above the cutoff must carry a
`**Discussed:**` line naming at least two distinct members and at least one evidence path. A page that
cannot name its discussion is not a decision, it is one agent writing code in public.

Cutoff: #53 is the entry that records this rule. Entries up to and including #53 predate the gate and
are marked as pre-rule in the historical note below rather than retro-written.
"""
import json
import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DECISIONS = os.path.join(ROOT, "docs", "decisions")
CUTOFF = 54          # #54 records the rule; enforcement starts at #55
MEMBERS = ("Glm仔", "Mini仔", "kimi 仔", "Jev仔", "Hermes仔")
DISCUSSED_RE = re.compile(r"\*\*Discussed:\*\*(.+)")
PRERULE = ("DECISIONS #49–#53 were signed before this gate existed and are recorded as pre-rule; "
           "their evidence is the verify reports in docs/memory-arch/.")


def discussion_problems(body):
    """Return the reasons `body` fails the group-authority gate. Never returns [] for a missing line."""
    match = DISCUSSED_RE.search(body)
    if not match:
        return ["no '**Discussed:**' line"]
    line = match.group(1)
    problems = []
    named = {member for member in MEMBERS if member in line}
    if len(named) < 2:
        problems.append(f"names {len(named)} distinct member(s), needs 2")
    if not re.search(r"(docs/|experiments/|knowledge-graph/|VERIFY|ATTACK)", line):
        problems.append("cites no evidence path")
    return problems


def split_page(path):
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    head, _sep, rest = text.partition("\n\n")
    meta, _sep2, body = rest.partition("\n\n")
    return head, meta, body


class GroupAuthorityGateTests(unittest.TestCase):
    def setUp(self):
        with open(os.path.join(DECISIONS, "manifest.json"), encoding="utf-8") as fh:
            self.manifest = json.load(fh)
        self.pages = {page["n"]: page for page in self.manifest["pages"]}

    def test_rule_is_recorded_on_the_cutoff_page(self):
        self.assertIn(CUTOFF, self.pages, "the cutoff entry is missing")
        _head, _meta, body = split_page(os.path.join(DECISIONS, self.pages[CUTOFF]["slug"]))
        self.assertIn("CEO", body)
        self.assertIn("sign", body.lower())
        self.assertIn("**Discussed:**", body, "the rule page should itself show the required line")

    def test_gate_function_rejects_what_it_should(self):
        cases = {
            "no line": "a decision with no discussion",
            "one name": "**Discussed:** Glm仔 — experiments/x.md",
            "names but no path": "**Discussed:** Glm仔 and Mini仔 agreed",
            "valid": "**Discussed:** Glm仔 — experiments/a/PREREGISTRATION.md; "
                     "Mini仔 — experiments/a/result.json",
        }
        self.assertEqual(len(discussion_problems(cases["no line"])), 1)
        self.assertEqual(len(discussion_problems(cases["one name"])), 1)
        self.assertEqual(discussion_problems(cases["names but no path"]), ["cites no evidence path"])
        self.assertEqual(discussion_problems(cases["valid"]), [])

    def test_every_later_page_names_its_discussion(self):
        for number in sorted(n for n in self.pages if n > CUTOFF):
            _head, _meta, body = split_page(os.path.join(DECISIONS, self.pages[number]["slug"]))
            problems = discussion_problems(body)
            self.assertEqual(
                problems, [],
                f"#{number}: group-authority gate failed ({'; '.join(problems)}). A decision page "
                f"must name the members who proposed and independently verified it.")

    def test_historical_entries_are_marked_not_rewritten(self):
        """The pre-rule entries stay as published; the gate does not require them to be revised."""
        for number in range(49, CUTOFF + 1):
            _head, _meta, body = split_page(os.path.join(DECISIONS, self.pages[number]["slug"]))
            self.assertIn("*Signed", body, f"#{number} lost its signature block")


if __name__ == "__main__":
    unittest.main()
