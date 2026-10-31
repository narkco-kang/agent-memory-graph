#!/usr/bin/env python3
"""One definition of "a document" for the documentation gates.

v0.31.0. Until this module existed, both gates selected files with
`name.endswith(".md")`. A gate that selects by file *name* is bypassed by renaming a
file: the independent verifier measured `docs/n/A.markdown` (30,000 B),
`docs/n/B.txt` (30,000 B) and `docs/n/NOEXT` (30,000 B) all passing both gates on
v0.30.0, and a 30 KB `.markdown` page documenting `amg teleport` passing the symbol
gate. The content was exactly as wrong as a `.md` file's; only the suffix differed.

So the scope is the **directory**, not the suffix: every regular file under `docs/`
is a document, plus the repository `README.md`. That is a rule about where documents
live, not about what they are called, so no rename can escape it.

Two consequences, stated rather than discovered later:

  * a large binary asset does not belong under `docs/` — put it outside the document
    tree, because the budget applies to bytes regardless of content type;
  * `CHANGELOG.md` and `RELEASE.md` stay out of scope by name in the callers, and
    they live at the repository root, not under `docs/`, so this walk never sees them.

Both gates import this module instead of each copying the walk: the v0.30.0 extension
bug was one design copied twice, so the fix is one implementation used twice.
"""
import os

ENTRY_DOCUMENT = "README.md"


def document_files(root):
    """Repository README plus every regular file under `docs/`, recursively.

    Returns POSIX-style relative paths sorted for stable, platform-identical output.
    Directory symlinks are not followed (`os.walk` default), so the walk cannot loop;
    a file symlink is included, because following it reads content the same way a
    plain file's content is read — excluding it would be a one-command bypass.
    """
    targets = [ENTRY_DOCUMENT]
    docs_dir = os.path.join(root, "docs")
    for current, dirs, names in os.walk(docs_dir):
        dirs.sort()
        for name in sorted(names):
            full = os.path.join(current, name)
            if not os.path.isfile(full):
                continue
            rel = os.path.relpath(full, root)
            targets.append(rel.replace(os.sep, "/"))
    return sorted(targets)
