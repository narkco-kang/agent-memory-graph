# Contributing

Thanks for looking. This project is deliberately small; the rules below keep it
honest.

## Ground rules

1. **Docs must equal code.** `tools/check_doc_symbols.py` fails if a capability
   named in `README.md` or `docs/API.md` has no corresponding symbol. If your
   change adds a command or public method, document it; if you document
   something, implement it.
2. **No unverified claims.** Anything not measured or executed goes in a
   "Not implemented" or "Not measured" section. Estimates must be labelled as
   estimates.
3. **Never fabricate evidence.** `content_sha256` must be the hash of the cited
   artifact. If you cannot hash it, do not add the evidence object.
4. **Tests first for fixes.** A bug fix arrives with a test that fails before it
   and passes after; include the failing output in the PR description.
5. **No force-push to `main`.** Open a PR. CI must be green.

## Running the checks locally

```bash
pip install -e .
python -m unittest discover -s tests -v
python tools/check_doc_symbols.py README.md docs/API.md
bash examples/quickstart.sh
python benchmarks/bench.py          # optional, a few minutes
```

## Adding a protocol rule

Protocol changes need three things in one PR: the rule in `docs/DECISIONS.md`
with its evidence, the enforcement point (a single place, not scattered
`if`s), and a test that proves the rule rejects what it should reject.

## Reporting a defect

Open an issue with: the command you ran, the observed output, the expected
output, and (if it is a data problem) a minimal graph file. Do not include
credentials or personal data — the graph format is plain JSON and easy to
redact.
