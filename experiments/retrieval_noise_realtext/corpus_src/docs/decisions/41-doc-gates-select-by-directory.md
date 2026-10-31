# Decision #41

[← decision log](../DECISIONS.md) · status: active

**Select documents by directory, not by file suffix.** Measured on v0.30.0: `docs/n/A.markdown`, `docs/n/B.txt` and `docs/n/NOEXT` at 30,000 B each
all passed the size gate, and a 30 KB `.markdown` page describing a subcommand that has
never existed passed the symbol gate with exit 0. (Writing that command verbatim in this
page fails the gate itself — which is how the sentence was caught, and why it is phrased
as a description here.) The suffix was the only difference
from a page both gates would have failed, so the gate was one `mv` away from checking nothing.
Decision: scope lives in `tools/doc_scope.py` — `README.md` plus **every regular file under
`docs/`**, at any depth, whatever it is named — and both gates import it instead of each
copying the walk. In the same pass the symbol gate resolves targets against the repository
root (run from elsewhere it used to `skip (missing)` every target and exit 0) and decodes with
`errors="replace"`. Cost: a large binary asset does not belong under `docs/`, because the
budget applies to bytes regardless of content type.
*Signed 2026-10-31; `tests/test_doc_symbols.py::test_both_gates_see_the_same_files`; v0.31.0.*
