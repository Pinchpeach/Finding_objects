"""README.md and the overview PDF come from one source (``v2/document/overview_content.py``).

The 2.36.1 PDF and the README were written by hand twice and drifted.  These tests keep them from drifting again:
the committed README must be the rendering of the content, the counts the text states (collectors, rules, summary
columns) must equal what the code has, relative links must resolve, the English documents must contain no Hangul, and
the PDF must build with every glyph of the text present in the font.
"""

import re
import sys
from pathlib import Path

import pytest

V2 = Path(__file__).resolve().parents[2]
ROOT = V2.parent
DOC = V2 / "document"
sys.path.insert(0, str(DOC))
sys.path.insert(0, str(V2 / "Get_data"))
sys.path.insert(0, str(V2))
import build_overview as B  # noqa: E402
import overview_content as C  # noqa: E402


def test_readme_is_the_rendering_of_the_content():
    assert (ROOT / "README.md").read_text(
        encoding="utf-8"
    ) == B.render_markdown(), "README.md is out of date: run python v2/document/build_overview.py"


def test_documents_are_english_only():
    # the project's other documents are Korean; the README and the overview are English by decision (2026-11-24)
    text = B.render_markdown() + B._text_of_content()
    assert not re.search(r"[가-힣]", text)


def test_counts_in_the_text_match_the_code():
    import csv

    import controller
    import summary

    md = B.render_markdown()
    assert f"**{len(controller.COLLECTORS)} public archives**" in md
    assert f"{len(controller.COLLECTORS)} collectors" in md
    rules = list(csv.DictReader(open(V2 / "Preprocess" / "classification_rules.csv", encoding="utf-8")))
    assert "35 rows of `v2/Preprocess/classification_rules.csv`" in md and len(rules) == 35
    assert f"{len(summary.COLUMNS)} columns to read first" in md


def test_relative_links_resolve():
    md = B.render_markdown()
    bad = []
    for target in re.findall(r"\]\(([^)]+)\)", md):
        if target.startswith(("http", "#")):
            continue
        if not (ROOT / target.rstrip("/")).exists():
            bad.append(target)
    assert not bad, bad


def test_the_pdf_named_in_the_readme_is_committed():
    assert (DOC / B.pdf_name()).is_file()
    assert f"v2/document/{B.pdf_name()}" in B.render_markdown()


def test_every_block_kind_is_rendered():
    kinds = {b["kind"] for s in C.SECTIONS for b in s["blocks"]}
    assert kinds <= {"p", "ul", "table", "flow", "code", "h3", "note"}
    assert all(
        len(r) == len(b["head"]) for s in C.SECTIONS for b in s["blocks"] if b["kind"] == "table" for r in b["rows"]
    )


def test_pdf_builds_with_all_glyphs(tmp_path):
    pytest.importorskip("reportlab")
    out = tmp_path / "overview.pdf"
    try:
        pages = B.build_pdf(out)
    except SystemExit as e:
        if "font not found" in str(e):
            pytest.skip(str(e))
        raise
    assert 6 <= pages <= 14
    pypdf = pytest.importorskip("pypdf")
    text = " ".join(p.extract_text() for p in pypdf.PdfReader(str(out)).pages)
    for needle in ("99.65 %", "29/119", "93.79 %", "35 rows", "UNCONFIRMED", "10σ", "12′", "1.0″", "≥"):
        assert needle in text, needle
