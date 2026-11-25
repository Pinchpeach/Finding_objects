"""The 12-slide deck (``v2/document/PIPELINE_STACK_v<version>.pptx`` / ``.pdf``) is generated and cannot go stale.

The v2.44.0 deck was drawn by hand and kept its figures (29 archives, 36 + 2 rules and models, 99.16 %, 141 tests)
long after they were wrong.  These tests tie the new deck to the code and to the overview: slide count, language,
no stale headline figure, counts equal to the code, every percentage and large count also present in the overview,
and the committed PPTX / PDF are what the generator produces from the current text.
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
import deck_content as D  # noqa: E402
import overview_content as C  # noqa: E402

STALE = ("29 archives", "29 Archives", "36 + 2", "36 literature", "99.16", "141 tests")


def _plain(text: str) -> str:
    return text.replace("**", "").replace("`", "")


def _slide_texts(path) -> list[str]:
    pptx = pytest.importorskip("pptx")
    out = []
    for slide in pptx.Presentation(str(path)).slides:
        parts = []
        for shape in slide.shapes:
            if shape.has_text_frame:
                parts.append(shape.text_frame.text)
            if getattr(shape, "has_table", False) and shape.has_table:
                parts += [c.text_frame.text for r in shape.table.rows for c in r.cells]
        out.append("\n".join(parts))
    return out


def test_deck_text_is_english_and_has_no_stale_headline_figures():
    text = D.all_text()
    assert not re.search(r"[가-힣]", text)
    for needle in STALE:
        assert needle not in text, needle
    assert D.PROGRAM_VERSION == C.PROGRAM_VERSION


def test_deck_counts_match_the_code():
    import csv

    import controller
    import summary

    text = _plain(D.all_text())
    n = len(controller.COLLECTORS)
    assert f"{n} public archives" in text and f"{n} collectors" in text
    rules = list(csv.DictReader(open(V2 / "Preprocess" / "classification_rules.csv", encoding="utf-8")))
    assert f"{len(rules)} rows of v2/Preprocess/classification_rules.csv" in text
    assert sum(int(r[1]) for r in D.FUSION["rules_rows"]) == len(rules)
    assert (str(len(summary.COLUMNS)), "columns to read first") == D.GLANCE["tiles"][3][:2]
    # the stack named on the last slide is the stack of the repository
    req = (V2 / "app" / "requirements.txt").read_text().lower()
    for pkg in ("pyside6", "pandas", "numpy", "scipy", "astropy", "astroquery", "pyvo", "requests"):
        assert pkg in req and pkg in text.lower(), pkg
    assert "pyinstaller" in (V2 / "app" / "packaging" / "requirements-build.txt").read_text().lower()
    assert '"sklearn"' in (V2 / "app" / "packaging" / "finding_objects.spec").read_text()  # excluded from the build
    for path, _ in D.STACK["map_rows"]:
        assert list(ROOT.glob(path)) if "*" in path else (ROOT / path).is_dir(), path
    for _, _, module, _, _ in D.PIPELINE["stages"][:7]:
        hits = [p for p in (V2 / "Preprocess", V2) if (p / f"{module}.py").is_file() or (p / module).is_file()]
        assert hits, module


def test_every_figure_of_the_deck_is_in_the_overview():
    """Percentages and counts of a thousand or more are not typed twice: each must occur in the overview text."""
    overview = _plain(B.render_markdown())
    deck = _plain(D.all_text())
    missing = [f"{m} %" for m in set(re.findall(r"(\d+(?:\.\d+)?) %", deck)) if f"{m} %" not in overview]
    missing += [m for m in set(re.findall(r"\d{1,3}(?:,\d{3})+", deck)) if m not in overview]
    assert not missing, sorted(missing)
    # the limits must be on the slides, not only the results
    for needle in (
        "not an all-wavelength classifier",
        "29/119",
        "47/97",
        "0 of 33",
        "Not representative",
        "Development sets",
    ):
        assert needle in deck, needle


def test_ablation_chart_uses_the_overview_table():
    rows = D.overview_table("4.", "Switched off")["rows"]
    assert [(r[0], r[1], r[2]) for r in rows] == D.DECIDES["rows"] and len(D.DECIDES["readings"]) == len(rows)
    assert D.DECIDES["rows"][-1] == ("X-ray and radio", "0 / 0", "0 / 0")


def test_deck_files_are_committed_and_linked_from_the_readme():
    md = B.render_markdown()
    for suffix in (".pptx", ".pdf", "_preview.png"):
        assert (DOC / f"{C.DECK_STEM}{suffix}").is_file(), suffix
    assert f"v2/document/{C.DECK_STEM}.pdf" in md and f"v2/document/{C.DECK_STEM}.pptx" in md


def test_pptx_builds_reproducibly_and_matches_the_committed_file(tmp_path):
    pytest.importorskip("pptx")
    import build_deck

    a, b = tmp_path / "a.pptx", tmp_path / "b.pptx"
    assert build_deck.build_pptx(a) == D.N_SLIDES == 12
    build_deck.build_pptx(b)
    assert a.read_bytes() == b.read_bytes()
    fresh = _slide_texts(a)
    assert len(fresh) == 12
    assert fresh == _slide_texts(
        DOC / build_deck.pptx_name()
    ), "deck is out of date: run python v2/document/build_deck.py"
    joined = "\n".join(fresh)
    for needle in STALE:
        assert needle not in joined, needle
    for needle in ("99.65 %", "93.79 %", "30 collectors", "INFERRED", "--retry-failed", "PyInstaller"):
        assert needle in joined, needle


def test_committed_pdf_has_the_same_slides_and_all_glyphs():
    pypdf = pytest.importorskip("pypdf")
    pages = pypdf.PdfReader(str(DOC / f"{C.DECK_STEM}.pdf")).pages
    assert len(pages) == 12
    text = [re.sub(r"\s+", " ", p.extract_text()) for p in pages]
    titles = [
        X["title"]
        for X in (
            D.TITLE,
            D.GLANCE,
            D.PIPELINE,
            D.SOURCES,
            D.DECIDES,
            D.FUSION,
            D.PROVENANCE,
            D.VALIDATION,
            D.PERFORMANCE,
            D.FAINT,
            D.OPERATION,
            D.STACK,
        )
    ]
    for i, title in enumerate(titles):
        assert title in text[i], (i + 1, title)
    joined = " ".join(text)
    for needle in ("12′", "10σ", "≥", "≤", "3.5°", "→", "−40°", "“QSO?”", "99.65 %", "29/119"):
        assert needle in joined, needle
    assert not re.search(r"[가-힣]", joined)
