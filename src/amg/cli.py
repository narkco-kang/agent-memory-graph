"""amg CLI. Exit codes: 0 ok / 1 protocol+conflicts / 2 usage / 3 io+lock."""
import argparse
import json
import os
import sys

from . import __version__
from .const import EXIT_ERROR, EXIT_IO, EXIT_OK, EXIT_USAGE
from .errors import LockTimeout, ProtocolError
from .memory import Memory
from . import security as security_mod

COMMANDS = ["init", "add", "import", "status", "supersede", "link", "related", "search", "digest", "check", "audit", "mcp",
            "export", "doctor", "migrate", "adopt", "expire", "archive", "fingerprint", "verify", "handoff", "version"]


def _evidence_args(values):
    out = []
    for raw in values or []:
        parts = raw.split("|")
        if len(parts) < 3:
            raise ProtocolError("E_EVIDENCE_FORMAT",
                                "--evidence expects 'locator|content_sha256|captured_at[|grade]'")
        item = {"locator": parts[0], "content_sha256": parts[1], "captured_at": parts[2]}
        if len(parts) > 3 and parts[3].strip():
            item["grade"] = int(parts[3])
        out.append(item)
    return out


def _print(obj, as_json: bool):
    print(json.dumps(obj, ensure_ascii=False, indent=2) if as_json else obj)


def cmd_init(a):
    m = Memory.init(a.dir, a.group, goal=a.goal or "")
    _print(f"initialized {os.path.abspath(a.dir)} (group={a.group})", a.json)
    return EXIT_OK


def cmd_add(a):
    m = Memory.open(a.dir)
    kwargs = {}
    if a.type == "rule":
        if not a.applies:
            raise ProtocolError("E_RULE_APPLIES", "rule nodes require --applies")
        if a.expires_when is None and not a.expires_never:
            raise ProtocolError("E_RULE_EXPIRES",
                                "rule nodes must declare --expires-when or --expires-never explicitly")
        kwargs["applies"] = a.applies
        kwargs["expires_when"] = None if a.expires_never else a.expires_when
    node = m.add_node(id=a.id, type=a.type, label=a.label, source=a.source,
                      status=a.status, owner=a.owner, note=a.note,
                      valid_from=a.valid_from, valid_until=a.valid_until,
                      evidence=_evidence_args(a.evidence),
                      conclusion=True if a.conclusion else None,
                      by=a.by, **kwargs)
    _print(f"added {node['id']} [{node['type']}/{node['status']}]", a.json)
    return EXIT_OK


def cmd_import(a):
    m = Memory.open(a.dir)
    try:
        with open(a.from_file, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except FileNotFoundError:
        raise ProtocolError("E_BAD_FILE", f"batch file not found: {a.from_file}")
    except json.JSONDecodeError as exc:
        raise ProtocolError("E_BAD_BATCH", f"batch file is not valid JSON: {exc}")
    if isinstance(data, list):
        nodes, edges = data, []
    elif isinstance(data, dict):
        nodes, edges = data.get("nodes"), data.get("edges") or []
    else:
        raise ProtocolError("E_BAD_BATCH", "batch file must be a list of nodes or an object with nodes/edges")
    res = m.add_many(nodes, edges, by=a.by)
    _print(f"imported {res['nodes']} node(s), {res['edges']} edge(s) -> rev {res['rev']}", a.json)
    return EXIT_OK


def cmd_status(a):
    m = Memory.open(a.dir)
    res = m.set_status(a.id, a.new_status, note=a.note,
                       evidence=_evidence_args(a.evidence), by=a.by)
    _print(f"{res['id']}: {res['from']} -> {res['to']}", a.json)
    return EXIT_OK


def cmd_supersede(a):
    m = Memory.open(a.dir)
    res = m.supersede(a.old_id, a.new_id, note=a.note, by=a.by)
    _print(f"{res['old']} superseded by {res['new']} (valid_until {res['valid_until']})", a.json)
    return EXIT_OK


def cmd_related(a):
    m = Memory.open(a.dir)
    res = m.related(a.id, depth=a.depth, kind=a.kind, audit_read=a.audit_read)
    if a.json:
        print(json.dumps(res, ensure_ascii=False, indent=2))
    else:
        print(f"{res['id']} depth={res['depth']}" + (f" kind={res['kind']}" if res["kind"] else ""))
        for n in res["neighbors"]:
            arrow = "->" if n["direction"] == "out" else "<-"
            flag = "✓" if n["anchor_state"] == "present" else "~"
            print(f"{flag} {arrow} [{n['kind']}] {n['id']} [{n['status']}] {n.get('label') or ''}"
                  f" (depth {n['depth']}{', cycle' if n.get('cycle') else ''})")
        if not res["neighbors"]:
            print("no neighbors")
    return EXIT_OK


def cmd_link(a):
    m = Memory.open(a.dir)
    m.add_edge(a.from_id, a.to_id, a.kind, by=a.by)
    _print(f"linked {a.from_id} -{a.kind}-> {a.to_id}", a.json)
    return EXIT_OK


def cmd_search(a):
    m = Memory.open(a.dir)
    hits = m.search(a.query, layer=a.layer, k=a.k, strict=a.strict, expand=a.expand,
                    audit_read=a.audit_read, include_archive=a.include_archive)
    if a.json:
        print(json.dumps(hits, ensure_ascii=False, indent=2))
    else:
        for h in hits:
            flag = "✓" if h["anchor_state"] == "present" else "~"
            where = f", archive={h['archive_file']}" if h.get("archived") else ""
            print(f"{flag} {h['score']:>5} {h['id']} [{h['status']}] {h.get('label') or ''}"
                  f" (anchor={h['anchor_state']}, ev×{h['evidence_count']}{where})")
        if not hits:
            print("no hits")
    return EXIT_OK


def cmd_digest(a):
    m = Memory.open(a.dir)
    text = m.digest(max_bytes=a.max_bytes)
    out = a.out or os.path.join(os.path.abspath(a.dir), "graph.md")
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(text)
    size = len(text.encode("utf-8"))
    if a.json:
        print(json.dumps({"out": out, "bytes": size, "max_bytes": a.max_bytes}, ensure_ascii=False))
    else:
        print(f"digest -> {out} ({size} B, budget {a.max_bytes} B)")
    return EXIT_OK


def cmd_check(a):
    m = Memory.open(a.dir)
    rep = m.check(strict=a.strict)
    if a.json:
        print(json.dumps(rep, ensure_ascii=False, indent=2))
    else:
        print(f"nodes {rep['counts']['nodes']} / edges {rep['counts']['edges']} / changes {rep['counts']['changes']}")
        for e in rep["errors"]:
            print(f"✗ {e}")
        for h in rep["hints"]:
            print(f"· {h}")
        print("✓ check passed" if rep["ok"] else f"✗ {len(rep['errors'])} error(s)")
    return EXIT_OK if rep["ok"] else EXIT_ERROR


def cmd_audit(a):
    pin = None
    if a.pin:
        with open(a.pin, "r", encoding="utf-8") as fh:
            pin = json.load(fh)
    m = Memory.open(a.dir)
    rep = m.audit(pin=pin, stale_days=a.stale_days)
    if a.json:
        print(json.dumps(rep, ensure_ascii=False, indent=2))
    else:
        for c in rep["conflicts"]:
            print(f"✗ {c}")
        for h in rep["hints"]:
            print(f"· {h}")
        lg = rep["legacy"]
        print(f"legacy: done-no-evidence {lg['done_no_evidence_ratio']} / "
              f"no-evidence {lg['no_evidence_ratio']}")
        if rep["pin"]:
            print(f"pin match: {rep['pin']['match']}")
        print("✓ audit clean" if rep["ok"] else f"✗ {len(rep['conflicts'])} conflict(s)")
    return EXIT_OK if rep["ok"] else EXIT_ERROR


def cmd_mcp(a):
    """Serve the graph over stdio as an MCP server. No socket, no auth.

    `--read-only` is enforced twice on purpose: the server refuses the write
    tools before dispatch, and the `Memory` instance refuses every commit. The
    second layer is what makes the guarantee independent of the tool list.
    """
    from . import mcp as mcp_mod
    m = Memory.open(a.dir, read_only=a.read_only)
    for item in m.security_findings():
        sys.stderr.write(f"amg mcp: warning [{item['code']}] {item['detail']}\n")
    mode = "read-only" if a.read_only else "read-write"
    sys.stderr.write(f"amg mcp: serving {os.path.abspath(a.dir)} over stdio "
                     f"(no network, no auth, {mode})\n")
    sys.stderr.flush()
    return mcp_mod.serve(m, read_only=a.read_only)


def cmd_handoff(a):
    """Write the handoff card, or read the active one. Bounded on purpose."""
    m = Memory.open(a.dir)
    if a.note is None:
        card = m.handoff()
        if card is None:
            print("no handoff card yet — write one with: amg handoff <dir> --by NAME --note -",
                  file=sys.stderr)
            return EXIT_USAGE
        if a.json:
            print(json.dumps(card, ensure_ascii=False, indent=2))
        else:
            print(card["note"].rstrip())
            print(f"\n· {card['bytes']}/{card['max_bytes']} B · by {card['by']} · {card['at']}")
        return EXIT_OK
    note = a.note
    if note == "-":
        note = sys.stdin.read()
    card = m.write_handoff(note, by=a.by, owner=a.owner)
    if a.json:
        print(json.dumps(card, ensure_ascii=False, indent=2))
    else:
        print(f"handoff written: {card['id']} ({card['bytes']}/{card['max_bytes']} B)")
        if card.get("superseded"):
            print(f"superseded: {card['superseded']}")
    return EXIT_OK


def cmd_fingerprint(a):
    """Print the canonical digests of state and history. Writes nothing to the graph."""
    m = Memory.open(a.dir)
    fp = m.fingerprint()
    if a.out:
        with open(a.out, "w", encoding="utf-8") as fh:
            json.dump(fp, fh, ensure_ascii=False, indent=2)
            fh.write("\n")
    if a.json:
        print(json.dumps(fp, ensure_ascii=False, indent=2))
    else:
        print(f"{os.path.abspath(a.dir)}  rev {fp['rev']}  "
              f"{fp['nodes']} nodes / {fp['edges']} edges / {fp['changes']} changes")
        print(f"  state_sha256    {fp['state_sha256']}")
        print(f"  history_sha256  {fp['history_sha256']}")
        if a.out:
            print(f"  written to {a.out}")
        print("  keep this value outside the graph: a fingerprint stored next to the "
              "data proves nothing (docs/THREAT-MODEL.md)")
    return EXIT_OK


def _load_expected(a):
    if a.expect:
        try:
            with open(a.expect, encoding="utf-8") as fh:
                return json.load(fh)
        except (OSError, json.JSONDecodeError) as exc:
            raise ProtocolError("E_BAD_FINGERPRINT", f"cannot read --expect {a.expect}: {exc}")
    if a.expect_state or a.expect_history:
        return {"state_sha256": (a.expect_state or "").lower(),
                "history_sha256": (a.expect_history or "").lower()}
    raise ProtocolError("E_NO_EXPECTATION",
                        "pass --expect FILE, or --expect-state/--expect-history HEX")


def cmd_verify(a):
    """Compare current digests with a recorded fingerprint. Exit 1 on mismatch."""
    m = Memory.open(a.dir)
    report = m.verify_fingerprint(_load_expected(a))
    if a.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        for name in report["checked"]:
            data = report["checks"][name]
            print(f"  {name}: {'ok' if data['match'] else 'MISMATCH'}")
        print(f"verified {', '.join(report['checked'])} -> "
              f"{'match' if report['ok'] else 'MISMATCH ' + ', '.join(report['mismatched'])}")
    if not report["ok"]:
        raise ProtocolError("E_FINGERPRINT_MISMATCH",
                            "recorded fingerprint does not match the graph "
                            f"({', '.join(report['mismatched'])})")
    return EXIT_OK


def cmd_export(a):
    m = Memory.open(a.dir)
    sys.stdout.write(m.export(fmt=a.format))
    return EXIT_OK


def cmd_doctor(a):
    d = os.path.abspath(a.dir)
    leftovers = [f for f in os.listdir(d) if f.startswith(".graph.") and f.endswith(".tmp")]
    for f in leftovers:
        os.unlink(os.path.join(d, f))
    m = Memory.open(a.dir)
    rep = m.check()
    hygiene = m.security_findings()
    info = {"dir": d, "cleaned_tmp": len(leftovers), "check_ok": rep["ok"],
            "counts": rep["counts"], "size_bytes": os.path.getsize(os.path.join(d, "graph.json")),
            "security": hygiene, "security_worst": security_mod.worst(hygiene)}
    if a.json:
        print(json.dumps(info, ensure_ascii=False, indent=2))
    else:
        print(f"dir {d}\ncleaned {len(leftovers)} tmp file(s)\ncheck_ok={rep['ok']} "
              f"nodes={rep['counts']['nodes']} size={info['size_bytes']} B")
        if hygiene:
            for item in hygiene:
                print(f"  [{item['severity']}] {item['code']}: {item['detail']}")
        else:
            print("  permissions: graph and directory are not world/group writable, "
                  "path is local")
    if a.strict and info["security_worst"] in {"error", "warn"}:
        raise ProtocolError("E_INSECURE_GRAPH",
                            f"{info['security_worst']} severity hygiene findings: "
                            + ", ".join(sorted({h["code"] for h in hygiene})))
    return EXIT_OK if rep["ok"] else EXIT_ERROR


def cmd_migrate(a):
    m = Memory.open(a.dir)
    stats = m.migrate()
    print(json.dumps(stats, ensure_ascii=False, indent=2) if a.json else
          f"changed={stats['changed']} records={stats['records']} "
          f"filled_target={stats['filled_target']} filled_rev={stats['filled_rev']}")
    return EXIT_OK


# Exit-code classification (maintainer ruling 2026-10-29):
#   2 = the caller used the API wrong (bad argument, unknown enum, wrong target)
#   1 = the content violates the protocol (gate rejection, duplicate, dangling)
# There is deliberately NO default branch: an unclassified code is a programming
# error and must fail loudly, so a newly added exception can never quietly land
# on exit 1 and be mistaken for a protocol violation.
USAGE_EXIT_CODES = frozenset({
    "E_NO_GRAPH", "E_BAD_TYPE", "E_BAD_STATUS", "E_BAD_LAYER", "E_BAD_EDGE",
    "E_BAD_FORMAT", "E_BAD_ID", "E_EXISTS", "E_RULE_APPLIES", "E_RULE_EXPIRES",
    "E_BAD_BATCH", "E_BAD_FILE", "E_BAD_DEPTH",
    "E_USE_SUPERSEDE", "E_BAD_SUPERSEDE", "E_BAD_VALID_TIME", "E_BAD_VALID_RANGE",
    # adopt-specific (added with the adoption tool; they mean "wrong input",
    # not "bad content"): pointing adopt at an already-amg graph
    "E_ALREADY_AMG",
    # read-only mode: the caller addressed a capability this session does not
    # have (same class as E_ALREADY_AMG), not a violation of graph content
    "E_READ_ONLY",
    # fingerprint: no expectation given / unusable expectation file
    "E_NO_EXPECTATION", "E_BAD_FINGERPRINT",
    # handoff: empty card or over the 4 KB budget — the caller's input is wrong,
    # and the fix is to shorten it, not to change the graph
    "E_BAD_HANDOFF", "E_HANDOFF_TOO_LARGE",
    # search: --include-archive only applies to L2 history; asking for it on a node
    # layer is a wrong call, not bad content
    "E_ARCHIVE_LAYER",
})
ERROR_EXIT_CODES = frozenset({
    "E_NO_SOURCE", "E_NOTE_REQUIRED", "E_EVIDENCE_MISSING", "E_EVIDENCE_FORMAT",
    "E_DUP_ID", "E_DUP_EDGE", "E_NO_NODE", "E_IMMUTABLE",
    # adopt-specific: the legacy source itself violates the protocol
    "E_ADOPT_UNSUPPORTED", "E_ADOPT_DANGLING",
    # the file no longer matches the fingerprint recorded outside it
    "E_FINGERPRINT_MISMATCH",
    # the graph sits outside the only boundary this project has (see THREAT-MODEL)
    "E_INSECURE_GRAPH",
    # archive: the move could not be proven lossless, so it was rolled back.
    # Classified as content (1), not caller error: the records are fine, the
    # proof is what failed, and a caller has nothing to fix by retyping.
    "E_ARCHIVE_VERIFY",
})
EXIT_CODES_BY_ERROR = {code: 2 for code in USAGE_EXIT_CODES}
EXIT_CODES_BY_ERROR.update({code: 1 for code in ERROR_EXIT_CODES})


def exit_code_for(exc) -> int:
    """Map a ProtocolError to its exit code using the explicit table only."""
    code = getattr(exc, "code", None)
    try:
        return EXIT_CODES_BY_ERROR[code]
    except KeyError:
        raise RuntimeError(
            f"unclassified protocol error code {code!r}: add it to "
            "USAGE_EXIT_CODES or ERROR_EXIT_CODES (no default on purpose)"
        ) from None


def cmd_adopt(a):
    rep = Memory.adopt(a.src, a.dst, group=a.group, drop_dangling=a.drop_dangling,
                       pin_out=a.pin_out, dry_run=a.dry_run)
    if a.json:
        print(json.dumps(rep, ensure_ascii=False, indent=2))
    else:
        mapped, counts = rep["mapped"], rep["counts"]
        print(f"adopt {'(dry-run) ' if rep['dry_run'] else ''}{rep['src']} -> {rep['dst']}")
        print(f"  nodes {counts['nodes_before']}->{counts['nodes']}  edges "
              f"{counts['edges_before']}->{counts['edges']}  changes "
              f"{counts['changes_before']}->{counts['changes']}")
        print(f"  source backfilled {mapped['source_backfilled']} | legacy evidence strings "
              f"{mapped['evidence_legacy_strings']} | kept objects {mapped['evidence_objects_kept']}"
              f" | rejected objects {mapped['evidence_objects_rejected']}")
        print(f"  superseded completed {mapped['superseded_completed']} | valid_from unknown "
              f"{mapped['valid_from_unknown']} | dup edges merged "
              f"{counts['duplicate_edges_merged']} | dangling dropped {counts['dangling_dropped']}")
        lg = rep["legacy"]
        print(f"  legacy: done-no-evidence {lg['done_no_evidence_ratio']} / "
              f"no-evidence {lg['no_evidence_ratio']}")
        if rep["pin"]:
            print(f"  pin -> {rep['pin']}")
        print("  check:", "✓ passed" if rep["check"]["ok"]
              else f"✗ {len(rep['check']['errors'])} error(s)")
        for err in rep["check"]["errors"][:10]:
            print(f"    ✗ {err}")
    return EXIT_OK if rep["check"]["ok"] else EXIT_ERROR


def cmd_expire(a):
    m = Memory.open(a.dir)
    rep = m.expire(apply=a.apply)
    if a.json:
        print(json.dumps(rep, ensure_ascii=False, indent=2))
    else:
        mode = "apply" if a.apply else "dry-run"
        print(f"expire ({mode}) {os.path.abspath(a.dir)}")
        listed = ", ".join(rep["eligible"][:5]) or "—"
        more = "" if len(rep["eligible"]) <= 5 else f" (+{len(rep['eligible']) - 5} more)"
        print(f"  eligible {len(rep['eligible'])}: {listed}{more}")
        print(f"  applied {rep['applied']} | skipped (unknown validity) "
              f"{rep['skipped_unknown_validity']} | already superseded "
              f"{rep['already_superseded']} | rev {rep['rev']}")
        if not a.apply:
            print("  dry-run: nothing written (use --apply to expire)")
    return EXIT_OK


def cmd_archive(a):
    if a.verify:
        m = Memory.open(a.dir, read_only=True)
        rep = m.archive_verify()
        if a.json:
            print(json.dumps(rep, ensure_ascii=False, indent=2))
        else:
            print(f"archive verify {os.path.abspath(a.dir)}")
            for item in rep["files"]:
                mark = "✓" if item.get("ok") else "✗"
                print(f"  {mark} {item['file']}: {item.get('count')} record(s) "
                      f"rev {item.get('revFrom')}..{item.get('revTo')}")
            span = (f", rev {rep['rev_range'][0]}..{rep['rev_range'][1]}"
                    if rep["rev_range"] else "")
            print(f"  archived {rep['archived_records']} + live {rep['live_records']} "
                  f"= {rep['archived_records'] + rep['live_records']} record(s){span}")
            print(f"  rev continuity: {rep['rev_continuity']}")
            for reason in rep["reasons"]:
                print(f"  ✗ {reason}")
            print("✓ archive verified" if rep["ok"] else "✗ archive verification failed")
        return EXIT_OK if rep["ok"] else EXIT_ERROR

    m = Memory.open(a.dir)
    rep = m.archive(days=a.days, apply=a.apply, by=a.by)
    if a.json:
        print(json.dumps(rep, ensure_ascii=False, indent=2))
    else:
        mode = "apply" if a.apply else "dry-run"
        print(f"archive ({mode}) {os.path.abspath(a.dir)}")
        print(f"  cutoff {rep['cutoff']} ({rep['days']} d)")
        span = (f" rev {rep['rev_from']}..{rep['rev_to']}"
                if rep.get("rev_from") is not None else "")
        print(f"  eligible {rep['eligible']} of {rep['changes_total']} change record(s){span}")
        print(f"  deferred behind a newer record {rep['deferred_behind_newer']} | "
              f"undated after the prefix {rep['unknown_time_after_prefix']}")
        if rep["eligible"] == 0:
            print("  nothing is old enough; nothing written")
        elif not a.apply:
            print("  dry-run: nothing written (use --apply)")
        else:
            v = rep["verify"]
            print(f"  archived -> {rep['archive']['file']} "
                  f"({rep['archive']['count']} record(s), {rep['archive']['bytes']} B)")
            print(f"  snapshot -> {rep['snapshot']['file']} "
                  f"(sha256 {rep['snapshot']['sha256'][:16]}…)")
            print(f"  bytes {rep['bytes_before']} -> {rep['bytes_after']}")
            flag = lambda ok: "✓" if ok else ("—" if ok is None else "✗")
            print(f"  proof: payload {flag(v['archive_payload_match'])} | "
                  f"live ledger {flag(v['live_ledger_match'])} | "
                  f"state unchanged {flag(v['state_unchanged'])} | "
                  f"check {flag(v['check_ok'])} | "
                  f"rev contiguous {flag(v['rev_contiguous'])}")
            for reason in v["reasons"]:
                print(f"  ✗ {reason}")
            print("✓ archive written and verified" if v["ok"]
                  else "✗ verification failed (graph restored)")
    return EXIT_OK


def cmd_version(a):
    print(f"amg {__version__}")
    return EXIT_OK


def build_parser():
    p = argparse.ArgumentParser(prog="amg", description="append-only evidence-gated memory graph")
    p.add_argument("--version", action="version", version=f"amg {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("init"); s.add_argument("dir"); s.add_argument("--group", required=True)
    s.add_argument("--goal", default=""); s.add_argument("--json", action="store_true")
    s.set_defaults(func=cmd_init)

    s = sub.add_parser("add"); s.add_argument("dir"); s.add_argument("--id", required=True)
    s.add_argument("--type", required=True); s.add_argument("--label", required=True)
    s.add_argument("--source", required=True); s.add_argument("--status", default="open")
    s.add_argument("--owner"); s.add_argument("--note", default="")
    s.add_argument("--evidence", action="append")
    s.add_argument("--conclusion", action="store_true")
    s.add_argument("--valid-from",
                   help="fact time (ISO-8601). Omitted = unknown; never the write time")
    s.add_argument("--valid-until",
                   help="validity end (ISO-8601); must not precede --valid-from")
    s.add_argument("--applies", help="L4 rule scope, e.g. global / repo:agent-memory-graph")
    s.add_argument("--expires-when", default=None,
                   help="L4 rule lifetime (e.g. 2026-12-31); declare lifetime explicitly")
    s.add_argument("--expires-never", action="store_true",
                   help="declare that an L4 rule never expires (explicit, not a default)")
    s.add_argument("--by", default="cli")
    s.add_argument("--json", action="store_true"); s.set_defaults(func=cmd_add)

    s = sub.add_parser("import"); s.add_argument("dir")
    s.add_argument("--from", dest="from_file", required=True, help="JSON file with nodes[] and optional edges[]")
    s.add_argument("--by", default="cli"); s.add_argument("--json", action="store_true")
    s.set_defaults(func=cmd_import)

    s = sub.add_parser("status"); s.add_argument("dir"); s.add_argument("id")
    s.add_argument("new_status"); s.add_argument("--note", required=True)
    s.add_argument("--evidence", action="append"); s.add_argument("--by", default="cli")
    s.add_argument("--json", action="store_true"); s.set_defaults(func=cmd_status)

    s = sub.add_parser("supersede"); s.add_argument("dir")
    s.add_argument("old_id"); s.add_argument("new_id")
    s.add_argument("--note", required=True)
    s.add_argument("--by", default="cli"); s.add_argument("--json", action="store_true")
    s.set_defaults(func=cmd_supersede)

    s = sub.add_parser("link"); s.add_argument("dir"); s.add_argument("--from", dest="from_id", required=True)
    s.add_argument("--to", dest="to_id", required=True); s.add_argument("--kind", required=True)
    s.add_argument("--by", default="cli"); s.add_argument("--json", action="store_true")
    s.set_defaults(func=cmd_link)

    s = sub.add_parser("related"); s.add_argument("dir"); s.add_argument("id")
    s.add_argument("--depth", type=int, default=1); s.add_argument("--kind")
    s.add_argument("--audit-read", action="store_true")
    s.add_argument("--json", action="store_true"); s.set_defaults(func=cmd_related)

    s = sub.add_parser("search"); s.add_argument("dir"); s.add_argument("query")
    s.add_argument("--layer", default="L3"); s.add_argument("--k", type=int, default=10)
    s.add_argument("--strict", action="store_true"); s.add_argument("--expand", action="store_true")
    s.add_argument("--audit-read", action="store_true",
                   help="log this read to reads.jsonl if it is high-risk (L4/strict/superseded)")
    s.add_argument("--include-archive", action="store_true",
                   help="L2 only: also search cold history in archive/changes-*.json")
    s.add_argument("--json", action="store_true")
    s.set_defaults(func=cmd_search)

    s = sub.add_parser("digest"); s.add_argument("dir"); s.add_argument("--max-bytes", type=int, default=65536)
    s.add_argument("--out"); s.add_argument("--json", action="store_true"); s.set_defaults(func=cmd_digest)

    s = sub.add_parser("check"); s.add_argument("dir"); s.add_argument("--strict", action="store_true")
    s.add_argument("--json", action="store_true"); s.set_defaults(func=cmd_check)

    s = sub.add_parser("audit"); s.add_argument("dir"); s.add_argument("--pin")
    s.add_argument("--stale-days", type=int, default=None,
                   help="override AMG_STALE_DAYS for this run (default 3)")
    s.add_argument("--json", action="store_true"); s.set_defaults(func=cmd_audit)

    s = sub.add_parser("mcp"); s.add_argument("dir")
    s.add_argument("--read-only", action="store_true", dest="read_only",
                   help="refuse write tools; the graph cannot be modified through this session")
    s.set_defaults(func=cmd_mcp)

    s = sub.add_parser("handoff")
    s.add_argument("dir")
    s.add_argument("--by", default="amg", help="who is handing over")
    s.add_argument("--owner", default=None, help="who picks it up next")
    s.add_argument("--note", default=None,
                   help="card text; use '-' to read stdin (≤ 4 KB); omit to print the active card")
    s.add_argument("--json", action="store_true")
    s.set_defaults(func=cmd_handoff)
    s = sub.add_parser("fingerprint"); s.add_argument("dir")
    s.add_argument("--json", action="store_true"); s.add_argument("--out")
    s.set_defaults(func=cmd_fingerprint)

    s = sub.add_parser("verify"); s.add_argument("dir")
    s.add_argument("--expect"); s.add_argument("--expect-state"); s.add_argument("--expect-history")
    s.add_argument("--json", action="store_true")
    s.set_defaults(func=cmd_verify)

    s = sub.add_parser("export"); s.add_argument("dir"); s.add_argument("--format", default="json",
                                                                        choices=["json", "jsonl"])
    s.set_defaults(func=cmd_export)

    s = sub.add_parser("doctor"); s.add_argument("dir"); s.add_argument("--json", action="store_true")
    s.add_argument("--strict", action="store_true",
                   help="exit 1 when the graph is world/group writable or on a network path")
    s.set_defaults(func=cmd_doctor)

    s = sub.add_parser("migrate"); s.add_argument("dir"); s.add_argument("--json", action="store_true")
    s.set_defaults(func=cmd_migrate)

    s = sub.add_parser("adopt", help="adopt a legacy group-kg/v1 graph into amg/v1")
    s.add_argument("src"); s.add_argument("dst")
    s.add_argument("--group", help="override group name (default: source group)")
    s.add_argument("--drop-dangling", action="store_true",
                   help="drop edges whose endpoints do not exist (counted, never silent)")
    s.add_argument("--pin-out", help="write the legacy exemption pin for `amg audit --pin`")
    s.add_argument("--dry-run", action="store_true", help="report only, write nothing")
    s.add_argument("--json", action="store_true"); s.set_defaults(func=cmd_adopt)

    s = sub.add_parser("expire", help="supersede nodes whose known validity window ended")
    s.add_argument("dir")
    s.add_argument("--apply", action="store_true",
                   help="write the expiry (default is a dry-run that writes nothing)")
    s.add_argument("--json", action="store_true"); s.set_defaults(func=cmd_expire)

    s = sub.add_parser("archive", help="move old ledger records into a provable cold archive")
    s.add_argument("dir")
    s.add_argument("--older-than-days", type=int, dest="days", default=None,
                   help="archive change records older than N days (default 30; env AMG_ARCHIVE_DAYS)")
    s.add_argument("--apply", action="store_true",
                   help="write the archive (default is a dry-run that writes nothing)")
    s.add_argument("--verify", action="store_true",
                   help="audit existing archive files against the live ledger; writes nothing")
    s.add_argument("--by", default="amg archive")
    s.add_argument("--json", action="store_true"); s.set_defaults(func=cmd_archive)

    s = sub.add_parser("version"); s.set_defaults(func=cmd_version)
    return p


def _utf8_console() -> None:
    """Windows consoles default to cp1252 and cannot encode the status glyphs."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):  # pragma: no cover
            pass


def main(argv=None) -> int:
    _utf8_console()
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except ProtocolError as exc:
        print(f"✗ {exc.code}: {exc.message}", file=sys.stderr)
        return exit_code_for(exc)
    except LockTimeout as exc:
        print(f"✗ lock: {exc}", file=sys.stderr)
        return EXIT_IO
    except OSError as exc:
        print(f"✗ io: {exc}", file=sys.stderr)
        return EXIT_IO


if __name__ == "__main__":
    sys.exit(main())
