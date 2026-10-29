#!/usr/bin/env bash
# End-to-end demo on a throwaway graph. Safe to run repeatedly.
set -euo pipefail
DIR="$(mktemp -d)/mem"
REPO="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO"
SHA="$(python3 -c 'import hashlib;print(hashlib.sha256(open("README.md","rb").read()).hexdigest())')"
export PYTHONPATH="$REPO/src"

python3 -m amg.cli init   "$DIR" --group demo --goal "demonstrate amg"
python3 -m amg.cli add    "$DIR" --id task.a --type task --label "write parser" --source "standup 2026-10-29"
python3 -m amg.cli status "$DIR" task.a in_progress --note "started"
python3 -m amg.cli add    "$DIR" --id decision.p --type decision --label "parser is done" --source "review" --status done \
  --evidence "path:README.md|$SHA|2026-10-29T18:00:00+08:00|2"
python3 -m amg.cli search "$DIR" "parser" --json
python3 -m amg.cli check  "$DIR" --strict
python3 -m amg.cli digest "$DIR" --max-bytes 4096
python3 -m amg.cli audit  "$DIR"
echo "graph at: $DIR"
