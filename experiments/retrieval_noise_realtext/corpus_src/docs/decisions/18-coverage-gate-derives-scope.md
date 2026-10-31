# Decision #18

[← decision log](../DECISIONS.md) · status: active · *Signed 2026-10-30.*

**A coverage gate must derive its own scope; a hand-written list is a claim about
    the past.** From v0.3.0 the documentation↔code gate ran on a hand-written list of
    files (CI: two; release checklists: six or seven). Documents kept being added and
    the list did not, so every release was greener about a smaller share of the docs
    than its checklist implied — the checklists said "six documents" while `docs/`
    held eight. The gate now scans `README.md` plus every `docs/*.md`, a test asserts
    the default covers every document, and the success line names the files it
    checked. The same reasoning produced two companions: `docs/README.md` must link
    every document (tested), and every CLI command must appear in `docs/API.md`
    (tested) — a command can otherwise exist and be documented nowhere.
    *Signed 2026-10-30.*
