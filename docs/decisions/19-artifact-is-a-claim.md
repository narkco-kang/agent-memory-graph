# Decision #19

[← decision log](../DECISIONS.md) · status: active · *Signed 2026-10-30, after v0.7.1.*

**The artifact is a claim: build it, inspect it, and run the tests inside it.**
    Every check until v0.7.1 used `pip install -e .` against a checkout, so the
    published sdist had never been executed. Built and unpacked, it exposed the
    problem: `src/` and `tests/` shipped without `docs/`, `tools/` or
    `experiments/`, so its own suite gave 17 errors and 4 failures, all
    file-not-found. The wheel was complete, which is why installing the artifact
    (added as a criterion in v0.7.0) did not catch it — **an install check proves
    the code imports, not that the artifact is complete.** From v0.7.1: `MANIFEST.in`
    ships what the tests read, `tools/check_dist.py` inspects both artifacts with
    expectations derived from the working tree, and the CI `package` job installs
    the wheel and runs the sdist's shipped suite. Same rule as #18, applied one
    level out: a check that cannot name what it covered is not a check.
    *Signed 2026-10-30, after v0.7.1.*
