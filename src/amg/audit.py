"""Audit: legacy coverage, staleness, expiry, integrity. Exit 1 on conflicts."""
import datetime
import hashlib
import os

from .const import is_conclusion, not_yet_valid, parse_ts

# How long a work item may sit in `in_progress`/`blocked` before audit calls it
# stale. Default 3 days, overridable per call (`audit(..., stale_days=N)`) or by the
# `AMG_STALE_DAYS` environment variable — because the right threshold is a property
# of the team's cadence, not of the tool (DECISIONS #21).
DEFAULT_STALE_DAYS = 3
MAX_STALE_DAYS = 365


def stale_days_from_env(default: int = DEFAULT_STALE_DAYS) -> int:
    """Read AMG_STALE_DAYS. Nonsense or out-of-range values fall back to the default.

    Silent fallback is deliberate, like AMG_LOCK_TIMEOUT: a typo must not silently
    disable (0) or effectively disable (huge) the check.
    """
    raw = os.environ.get("AMG_STALE_DAYS")
    if raw is None:
        return default
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return default
    if not 0 < value <= MAX_STALE_DAYS:
        return default
    return value

# Types that register something long-lived rather than a work item. A group marked
# `in_progress` is active, not abandoned, and its `updatedAt` does not move when its
# children change — so the staleness rule, which assumes short-lived work, reported
# noise (docs/REAL-WORLD.md). Exemptions are explicit on purpose: an unknown type is
# still checked, so abandoning a new kind of work cannot become invisible by omission.
LONG_LIVED_TYPES = frozenset({"group", "env", "member", "handoff"})


def _parse(value):
    return parse_ts(value)


def expiry_eligible(node: dict) -> bool:
    """TTL auto-expiry must never process a node whose validity time is unknown.

    Expiring an adopted node would delete a fact on the strength of a timestamp
    we never had; leaving it alive is the safe direction (maintainer ruling 2026-10-29).
    Absent field = known, so only `valid_time_known: false` is refused.
    """
    return node.get("valid_time_known") is not False


def _sorted_sha(ids) -> str:
    return hashlib.sha256("\n".join(sorted(ids)).encode("utf-8")).hexdigest()


def legacy_stats(doc: dict) -> dict:
    nodes = doc.get("nodes") or []
    done_no_ev = [n["id"] for n in nodes if n.get("status") == "done" and not (n.get("evidence") or [])]
    all_no_ev = [n["id"] for n in nodes if not (n.get("evidence") or [])]
    done = [n["id"] for n in nodes if n.get("status") == "done"]
    return {
        "done": len(done),
        "nodes": len(nodes),
        "done_no_evidence": len(done_no_ev),
        "no_evidence": len(all_no_ev),
        "done_no_evidence_ratio": f"{len(done_no_ev)}/{len(done)}",
        "no_evidence_ratio": f"{len(all_no_ev)}/{len(nodes)}",
        "done_no_evidence_sha256": _sorted_sha(done_no_ev),
        "no_evidence_sha256": _sorted_sha(all_no_ev),
        "_ids": set(done_no_ev),
    }


#: Files/directories that mark the tree the team actually works in. A directory
#: holding none of them is very unlikely to be the base the legacy locators were
#: written against, and auditing against it yields a number instead of an error.
STRUCTURE_ANCHORS = ("README.md", "docs", "agent-memory-graph", "src", "tests")


def root_identity(root: str) -> dict:
    """Report a directory's PHYSICAL identity, not its path string.

    A path string cannot identify a directory: case-insensitive filesystems give one
    directory several spellings, symlinks give one directory many paths, and hard
    links give one file many names (all measured). `(st_dev, st_ino)` collapses those.
    It is reported for a reader to compare, and is deliberately NOT a rejection
    condition: anyone who can choose the root can simply choose one that passes, so
    treating this as enforcement would be a false promise (DECISIONS #56).
    """
    try:
        st = os.stat(root)
    except OSError as exc:
        return {"path": root, "dev": None, "ino": None, "error": str(exc)}
    return {"path": root, "dev": st.st_dev, "ino": st.st_ino}


def root_anchors(root: str) -> dict:
    """Which structure anchors exist under `root`; empty means the root looks wrong.

    Why this exists: the same graph audited against the graph directory and against
    the workspace reported 232 and 24 unverifiable nodes. A wrong root does not fail,
    it produces a bigger number that reads like a finding. This turns that failure
    into an explicit refusal instead of a plausible report.
    """
    found = [name for name in STRUCTURE_ANCHORS
             if os.path.exists(os.path.join(root, name))]
    return {"root": root, "found": found, "suspect": not found}


def evidence_state(node: dict, root: str) -> dict:
    """Per-node evidence standing, for READ paths: `verified` / `declared` / `missing`.

    Why this is not `anchor_state`: `anchor_state` answers "is the list non-empty",
    which a caller reads as "this result has evidence behind it". It does not mean
    that, and printing `anchor=present` next to a bare-string declaration shows the
    reader a claim dressed as a result (reported by the CEO on the live view).

    The three states say what can actually be observed:

    * `verified` — at least one locator is a proper object whose file resolves and
      whose declared digest matches the bytes. This is the only passing state.
    * `declared` — locators exist but none could be verified, and at least one of them
      points at something that exists (or is prose/`cmd:`/`url:`). Something was
      recorded; nothing was checked.
    * `missing` — locators exist but every path-shaped one resolves nowhere. The
      pointer itself is dead.

    A node with no evidence at all is `absent`.
    """
    from .gate import resolve_evidence_path, sha256_of_file, split_sha_fragment

    items = node.get("evidence") or []
    if not items:
        return {"state": "absent", "checked": 0, "detail": "no evidence recorded"}

    resolved_any = False
    dead_any = False
    stale_any = False
    verified = 0
    for item in items:
        if not isinstance(item, dict):
            text = str(item).strip()
            raw = text[len("path:"):] if text.startswith("path:") else text
            # Split the fragment FIRST: a legacy `x.md#sha256:<hex>` ends in hex, not
            # in `.md`, so testing the raw string classified it as prose.
            bare_path, frag_sha = split_sha_fragment(raw)
            looks_like_path = (
                " " not in raw
                and not raw.startswith(("http://", "https://", "cmd:", "url:", "sha256:"))
                and (("/" in bare_path) or ("\\" in bare_path)
                     or bare_path.endswith((".py", ".md", ".json", ".mjs", ".js", ".sh",
                                            ".txt", ".html", ".jsonl", ".yml", ".yaml")))
            )
            if not looks_like_path:
                resolved_any = True          # prose: a declaration, but nothing observable
                continue
            path, base = resolve_evidence_path(root, bare_path)
            if path is None:
                dead_any = True
                continue
            if frag_sha:
                # The locator itself declared the digest, so this is checkable — the
                # legacy `path:x#sha256:<hex>` form is a claim that can be proved.
                try:
                    actual = sha256_of_file(path)
                except OSError:
                    dead_any = True
                    continue
                if actual != frag_sha:
                    # The file is there; its bytes changed. That is not "no evidence",
                    # it is evidence that no longer describes what was claimed — the
                    # memory has gone stale against its own proof.
                    stale_any = True
                    continue
                # Do not return early: another locator on the same node may be stale,
                # and a node with one good and one rotted citation is partly stale.
                verified += 1
                continue
            resolved_any = True
            continue
        locator = str(item.get("locator") or "")
        expected = str(item.get("content_sha256") or "")
        if not locator.startswith("path:"):
            resolved_any = True              # cmd:/url:/sha256: carry no local bytes
            continue
        path, base = resolve_evidence_path(root, locator[len("path:"):])
        if path is None:
            dead_any = True
            continue
        try:
            actual = sha256_of_file(path)
        except OSError:
            dead_any = True
            continue
        if expected and actual != expected:
            stale_any = True
            continue
        verified += 1
        continue

    # Order matters: a node with one stale digest and one prose note is STALE, not
    # "declared". Letting `declared` win hid three such nodes on the team graph —
    # exactly the failure this state exists to surface.
    if stale_any:
        # Two literal states, not a ternary: the glyph-coverage test walks this
        # function's source for `"state": "<literal>"` and a computed state would be
        # invisible to it — which is how `partly_stale` slipped past the display map.
        state = "partly_stale" if verified else "stale"
        return {"state": state, "checked": verified,
                "detail": "the file exists but its bytes no longer match the declared digest"}
    if verified:
        return {"state": "verified", "checked": verified,
                "detail": "file resolved and digest matched"}
    if resolved_any:
        return {"state": "declared", "checked": 0,
                "detail": "recorded, but no digest was verified"}
    if dead_any:
        return {"state": "missing", "checked": 0, "detail": "every path locator resolves nowhere"}
    return {"state": "declared", "checked": 0, "detail": "recorded, but nothing was verified"}


def evidence_buckets(doc: dict, root: str) -> dict:
    """Split `done` nodes into three named buckets instead of one `done_no_evidence`.

    Why (DECISIONS #57, `decision.mem-arch-known-limitation-not-exemption`):

    `legacy_stats` reports a single `done_no_evidence` count. That number mixes
    "no evidence at all" with "a declaration the audit cannot check", and a reader
    who sees one number cannot tell which of the two they are looking at — the same
    failure as reporting `ValidationSuspended` as `ValidationFailed`. Measured on the
    team graph, the mixed number was 187 while the third bucket was 204 nodes that
    were never debt at all, only resolved against a different base.

    Buckets (per `done` node, a node lands in exactly one):

    * `evidence_absent` — the list is empty. There is nothing to check.
    * `evidence_unverifiable` — there are locators, but none can be observed:
      `missing`, `outside_root`, non-path locators (prose, `cmd:`, `url:`), or a
      declared digest that no longer matches the bytes.
    * `evidence_resolvable` — at least one locator resolves and its digest matches,
      reported with the base that resolved it (`root` or the sub-base name) and
      whether it needed a sub-base. A sub-base hit is evidence of a locator written
      against a different root; reporting the base keeps that visible instead of
      quietly making the debt number smaller.

    `known_limitation` is an interface reserved for the registry (P1). It is empty
    here on purpose: a limitation is not an exemption, and this build cannot know
    which nodes are registered.
    """
    from .gate import resolve_evidence_path, sha256_of_file, split_sha_fragment

    absent, unverifiable, resolvable, declared = [], [], [], []
    for node in doc.get("nodes") or []:
        if node.get("status") != "done":
            continue
        nid = node.get("id")
        items = node.get("evidence") or []
        if not items:
            absent.append(nid)
            continue
        hit = None
        reasons = []
        for item in items:
            if not isinstance(item, dict):
                # A legacy bare string is a DECLARATION, not a verified object: there is
                # no declared digest to match, so it can at most prove the file exists.
                # Counting it as `resolvable` would claim more than it supports; counting
                # it as absent would hide that a declaration was made. It lands in
                # `unverifiable` with the reason `legacy_bare_string`, and its
                # base-resolution is still reported so a switcher cannot hide the
                # locator-base bug behind a smaller number.
                text = str(item).strip()
                raw = text[len("path:"):] if text.startswith("path:") else text
                _ext = (".py", ".md", ".json", ".mjs", ".js", ".sh", ".txt",
                        ".html", ".jsonl", ".yml", ".yaml")
                looks_like_path = (
                    " " not in raw
                    and not raw.startswith(("http://", "https://", "cmd:", "url:", "sha256:"))
                    and (("/" in raw) or ("\\" in raw) or raw.endswith(_ext))
                )
                if looks_like_path and not raw.startswith(("http://", "https://", "cmd:")):
                    _bare, _frag = split_sha_fragment(raw)
                    _p, _b = resolve_evidence_path(root, _bare)
                    reasons.append(f"legacy_bare_string@{_b or 'unresolved'}")
                else:
                    reasons.append("legacy_bare_string@prose")
                continue
            locator = str(item.get("locator") or "")
            expected = str(item.get("content_sha256") or "")
            if not locator.startswith("path:"):
                reasons.append("unverifiable_locator")
                continue
            path, base = resolve_evidence_path(root, locator[len("path:"):])
            if path is None:
                reasons.append(base)          # "missing" or "outside_root"
                continue
            try:
                actual = sha256_of_file(path)
            except OSError:
                reasons.append("unreadable")
                continue
            if expected and actual != expected:
                reasons.append("mismatch")
                continue
            hit = {
                "id": nid,
                "base": base,
                # a sub-base hit means the locator was written against another root
                "via_sub_base": base != "root",
                "locator": locator,
                "path": path,
            }
            break
        if hit is not None:
            resolvable.append(hit)
        elif reasons and all(r.startswith("legacy_bare_string@") for r in set(reasons)):
            # Every locator is a bare-string declaration, so no digests exist to check.
            # The split that matters is NOT "is it a bare string" but "could its
            # locators be observed at all":
            #   * resolved at some base, or prose-only -> nothing was lost, it is a
            #     declaration we cannot verify: `declared`.
            #   * nothing resolved (`missing` / `outside_root`) -> the pointer itself is
            #     dead: that is `unverifiable`, not a declaration sitting quietly in a
            #     bucket that reads as "known and accounted for".
            # Before this split, 272 dead pointers were reported as `declared` while
            # `unverifiable` read 0 — a number that says "nothing is broken" while the
            # same run lists 272 broken pointers (reported by the CEO on the live view).
            bases = sorted({r.split("@", 1)[1] for r in reasons})
            dead = {"missing", "outside_root", "unresolved"} & set(bases)
            if dead and "prose" not in bases:
                unverifiable.append({"id": nid, "reasons": [f"legacy_bare_string@{b}"
                                                          for b in sorted(dead)]})
            else:
                declared.append({"id": nid, "bases": bases})
        else:
            unverifiable.append({"id": nid, "reasons": sorted(set(reasons))})

    absent.sort()
    unverifiable.sort(key=lambda row: row["id"])
    resolvable.sort(key=lambda row: row["id"])
    declared.sort(key=lambda row: row["id"])
    return {
        "evidence_absent": {"count": len(absent), "ids": absent},
        "evidence_unverifiable": {"count": len(unverifiable), "nodes": unverifiable},
        "evidence_resolvable": {
            "count": len(resolvable),
            "via_base": {
                "root": sum(1 for r in resolvable if r["base"] == "root"),
                **{name: sum(1 for r in resolvable if r["base"] == name)
                   for name in sorted({r["base"] for r in resolvable} - {"root"})},
            },
            "nodes": resolvable,
        },
        "evidence_declared_uncheckable": {
            "count": len(declared),
            "nodes": declared,
            "note": "legacy bare-string declarations: the file may exist, but no digest "
                    "was declared, so existence is all that can be shown",
        },
        "known_limitation": {"count": 0, "ids": [], "note": "registry not implemented (P1)"},
    }


def audit(doc: dict, pin: dict = None, now: datetime.datetime = None,
          stale_days: int = None) -> dict:
    now = now or datetime.datetime.now(datetime.timezone.utc)
    if stale_days is None:
        stale_days = stale_days_from_env()
    nodes = doc.get("nodes") or []
    edges = doc.get("edges") or []
    changes = doc.get("changes") or []
    conflicts, hints, findings = [], [], []

    def add(severity: str, kind: str, detail: str, **fields):
        """Record one finding; the human lists are derived from these, never the
        reverse, so `--json` consumers and text output cannot describe different
        realities. Kept append-only and order-preserving for compatibility."""
        entry = {"severity": severity, "kind": kind, "detail": detail}
        entry.update(fields)
        findings.append(entry)
        (conflicts if severity == "conflict" else hints).append(detail)

    legacy = legacy_stats(doc)
    pinned = set()
    pin_report = None
    if pin:
        expected_done = pin.get("done_no_evidence_sha256")
        expected_all = pin.get("no_evidence_sha256")
        match = (expected_done in (None, legacy["done_no_evidence_sha256"]) and
                 expected_all in (None, legacy["no_evidence_sha256"]))
        pin_report = {
            "expected": {"done_no_evidence_sha256": expected_done,
                         "no_evidence_sha256": expected_all},
            "actual": {"done_no_evidence_sha256": legacy["done_no_evidence_sha256"],
                       "no_evidence_sha256": legacy["no_evidence_sha256"]},
            "match": match,
        }
        if not match:
            add("conflict", "pin_changed",
                "legacy exemption pin changed without an explicit explanation "
                "(new exemptions or backfill) — only forward writes may add exemptions")
        else:
            pinned = legacy["_ids"]

    ids = {n.get("id") for n in nodes}
    for n in nodes:
        nid = n.get("id")
        if n.get("status") == "done" and not (n.get("evidence") or []) and nid not in pinned:
            add("conflict", "done_without_evidence", f"{nid}: done without evidence (IR-4)",
                node=nid, type=n.get("type"), status=n.get("status"), owner=n.get("owner"))
        if (n.get("status") in {"in_progress", "blocked"}
                and n.get("type") not in LONG_LIVED_TYPES):
            ts = _parse(n.get("updatedAt"))
            if ts and (now - ts).days >= stale_days:
                age = (now - ts).days
                add("conflict", "stale_work_item",
                    f"{nid}: {n.get('status')} untouched for {age}d (limit {stale_days}d)",
                    node=nid, type=n.get("type"), status=n.get("status"),
                    owner=n.get("owner"), age_days=age, limit_days=stale_days)
        if not_yet_valid(n, now):
            add("hint", "not_yet_valid",
                f"{nid}: not yet valid (valid_from {n.get('valid_from')} is in the "
                f"future) — treated as not yet in effect by retrieval and expiry",
                node=nid, valid_from=n.get("valid_from"))
        vu = _parse(n.get("valid_until"))
        if vu and vu <= now and n.get("status") != "superseded":
            if expiry_eligible(n):
                add("conflict", "expired_but_active",
                    f"{nid}: valid_until passed but status={n.get('status')} (not superseded)",
                    node=nid, status=n.get("status"), valid_until=n.get("valid_until"))
            else:
                add("hint", "expired_though_validity_unknown",
                    f"{nid}: valid_until passed but validity time is unknown "
                    f"(valid_time_known=false) — cannot auto-expire, manual review",
                    node=nid, valid_until=n.get("valid_until"))
        if is_conclusion(n) and n.get("status") == "done" and not (n.get("evidence") or []):
            add("hint", "conclusion_without_grade",
                f"{nid}: conclusion without evidence grade", node=nid, type=n.get("type"))

    from . import handoff as handoff_mod
    active_cards = handoff_mod.all_active(doc)
    if len(active_cards) > 1:
        add("conflict", "multiple_active_handoffs",
            f"{len(active_cards)} active handoff cards; exactly one may be active "
            f"(writing a new card supersedes the previous)",
            count=len(active_cards))
    for card in active_cards:
        size = handoff_mod.bytes_of(card.get("note"))
        if size > handoff_mod.MAX_BYTES:
            add("conflict", "handoff_over_budget",
                f"{card.get('id')}: handoff is {size} B (limit {handoff_mod.MAX_BYTES} B)",
                node=card.get("id"), bytes=size, limit_bytes=handoff_mod.MAX_BYTES)

    for e in edges:
        if e.get("from") not in ids or e.get("to") not in ids:
            add("conflict", "dangling_edge",
                f"dangling edge {e.get('from')} -{e.get('kind')}-> {e.get('to')}",
                edge={"from": e.get("from"), "to": e.get("to"), "kind": e.get("kind")})

    shapes = {}
    missing_target = missing_rev = 0
    for c in changes:
        key = ",".join(sorted(c.keys()))
        shapes[key] = shapes.get(key, 0) + 1
        if "target" not in c:
            missing_target += 1
        if "rev" not in c:
            missing_rev += 1
    # Registrations (group/env/member/handoff) are not facts with a validity window,
    # so they are not TTL candidates and must not inflate this count.
    unknown_validity = sum(
        1 for n in nodes
        if n.get("valid_time_known") is False and n.get("type") not in LONG_LIVED_TYPES)
    if unknown_validity:
        add("hint", "unknown_validity",
            f"valid_time_known=false on {unknown_validity} node(s): "
            f"TTL auto-expiry refuses them (no fact time recorded, so deleting on age "
            f"would be a guess)",
            count=unknown_validity)

    if missing_target or missing_rev:
        add("hint", "changes_key_shapes",
            f"changes key shapes: {len(shapes)} variants, missing target={missing_target}, "
            f"missing rev={missing_rev} (run `amg migrate` before any public release)",
            variants=len(shapes), missing_target=missing_target, missing_rev=missing_rev)

    return {
        "ok": not conflicts,
        "conflicts": conflicts,
        "hints": hints,
        "legacy": {k: v for k, v in legacy.items() if not k.startswith("_")},
        "pin": pin_report,
        "counts": {"nodes": len(nodes), "edges": len(edges), "changes": len(changes),
                   "rev": doc.get("rev", 0)},
        # Structured form of the same findings: severity, kind, the human detail, and
        # the node/edge/owner the reader has to act on. Added in 0.9.0; `conflicts`
        # and `hints` stay for compatibility.
        "findings": findings,
    }
