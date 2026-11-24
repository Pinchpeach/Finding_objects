#!/usr/bin/env python3
"""Build ``README.md`` and the overview PDF from one source, ``overview_content.py``.

    python v2/document/build_overview.py                 # README.md + v2/document/OVERVIEW_v<version>.pdf
    python v2/document/build_overview.py --check         # exit 1 if README.md differs from what the content gives
    python v2/document/build_overview.py --no-pdf        # README.md only (no reportlab needed)
    python v2/document/build_overview.py --pdf OUT.pdf --readme OUT.md

Why one source: the 2.36.1 PDF and the README were written by hand twice and drifted (stale figures in both).  Here
the text lives once in ``overview_content.py``; this script renders it as GitHub Markdown and as an A4 PDF, and the
test ``Preprocess/tests/test_overview_docs.py`` fails if the committed README is not the rendering of the content.

The PDF needs ``reportlab`` (``pip install reportlab``) and a TrueType font with the glyphs of the text (DejaVu Sans
is searched for in ``$OVERVIEW_FONT_DIR``, matplotlib's bundled fonts and the usual system folders).  The build
checks every character of the text against the font and stops with the list of missing characters instead of
printing empty boxes (the text uses prime marks, arrows, comparison signs and Greek letters).  Output is
reproducible (reportlab ``invariant`` mode: no creation date inside the file).
"""

from __future__ import annotations

import argparse
import html
import os
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE))
import overview_content as C  # noqa: E402

BLOB = f"{C.REPO}/blob/main/"
TREE = f"{C.REPO}/tree/main/"

# ------------------------------------------------------------------------------------------------ Markdown
README_FOOTER = (
    "*This README and the overview PDF are generated from `v2/document/overview_content.py` by "
    "`v2/document/build_overview.py`. Edit that file, not this one.*"
)


def pdf_name() -> str:
    return f"OVERVIEW_v{C.PROGRAM_VERSION}.pdf"


def _md_cell(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ")


def _md_block(b: dict) -> str:
    k = b["kind"]
    if k == "p":
        return b["text"]
    if k == "h3":
        return f"### {b['text']}"
    if k == "note":
        return "> " + b["text"]
    if k == "ul":
        return "\n".join(f"- {t}" for t in b["items"])
    if k == "code":
        return "```bash\n" + b["text"] + "\n```"
    if k == "table":
        head = "| " + " | ".join(_md_cell(h) for h in b["head"]) + " |"
        sep = "|" + "|".join("---" for _ in b["head"]) + "|"
        rows = ["| " + " | ".join(_md_cell(c) for c in r) + " |" for r in b["rows"]]
        return "\n".join([head, sep] + rows)
    if k == "flow":
        rows = [f"| **{_md_cell(lab)}** | {_md_cell(txt)} |" for lab, txt in b["stages"]]
        return "\n".join(["| Stage | What happens |", "|---|---|"] + rows)
    raise ValueError(k)


def render_markdown() -> str:
    pdf_link = f"v2/document/{pdf_name()}"
    out = [
        f"# {C.TITLE}",
        f"Program version {C.PROGRAM_VERSION} · {C.DATE} · {C.SUBTITLE}",
        f"**Read first:** [Overview PDF, version {C.PROGRAM_VERSION} (English)]({pdf_link}) · "
        f"[Release {C.PROGRAM_VERSION} with Windows, macOS and Linux downloads]({C.RELEASE_URL}) · "
        "[How to run](#12-running-it) · "
        "[Algorithm in detail (Korean)](v2/ALGORITHM.md) · [Changelog (Korean)](v2/CHANGELOG.md)",
    ]
    out.append(
        "The older material is listed in [section 15](#15-other-documents): the 2.36.1 overview (Korean) and the "
        "2.44.0 deck (English) are kept but not updated."
    )
    for sec in C.SECTIONS:
        out.append(f"## {sec['title']}")
        for b in sec["blocks"]:
            if b.get("only") == "pdf":
                continue
            out.append(_md_block(b))
    out.append("---")
    out.append(README_FOOTER)
    return "\n\n".join(out) + "\n"


# ------------------------------------------------------------------------------------------------ PDF
FONT_CANDIDATES = {
    "regular": ["DejaVuSans.ttf"],
    "bold": ["DejaVuSans-Bold.ttf"],
    "mono": ["DejaVuSansMono.ttf"],
    "monobold": ["DejaVuSansMono-Bold.ttf"],
}


def _font_dirs() -> list[Path]:
    dirs = []
    if os.environ.get("OVERVIEW_FONT_DIR"):
        dirs.append(Path(os.environ["OVERVIEW_FONT_DIR"]))
    try:
        import matplotlib

        dirs.append(Path(matplotlib.get_data_path()) / "fonts" / "ttf")
    except Exception:
        pass
    dirs += [
        Path("/usr/share/fonts/truetype/dejavu"),
        Path("/usr/share/fonts/dejavu"),
        Path("/Library/Fonts"),
        Path("/System/Library/Fonts/Supplemental"),
        Path(os.environ.get("WINDIR", "C:\\Windows")) / "Fonts",
    ]
    return [d for d in dirs if d.is_dir()]


def _find_font(names: list[str]) -> Path:
    for d in _font_dirs():
        for n in names:
            if (d / n).is_file():
                return d / n
    raise SystemExit(f"font not found: {names} (set OVERVIEW_FONT_DIR to a folder with the DejaVu Sans fonts)")


def _inline(text: str) -> str:
    """Markdown-ish inline markup -> reportlab paragraph XML (links: relative paths become GitHub URLs)."""
    spans: list[str] = []

    def keep(m):
        spans.append(m.group(1))
        return f"\x00{len(spans) - 1}\x00"

    t = re.sub(r"`([^`]+)`", keep, text)
    t = html.escape(t, quote=False)

    def link(m):
        label, url = m.group(1), m.group(2)
        if not url.startswith("http"):
            url = (TREE if url.endswith("/") else BLOB) + url
        return f'<a href="{url}" color="#1F5FAF">{label}</a>'

    t = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", link, t)
    t = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", t)
    t = re.sub(
        r"\x00(\d+)\x00",
        lambda m: f'<font name="Mono" size="-0.6">{html.escape(spans[int(m.group(1))], quote=False)}</font>',
        t,
    )
    return t


def _text_of_content() -> str:
    parts = [C.TITLE, C.SUBTITLE, C.DATE, C.PROGRAM_VERSION]
    for sec in C.SECTIONS:
        parts.append(sec["title"])
        for b in sec["blocks"]:
            if b.get("only") == "readme":
                continue
            k = b["kind"]
            if k in ("p", "h3", "note", "code"):
                parts.append(b["text"])
            elif k == "ul":
                parts += b["items"]
            elif k == "table":
                parts += b["head"]
                for r in b["rows"]:
                    parts += r
            elif k == "flow":
                for lab, txt in b["stages"]:
                    parts += [lab, txt]
    return "\n".join(parts)


def build_pdf(path: Path) -> int:
    """Write the PDF, return its page count."""
    try:
        from reportlab import rl_config
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_CENTER
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle
        from reportlab.lib.units import mm
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        from reportlab.platypus import (
            BaseDocTemplate,
            CondPageBreak,
            Frame,
            KeepTogether,
            PageTemplate,
            Paragraph,
            Preformatted,
            Spacer,
            Table,
            TableStyle,
        )
    except ImportError as e:  # pragma: no cover
        raise SystemExit(f"reportlab is needed for the PDF: pip install reportlab ({e})")

    rl_config.invariant = 1
    fonts = {k: TTFont(f"Ov-{k}", str(_find_font(v))) for k, v in FONT_CANDIDATES.items()}
    for f in fonts.values():
        pdfmetrics.registerFont(f)
    pdfmetrics.registerFontFamily(
        "Ov-regular", normal="Ov-regular", bold="Ov-bold", italic="Ov-regular", boldItalic="Ov-bold"
    )  # no italics used
    pdfmetrics.registerFontFamily(
        "Mono", normal="Ov-mono", bold="Ov-monobold", italic="Ov-mono", boldItalic="Ov-monobold"
    )
    # <font name="Mono"> inside paragraphs
    pdfmetrics.registerFont(TTFont("Mono", str(_find_font(FONT_CANDIDATES["mono"]))))

    text = _text_of_content()
    missing = sorted(
        {
            ch
            for ch in text
            if ch not in "\n\t" and not all(ord(ch) in f.face.charToGlyph for f in (fonts["regular"], fonts["mono"]))
        }
    )
    if missing:
        raise SystemExit("characters missing from the font: " + " ".join(f"{c} U+{ord(c):04X}" for c in missing))

    blue, light, grid = colors.HexColor("#2B579A"), colors.HexColor("#EAF0F8"), colors.HexColor("#B8C4D6")
    body = ParagraphStyle("body", fontName="Ov-regular", fontSize=8.8, leading=12.2, spaceAfter=4)
    cell = ParagraphStyle("cell", fontName="Ov-regular", fontSize=7.7, leading=9.9)
    cellb = ParagraphStyle("cellb", parent=cell, fontName="Ov-bold", textColor=colors.white)
    h1 = ParagraphStyle(
        "h1", fontName="Ov-bold", fontSize=21, leading=25, spaceAfter=2, textColor=colors.HexColor("#1B2A41")
    )
    sub = ParagraphStyle(
        "sub", fontName="Ov-regular", fontSize=9, leading=12.5, textColor=colors.HexColor("#555555"), spaceAfter=8
    )
    h2 = ParagraphStyle(
        "h2",
        fontName="Ov-bold",
        fontSize=13.5,
        leading=17,
        spaceBefore=11,
        spaceAfter=5,
        textColor=colors.HexColor("#1B2A41"),
    )
    h3 = ParagraphStyle(
        "h3",
        fontName="Ov-bold",
        fontSize=9.8,
        leading=13,
        spaceBefore=6,
        spaceAfter=3,
        textColor=colors.HexColor("#2B579A"),
    )
    bullet = ParagraphStyle("bullet", parent=body, leftIndent=11, bulletIndent=2, spaceAfter=2.5)
    code = ParagraphStyle(
        "code",
        fontName="Ov-mono",
        fontSize=7.3,
        leading=9.4,
        backColor=colors.HexColor("#F3F5F8"),
        borderPadding=(4, 4, 4, 4),
        spaceBefore=3,
        spaceAfter=7,
        leftIndent=4,
    )
    arrow = ParagraphStyle(
        "arrow", fontName="Ov-regular", fontSize=7, leading=8, alignment=TA_CENTER, textColor=colors.HexColor("#2B579A")
    )
    note = ParagraphStyle("note", parent=body, backColor=light, borderPadding=(4, 4, 4, 4), leftIndent=4, rightIndent=4)

    page_w, page_h = A4
    margin = 17 * mm
    avail = page_w - 2 * margin

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont("Ov-regular", 7.3)
        canvas.setFillColor(colors.HexColor("#666666"))
        canvas.drawString(margin, 9 * mm, f"Finding Objects v{C.PROGRAM_VERSION} · program overview ({C.DATE})")
        canvas.drawRightString(page_w - margin, 9 * mm, str(doc.page))
        canvas.restoreState()

    doc = BaseDocTemplate(
        str(path),
        pagesize=A4,
        leftMargin=margin,
        rightMargin=margin,
        topMargin=15 * mm,
        bottomMargin=17 * mm,
        title=f"{C.TITLE} (v{C.PROGRAM_VERSION})",
        author="Finding Objects",
        subject=C.SUBTITLE,
        invariant=1,
    )
    doc.addPageTemplates(
        [
            PageTemplate(
                id="p",
                frames=[
                    Frame(
                        margin,
                        17 * mm,
                        avail,
                        page_h - 32 * mm,
                        id="f",
                        leftPadding=0,
                        rightPadding=0,
                        topPadding=0,
                        bottomPadding=0,
                    )
                ],
                onPage=footer,
            )
        ]
    )

    story = [
        Paragraph(html.escape(C.TITLE), h1),
        Paragraph(_inline(f"Program version {C.PROGRAM_VERSION} · {C.DATE} · {C.SUBTITLE}"), sub),
        Paragraph(
            _inline(
                f"Source, tests and downloads: [{C.REPO}]({C.REPO}) · [Release {C.PROGRAM_VERSION}]({C.RELEASE_URL}). "
                "Algorithm details and the change history are in Korean ([ALGORITHM.md](v2/ALGORITHM.md), "
                "[CHANGELOG.md](v2/CHANGELOG.md))."
            ),
            note,
        ),
        Spacer(1, 4),
    ]

    def make_table(head, rows, widths):
        n = len(head)
        widths = widths or [1.0 / n] * n
        data = [[Paragraph(_inline(h), cellb) for h in head]] + [[Paragraph(_inline(c), cell) for c in r] for r in rows]
        t = Table(data, colWidths=[w * avail for w in widths], repeatRows=1)
        style = [
            ("BACKGROUND", (0, 0), (-1, 0), blue),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("GRID", (0, 0), (-1, -1), 0.4, grid),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 2.6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2.8),
        ]
        for i in range(2, len(data), 2):
            style.append(("BACKGROUND", (0, i), (-1, i), colors.HexColor("#F6F8FB")))
        t.setStyle(TableStyle(style))
        return t

    def make_flow(stages):
        data, style = [], [
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ]
        for i, (lab, txt) in enumerate(stages):
            r = len(data)
            data.append([Paragraph(f"<b>{html.escape(lab)}</b>", cell), Paragraph(_inline(txt), cell)])
            style += [
                ("BACKGROUND", (0, r), (0, r), light),
                ("BOX", (0, r), (0, r), 0.6, blue),
                ("LINEBELOW", (1, r), (1, r), 0.4, grid),
                ("TOPPADDING", (0, r), (-1, r), 3.5),
                ("BOTTOMPADDING", (0, r), (-1, r), 3.5),
            ]
            if i < len(stages) - 1:
                data.append([Paragraph("▼", arrow), ""])
                a = len(data) - 1
                style += [("TOPPADDING", (0, a), (-1, a), 0), ("BOTTOMPADDING", (0, a), (-1, a), 0)]
        t = Table(data, colWidths=[0.17 * avail, 0.83 * avail])
        t.setStyle(TableStyle(style))
        return t

    for sec in C.SECTIONS:
        first = True
        for b in sec["blocks"]:
            if b.get("only") == "readme":
                continue
            k = b["kind"]
            if k == "p":
                el = [Paragraph(_inline(b["text"]), body)]
            elif k == "h3":
                el = [Paragraph(_inline(b["text"]), h3)]
            elif k == "note":
                el = [Paragraph(_inline(b["text"]), note)]
            elif k == "ul":
                el = [Paragraph(_inline(t), bullet, bulletText="•") for t in b["items"]]
            elif k == "code":
                el = [Preformatted(b["text"], code)]
            elif k == "table":
                el = [make_table(b["head"], b["rows"], b["widths"]), Spacer(1, 5)]
            elif k == "flow":
                el = [make_flow(b["stages"]), Spacer(1, 5)]
            else:  # pragma: no cover
                raise ValueError(k)
            if first:  # a heading never ends a page: start a new page if little room is left
                story += [CondPageBreak(55 * mm), Paragraph(_inline(sec["title"]), h2)] + el
                first = False
            else:
                if k == "h3":
                    story.append(CondPageBreak(38 * mm))
                story += el
    doc.build(story)
    return doc.page if hasattr(doc, "page") else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--readme", type=Path, default=ROOT / "README.md")
    ap.add_argument("--pdf", type=Path, default=HERE / pdf_name())
    ap.add_argument("--no-pdf", action="store_true")
    ap.add_argument("--check", action="store_true", help="only compare README.md with the rendering; write nothing")
    a = ap.parse_args()
    md = render_markdown()
    if a.check:
        cur = a.readme.read_text(encoding="utf-8") if a.readme.exists() else ""
        if cur != md:
            print(f"{a.readme} is not the rendering of overview_content.py: run python v2/document/build_overview.py")
            return 1
        print("README.md matches overview_content.py")
        return 0
    a.readme.write_text(md, encoding="utf-8")
    print(f"wrote {a.readme}")
    if not a.no_pdf:
        pages = build_pdf(a.pdf)
        print(f"wrote {a.pdf} ({pages} pages)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
