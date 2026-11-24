"""Release notes come from the changelog table (the workflow used to look for a ``## <version>`` heading that the
table-form changelog never has, so every release body was "See v2/CHANGELOG.md")."""

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location("release_notes", ROOT / ".github" / "scripts" / "release_notes.py")
rn = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rn)

TABLE = """# changes

| version | date | PR | summary |
|---|---|---|---|
| 2.60.2 | 2026-11-24 | #78 | **First** change with a filter `\\|b\\| < 20` and a | in text ① two ② three |
| 2.60.1 | 2026-11-24 | #77 | older row |
"""


def test_a_table_row_becomes_notes():
    notes = rn.release_notes("2.60.2", TABLE)
    assert notes.startswith("## Finding Objects v2.60.2")
    assert "2026-11-24, pull request #78" in notes
    assert "`|b| < 20`" in notes and "① two ② three" in notes  # the escaped pipe is restored, the cell is not cut
    assert "older row" not in notes
    assert "blob/v2.60.2/v2/CHANGELOG.md" in notes


def test_the_version_must_match_exactly():
    assert rn.release_notes("2.60", TABLE) == ""
    assert rn.release_notes("2.6.2", TABLE) == ""
    assert rn.release_notes("v2.60.1", TABLE).count("older row") == 1  # a leading v is accepted


def test_a_heading_section_still_wins():
    text = "## 2.61.0 (x)\n\nwritten notes\n\n## 2.60.2 (y)\n\nolder\n\n" + TABLE
    assert rn.release_notes("2.61.0", text) == "## 2.61.0 (x)\n\nwritten notes"


def test_a_version_without_notes_gives_nothing_so_the_workflow_falls_back():
    assert rn.release_notes("9.9.9", TABLE) == ""


def test_the_real_changelog_has_notes_for_the_current_version():
    version = (ROOT / "v2" / "VERSION").read_text().strip()
    notes = rn.release_notes(version, (ROOT / "v2" / "CHANGELOG.md").read_text(encoding="utf-8"))
    assert notes.startswith(f"## Finding Objects v{version}") and len(notes) > 300
