"""A performance table must name the run that produced it (DECISIONS #46).

The failure this prevents, measured: v0.32.3 published a nine-cell tail-latency table built
from one CI run without naming the run. The independent verifier read the job logs and found
not one cell reproducible on the next runs — p95 moved by 39x for the same command, because at
80 samples p95 sits between the 76th and 77th value.

Pre-registered criteria:
1. the table under "The tail on three operating systems" exists, and every data row names a
   run id (10+ digits) and a job id;
2. no cell of that table is a bare number without a run it belongs to;
3. the section still says what was *not* measured, so provenance cannot quietly become
   completeness.
"""
import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOC = os.path.join(ROOT, "docs", "CONCURRENCY.md")
SECTION = "The tail on three operating systems"
RUN_ID_RE = re.compile(r"\b\d{9,}\b")          # GitHub Actions run / job ids
NOT_MEASURED = ("not measured", "not measured at all", "Not measured")


class TailTableProvenanceTests(unittest.TestCase):
    def setUp(self):
        with open(DOC, encoding="utf-8") as fh:
            text = fh.read()
        self.assertIn(SECTION, text, "the tail section is gone; restore or rename it here too")
        start = text.index(SECTION)
        # the section ends at the next level-2 heading
        rest = text[start:]
        end = rest.find("\n## ", 1)
        self.section = rest if end < 0 else rest[:end]

    def data_rows(self):
        rows = []
        for line in self.section.splitlines():
            line = line.strip()
            if not line.startswith("|"):
                continue
            cells = [c.strip() for c in line.strip("|").split("|")]
            if not cells or set("".join(cells)) <= set("-: "):      # separator row
                continue
            if cells[0].lower().startswith("run"):                  # header row
                continue
            rows.append(cells)
        return rows

    def test_every_row_names_a_run_and_a_job(self):
        rows = self.data_rows()
        self.assertGreaterEqual(len(rows), 3, "expected at least three measured rows")
        for cells in rows:
            joined = " | ".join(cells)
            ids = RUN_ID_RE.findall(joined)
            self.assertGreaterEqual(len(ids), 2,
                                    f"row has no run id + job id: {joined[:90]}")
            self.assertIn("(", joined, f"row does not name the job it came from: {joined[:90]}")

    def test_the_section_still_states_what_is_not_measured(self):
        lowered = self.section.lower()
        self.assertTrue(any(marker.lower() in lowered for marker in NOT_MEASURED),
                        "the section must keep saying what was not measured (Windows at 10k)")


if __name__ == "__main__":
    unittest.main()
