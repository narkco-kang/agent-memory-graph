# Decision #3

[← decision log](../DECISIONS.md) · status: amended (#31) · signed by the log preamble (*signed 2026-10-29*), this entry has no per-entry signature line

**Anchor filter degrades, never hides.** Only 22–36% of lexical hits carry
   evidence. Default returns unanchored hits with `anchor_state: "none"`;
   `--strict` is the only filter. Ranking puts anchored hits first.
