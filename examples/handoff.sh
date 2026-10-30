#!/usr/bin/env bash
# End-to-end demo of the handoff card: write, read, replace, audit. Safe to re-run.
set -euo pipefail
DIR="$(mktemp -d)/mem"
REPO="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO"
export PYTHONPATH="$REPO/src"
amg() { python3 -m amg.cli "$@"; }

amg init "$DIR" --group demo --goal "show the handoff card"

printf '%s\n' \
  '## Where we are' \
  '- did: adopted the legacy graph, pin at pin.json' \
  '- next: run the burst, then decide on fairness' \
  '- blocked: nothing' \
  '- pointers: docs/REAL-WORLD.md' \
  | amg handoff "$DIR" --by kimi --owner mini --note -

echo "--- the card a new session would read ---"
amg handoff "$DIR"

echo "--- writing a second card supersedes the first, it does not delete it ---"
amg handoff "$DIR" --by mini --note '## Where we are
- did: ran the burst on the real graph
- next: write the decision record
- blocked: nothing'

amg check "$DIR" --strict
amg audit "$DIR"

echo "--- a card over 4 KB is refused before anything is written ---"
if amg handoff "$DIR" --by mini --note "$(python3 -c 'print("x"*4097)')" 2>/dev/null; then
  echo "ERROR: oversized card was accepted"; exit 1
else
  echo "✓ oversized card refused (exit 2)"
fi

echo "graph at: $DIR"
