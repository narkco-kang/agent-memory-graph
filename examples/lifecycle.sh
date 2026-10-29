#!/usr/bin/env bash
# Full lifecycle: evidence gate rejection, supersede, expiry, audit.
# Everything here is asserted by exit code, so it doubles as a smoke test.
set -uo pipefail
REPO="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO"
DIR="$(mktemp -d)/mem"
export PYTHONPATH="$REPO/src"
SHA="$(python3 -c 'import hashlib;print(hashlib.sha256(open("README.md","rb").read()).hexdigest())')"
EVID="path:README.md|$SHA|2026-10-30T09:00:00+08:00|1"

step() { printf '\n=== %s\n' "$1"; }

python3 -m amg.cli init "$DIR" --group lifecycle --goal "demonstrate the rules"

step "a conclusion cannot be recorded as done without evidence (IR-4)"
python3 -m amg.cli add "$DIR" --id decision.limit --type decision --label "limit is 32" \
  --source "meeting 2026-10-30" --status done
echo "exit=$?  (expected 1)"

step "the same conclusion with an evidence object is accepted"
python3 -m amg.cli add "$DIR" --id decision.limit --type decision --label "limit is 32" \
  --source "meeting 2026-10-30" --status done --evidence "$EVID"
echo "exit=$?  (expected 0)"

step "a fact can carry an explicit validity window"
python3 -m amg.cli add "$DIR" --id decision.limit.v2 --type decision --label "limit is 64" \
  --source "review 2026-10-30" --status done --evidence "$EVID" \
  --valid-from 2026-10-01T00:00:00+08:00 --valid-until 2026-10-20T00:00:00+08:00
echo "exit=$?  (expected 0)"

step "supersede keeps the old node and stamps its window"
python3 -m amg.cli add "$DIR" --id decision.limit.v3 --type decision --label "limit is 64 (re-confirmed)" \
  --source "review 2026-10-25" --status done --evidence "$EVID"
python3 -m amg.cli supersede "$DIR" decision.limit.v2 decision.limit.v3 \
  --note "v3 re-confirms after the window lapsed"
echo "exit=$?  (expected 0)"
python3 -m amg.cli search "$DIR" "limit" --json | python3 -c "import json,sys;print('search results:',[(h['id'],h['status']) for h in json.load(sys.stdin)])"

step "expiry is explicit: dry-run first, then apply"
python3 -m amg.cli expire "$DIR"
python3 -m amg.cli expire "$DIR" --apply
echo "exit=$?  (expected 0)"

step "audit: what is left is honest"
python3 -m amg.cli audit "$DIR"
echo "audit exit=$?"

step "digest is bounded and pointer-only"
python3 -m amg.cli digest "$DIR" --max-bytes 2048
echo "graph kept at: $DIR"
