#!/usr/bin/env python3
"""Release notes for a version from ``v2/CHANGELOG.md`` (used by the "Publish release" step of build-app.yml).

    python3 .github/scripts/release_notes.py VERSION [CHANGELOG]      # prints the notes, nothing if there are none

The changelog is a table (one row per version: ``| version | date | PR | summary |``), but the workflow used to look
for a ``## <version>`` heading, so every release body fell back to "See v2/CHANGELOG.md" (v2.60.2 included).  This
script keeps the heading form working (a ``## <version> `` section is returned as is) and otherwise turns the table
row of the version into the notes: a title line, date and pull request, the summary, and a link to the full history.
The summary stays in the changelog's language (Korean); the release page is the place for the downloads, and the
English overview is linked in the notes.

Past releases are not touched; the notes only apply to the next ``gh release create``.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO = "https://github.com/Pinchpeach/Finding_objects"


def _section(version: str, text: str) -> str:
    """The ``## <version> ...`` section (up to the next ``## `` heading), or ''."""
    out, on = [], False
    for line in text.splitlines():
        if re.match(rf"^## {re.escape(version)}\b", line):
            on = True
            out.append(line)
        elif on and line.startswith("## "):
            break
        elif on:
            out.append(line)
    return "\n".join(out).strip()


def _row(version: str, text: str) -> str:
    """The table row ``| version | date | PR | summary |`` of the version as notes, or ''."""
    for line in text.splitlines():
        if not line.startswith("|"):
            continue
        # maxsplit: the summary cell holds escaped pipes (\|b\|) and must not be cut
        cells = line.split("|", 4)
        if len(cells) < 5 or cells[1].strip() != version:
            continue
        date, pr = cells[2].strip(), cells[3].strip()
        summary = cells[4].rstrip().removesuffix("|").strip().replace("\\|", "|")
        head = f"## Finding Objects v{version}"
        meta = ", ".join(x for x in (date, f"pull request {pr}" if pr.startswith("#") else pr) if x)
        tail = (
            f"Full change history (Korean): [v2/CHANGELOG.md]({REPO}/blob/v{version}/v2/CHANGELOG.md). "
            f"English overview of this version: [README]({REPO}/blob/v{version}/README.md)."
        )
        return f"{head}\n\n{meta}\n\n{summary}\n\n{tail}"
    return ""


def release_notes(version: str, changelog_text: str) -> str:
    version = version.strip().lstrip("v")
    return _section(version, changelog_text) or _row(version, changelog_text)


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 2
    path = Path(argv[1]) if len(argv) > 1 else Path("v2/CHANGELOG.md")
    notes = release_notes(argv[0], path.read_text(encoding="utf-8"))
    if notes:
        print(notes)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
