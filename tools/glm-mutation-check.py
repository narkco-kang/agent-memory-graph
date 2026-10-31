#!/usr/bin/env python3
"""Mutation check for the v0.36.0 anchor-key change (owner: Glm仔, reviewer role).

Runs in a THROWAWAY git worktree so the real tree is never touched.
For each candidate rank_key ordering it runs tests/test_tie_break.py and reports
which tests go red.  The acceptance rule (Chief, 2026-10-31): under the OLD
ordering at least TWO tests must fail.

    python3 tools/glm-mutation-check.py [--repo PATH]

Exit 0 only when the acceptance rule holds.
"""
import argparse
import os
import shutil
import subprocess
import sys
import tempfile

OLD = 'return (bool(anchor_present), round(raw, 3), node_id or "")'
NEW = 'return (round(raw, 3), bool(anchor_present), node_id or "")'


def run(cmd, cwd, env_extra=None):
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    env["PYTHONPATH"] = "src"
    if env_extra:
        env.update(env_extra)
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, env=env)


def scrub_pycache(root):
    for dirpath, dirnames, _ in os.walk(root):
        for d in list(dirnames):
            if d == "__pycache__":
                shutil.rmtree(os.path.join(dirpath, d), ignore_errors=True)
                dirnames.remove(d)


def tie_break_failures(repo, ordering):
    """Point rank_key at `ordering`, run the tie-break tests, return failing test names."""
    path = os.path.join(repo, "src", "amg", "retrieval.py")
    with open(path, encoding="utf-8") as fh:
        src = fh.read()
    if NEW not in src and OLD not in src:
        return None, "rank_key return line not found"
    patched = src.replace(NEW, ordering).replace(OLD, ordering)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(patched)
    scrub_pycache(repo)
    res = run([sys.executable, "-m", "unittest", "tests.test_tie_break", "-v"], repo)
    out = res.stdout + res.stderr
    failed = sorted({line.split()[1].split("(")[0].strip()
                     for line in out.splitlines()
                     if line.startswith(("FAIL:", "ERROR:"))})
    return failed, out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    args = ap.parse_args(argv)
    src_repo = os.path.abspath(args.repo)

    head = run(["git", "rev-parse", "--short", "HEAD"], src_repo).stdout.strip()
    dirty = [l for l in run(["git", "status", "--porcelain"], src_repo).stdout.splitlines()
             if "architecture" not in l]
    print(f"repo   : {src_repo}")
    print(f"HEAD   : {head}")
    print(f"dirty  : {len(dirty)} file(s)")
    for line in dirty:
        print(f"         {line}")

    tmp = tempfile.mkdtemp(prefix="glm-mut-")
    work = os.path.join(tmp, "wt")
    try:
        add = subprocess.run(["git", "worktree", "add", "-f", "--detach", work, "HEAD"],
                             cwd=src_repo, capture_output=True, text=True)
        if add.returncode != 0:
            print("cannot create worktree:", add.stderr.strip())
            return 2
        # replay the working-tree changes (the proposed fix) into the worktree
        for rel in ("src/amg/retrieval.py", "tests/test_tie_break.py", "tests/conftest.py"):
            s = os.path.join(src_repo, rel)
            if os.path.exists(s):
                d = os.path.join(work, rel)
                os.makedirs(os.path.dirname(d), exist_ok=True)
                shutil.copy2(s, d)

        results = {}
        for label, ordering in (("NEW (proposed)", NEW), ("OLD (mutated back)", OLD)):
            failures, out = tie_break_failures(work, ordering)
            if failures is None:
                print(f"\n[{label}] {out}")
                return 2
            results[label] = failures
            print(f"\n[{label}] failing = {len(failures)}")
            for f in failures:
                print(f"    - {f}")

        old_fail = len(results["OLD (mutated back)"])
        print()
        print(f"acceptance: OLD ordering must break >= 2 tests -> {old_fail} failing "
              f"=> {'PASS' if old_fail >= 2 else 'FAIL'}")
        return 0 if old_fail >= 2 else 1
    finally:
        subprocess.run(["git", "worktree", "remove", "--force", work],
                       cwd=src_repo, capture_output=True, text=True)
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
