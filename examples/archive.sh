#!/usr/bin/env bash
# End-to-end demo of `amg archive`: dry-run, apply with proof, verify, tamper check.
# Safe to re-run: everything happens in a temporary directory.
set -euo pipefail
DIR="$(mktemp -d)/mem"
REPO="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO"
export PYTHONPATH="$REPO/src"
amg() { python3 -m amg.cli "$@"; }

# Two writes: one dated in the past, one now. `AMG_NOW` makes the clock testable,
# which is the same knob the test suite uses.
AMG_NOW="2026-08-01T10:00:00+08:00" amg init "$DIR" --group demo --goal "show the archive"
AMG_NOW="2026-08-01T10:00:00+08:00" amg add "$DIR" --id rule.a --type rule --label "old rule" \
  --source "cmd:examples/archive.sh" --status open --note "written in August" \
  --applies "any" --expires-never
AMG_NOW="2026-08-01T10:01:00+08:00" amg add "$DIR" --id task.a --type task --label "old task" \
  --source "cmd:examples/archive.sh" --status open --note "also August"

echo "--- dry-run: reports what is cold, writes nothing ---"
amg archive "$DIR"
test ! -d "$DIR/archive" || { echo "ERROR: a dry-run created $DIR/archive"; exit 1; }
echo "✓ no archive directory after the dry-run"

echo "--- apply: snapshots, moves, and proves the move ---"
amg archive "$DIR" --older-than-days 30 --apply

echo "--- moved history stays searchable, and says it is old history ---"
amg search "$DIR" "rule.a" --layer L2 --include-archive --json \
  | python3 -c 'import json,sys; hits=json.load(sys.stdin); old=[h for h in hits if h.get("archived")]; assert old, hits; print("✓ %d archived hit(s), each naming its archive file: %s" % (len(old), ", ".join(sorted({h["archive_file"] for h in old}))))' 

echo "--- the proof can be re-run later, from disk only ---"
amg archive "$DIR" --verify

echo "--- a tampered archive is caught, not trusted ---"
ARCHIVE_FILE="$(ls "$DIR"/archive/changes-*.json | head -1)"
python3 - "$ARCHIVE_FILE" <<'PY'
import json, sys
path = sys.argv[1]
with open(path, encoding="utf-8") as fh:
    head = json.load(fh)
head["changes"][0]["note"] = "quietly rewritten"
with open(path, "w", encoding="utf-8") as fh:
    json.dump(head, fh)
PY
if amg archive "$DIR" --verify; then
  echo "ERROR: a tampered archive passed verification"; exit 1
else
  echo "✓ tampered archive rejected (exit 1)"
fi

echo "graph at: $DIR"
