"""Filesystem hygiene checks.

The only real boundary this project has is the operating system's file
permissions (see docs/THREAT-MODEL.md §2). That makes one class of mistake worth
detecting mechanically: the graph sitting somewhere the boundary does not hold —
world-writable, on a network mount, or behind a symlink that points elsewhere.

These are checks, not a sandbox. They cannot make a shared filesystem safe; they
can refuse to stay quiet about it.
"""
import os
import stat

NETWORK_PATH_PREFIXES = (
    "/Volumes/",       # macOS: includes SMB/NFS mounts under /Volumes
    "/net/",           # autofs
    "/nfs/",
    "/smb/",
    "//",              # UNC path on Windows
    "\\\\",
)


def _mode(path):
    try:
        return stat.S_IMODE(os.stat(path).st_mode)
    except OSError:
        return None


def findings(path: str) -> list:
    """Return a list of hygiene findings for a graph directory. Empty is good."""
    directory = os.path.abspath(path)
    out = []

    graph = os.path.join(directory, "graph.json")
    if not os.path.exists(graph):
        return [{"code": "E_NO_GRAPH", "severity": "error",
                 "detail": f"no graph.json in {directory}"}]

    if os.path.islink(graph):
        out.append({"code": "SEC_GRAPH_SYMLINK", "severity": "warn",
                    "detail": f"graph.json is a symlink to {os.path.realpath(graph)}"})

    if os.name == "nt":
        # Windows does not expose POSIX permission bits; every writable file looks
        # world-writable through st_mode, so reporting them would be noise. ACLs
        # are the real control there and are not inspected.
        out.append({"code": "SEC_PERMS_UNCHECKED", "severity": "info",
                    "detail": "POSIX permission bits are not meaningful on Windows; "
                              "ACLs are not inspected - see docs/THREAT-MODEL.md section 7b"})
        mode_checks = []
    else:
        mode_checks = [("graph.json", graph), ("graph directory", directory)]

    for label, target in mode_checks:
        mode = _mode(target)
        if mode is None:
            continue
        if mode & stat.S_IWOTH:
            out.append({"code": "SEC_WORLD_WRITABLE", "severity": "warn",
                        "detail": f"{label} is world-writable (mode {oct(mode)}): "
                                  "any local user can rewrite the memory"})
        elif mode & stat.S_IWGRP:
            out.append({"code": "SEC_GROUP_WRITABLE", "severity": "info",
                        "detail": f"{label} is group-writable (mode {oct(mode)}): "
                                  "everyone in that group can rewrite the memory"})

    normalised = directory.replace(os.sep, "/")
    for prefix in NETWORK_PATH_PREFIXES:
        if normalised.startswith(prefix.replace(os.sep, "/")) or prefix in normalised:
            out.append({"code": "SEC_NETWORK_PATH", "severity": "warn",
                        "detail": f"{directory} looks like a network mount ({prefix}); "
                                  "the advisory lock and the permission boundary do not "
                                  "hold there"})
            break

    return out


def worst(findings_list) -> str:
    """Return "error" / "warn" / "info" / "ok" for a findings list."""
    severities = {f["severity"] for f in findings_list}
    for level in ("error", "warn", "info"):
        if level in severities:
            return level
    return "ok"
