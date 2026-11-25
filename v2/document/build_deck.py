#!/usr/bin/env python3
"""Build the 12-slide "pipeline and tech stack" deck from ``deck_content.py``.

    python v2/document/build_deck.py                 # PIPELINE_STACK_v<version>.pptx, .pdf and _preview.png
    python v2/document/build_deck.py --no-pdf        # PPTX only (no LibreOffice needed)
    python v2/document/build_deck.py --out DIR       # write somewhere else (the tests do)

Why a generator: the v2.44.0 deck was drawn by hand in LibreOffice Impress and could not be rebuilt, so its figures
went stale (29 archives, 36 + 2 rules and models, 99.16 %, 141 tests).  Here the text lives in ``deck_content.py``
(which reads the overview's own tables), this script only draws, and ``Preprocess/tests/test_deck.py`` checks the
result against the code and the overview.

How it draws
* PPTX with ``python-pptx`` (``pip install python-pptx``): native text boxes, shapes and tables, so the slides stay
  editable.  The two charts (rule ablation, type-1 AGN recall) are drawn as native rectangles from the numbers of
  the content, not pasted pictures.
* PDF by converting that PPTX with LibreOffice headless (``soffice``), so both files show the same slides.  The
  preview PNG is page 1 of the PDF (``pdftoppm``).
* Font: Arial.  It exists on Windows and macOS, and LibreOffice on Linux substitutes the metric-compatible
  Liberation Sans, so line breaks are the same in PowerPoint and in the PDF (the old deck used Inter, which most
  PCs lack).  Both fonts have the glyphs the text needs (prime marks, ≥, σ, °, →); the test checks the PDF text.
* The PPTX is reproducible: fixed document dates and fixed zip timestamps.  The PDF carries LibreOffice's
  creation time and is not byte-reproducible.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import deck_content as D  # noqa: E402

from pptx import Presentation  # noqa: E402
from pptx.dml.color import RGBColor  # noqa: E402
from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE  # noqa: E402
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN  # noqa: E402
from pptx.oxml.ns import qn  # noqa: E402
from pptx.util import Emu, Inches, Pt  # noqa: E402

# ------------------------------------------------------------------------------------------------ design tokens
W, H = 13.333, 7.5  # inches, 16:9
MX = 0.6  # side margin
FONT = "Arial"
MONO = "Courier New"
INK = RGBColor(0x19, 0x19, 0x19)
INK2 = RGBColor(0x5F, 0x5F, 0x5F)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
CARD = RGBColor(0xF3, 0xF3, 0xF1)
LINE = RGBColor(0xD9, 0xD9, 0xD6)
DARK = RGBColor(0x26, 0x26, 0x2B)
DARK_TEXT2 = RGBColor(0xC8, 0xC8, 0xCC)
# two chart colours: slots 1 and 2 of the validated colour-blind-safe default palette (blue, orange); every bar
# also carries its number, so colour is never the only carrier
BLUE = RGBColor(0x25, 0x7D, 0xE0)
ORANGE = RGBColor(0xF4, 0x72, 0x30)
BLUE_TINT = RGBColor(0xE4, 0xEF, 0xFB)
GREY_BAR = RGBColor(0xC9, 0xC9, 0xC6)


def pdf_name() -> str:
    return f"{D.C.DECK_STEM}.pdf"


def pptx_name() -> str:
    return f"{D.C.DECK_STEM}.pptx"


def preview_name() -> str:
    return f"{D.C.DECK_STEM}_preview.png"


# ------------------------------------------------------------------------------------------------ primitives
_TOKEN = re.compile(r"(\*\*.+?\*\*|`.+?`)")


def _runs(par, text, size, color, bold=False, font=FONT):
    """Write ``text`` with **bold** and `code` markup into paragraph ``par``."""
    for part in _TOKEN.split(text):
        if not part:
            continue
        b, f, t = bold, font, part
        if part.startswith("**"):
            b, t = True, part[2:-2]
        elif part.startswith("`"):
            f, t = MONO, part[1:-1]
        r = par.add_run()
        r.text = t
        r.font.size = Pt(size * 0.94 if f == MONO else size)
        r.font.bold = b
        r.font.name = f
        r.font.color.rgb = color


def text(
    slide, x, y, w, h, body, size=14, color=INK, bold=False, align="l", anchor="t", spacing=1.08, bullets=False, gap=4
):
    """A text box.  ``body`` is a string (``\\n`` = new paragraph) or a list of paragraphs."""
    box = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = box.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    tf.vertical_anchor = {"t": MSO_ANCHOR.TOP, "m": MSO_ANCHOR.MIDDLE, "b": MSO_ANCHOR.BOTTOM}[anchor]
    paras = body if isinstance(body, (list, tuple)) else body.split("\n")
    for i, ptxt in enumerate(paras):
        par = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        par.alignment = {"l": PP_ALIGN.LEFT, "c": PP_ALIGN.CENTER, "r": PP_ALIGN.RIGHT}[align]
        par.line_spacing = spacing
        if i:
            par.space_before = Pt(gap)
        if bullets:
            _bullet(par, size)
        _runs(par, ptxt, size, color, bold)
    return box


def _bullet(par, size):
    """A real hanging bullet (python-pptx has no API for it)."""
    pPr = par._p.get_or_add_pPr()
    ind = int(Pt(size * 0.95))
    pPr.set("marL", str(ind))
    pPr.set("indent", str(-ind))
    for tag, attrs in (("a:buFont", {"typeface": FONT}), ("a:buChar", {"char": "•"})):
        el = pPr.makeelement(qn(tag), attrs)
        pPr.append(el)


def rect(slide, x, y, w, h, fill=CARD, line=None, rounded=True, radius=0.08, dash=False, line_w=1.0):
    shape = slide.shapes.add_shape(
        MSO_SHAPE.ROUNDED_RECTANGLE if rounded else MSO_SHAPE.RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h)
    )
    if rounded:
        shape.adjustments[0] = min(0.5, radius / max(min(w, h), 1e-6))
    if fill is None:
        shape.fill.background()
    else:
        shape.fill.solid()
        shape.fill.fore_color.rgb = fill
    if line is None:
        shape.line.fill.background()
    else:
        shape.line.color.rgb = line
        shape.line.width = Pt(line_w)
        if dash:
            ln = shape.line._get_or_add_ln()
            ln.append(ln.makeelement(qn("a:prstDash"), {"val": "dash"}))
    _plain(shape)
    return shape


def _plain(shape):
    """Remove the theme style reference (it adds a drop shadow that LibreOffice draws even on hairlines)."""
    style = shape._element.find(qn("p:style"))
    if style is not None:
        shape._element.remove(style)


def arrow(slide, x1, y1, x2, y2, color=INK2, width=1.25):
    c = slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, Inches(x1), Inches(y1), Inches(x2), Inches(y2))
    c.line.color.rgb = color
    c.line.width = Pt(width)
    ln = c.line._get_or_add_ln()
    ln.append(ln.makeelement(qn("a:tailEnd"), {"type": "triangle", "w": "med", "len": "med"}))
    _plain(c)
    return c


def table(slide, x, y, w, head, rows, widths, size=11, head_size=None, row_h=0.3, pad=0.07, head_h=0.36):
    """A native table with the deck's own look (dark header, hairlines between rows, no theme style)."""
    n_r, n_c = len(rows) + 1, len(head)
    frame = slide.shapes.add_table(n_r, n_c, Inches(x), Inches(y), Inches(w), Inches(head_h + row_h * (n_r - 1)))
    tbl = frame.table
    # drop the theme's banded style: every cell is filled explicitly below
    tblPr = tbl._tbl.tblPr
    tblPr.set("firstRow", "0")
    tblPr.set("bandRow", "0")
    for el in tblPr.findall(qn("a:tableStyleId")):
        tblPr.remove(el)
    total = sum(widths)
    for i, f in enumerate(widths):
        tbl.columns[i].width = Emu(int(Inches(w) * f / total))
    for r in range(n_r):
        tbl.rows[r].height = Inches(row_h if r else head_h)
        for c in range(n_c):
            cell = tbl.cell(r, c)
            cell.margin_left = cell.margin_right = Inches(pad * 1.4)
            cell.margin_top = cell.margin_bottom = Inches(pad)
            cell.vertical_anchor = MSO_ANCHOR.MIDDLE
            cell.fill.solid()
            cell.fill.fore_color.rgb = DARK if r == 0 else (WHITE if r % 2 else CARD)
            _cell_borders(cell)
            tf = cell.text_frame
            tf.word_wrap = True
            body = head[c] if r == 0 else rows[r - 1][c]
            for i, ptxt in enumerate(body.split("\n")):
                par = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
                par.line_spacing = 1.05
                if r == 0:
                    _runs(par, ptxt, head_size or size, WHITE, bold=True)
                else:
                    _runs(par, ptxt, size, INK)
    return frame


def _cell_borders(cell):
    tcPr = cell._tc.get_or_add_tcPr()
    for tag in ("a:lnL", "a:lnR", "a:lnT", "a:lnB"):
        ln = tcPr.makeelement(qn(tag), {"w": "0"})
        ln.append(ln.makeelement(qn("a:noFill"), {}))
        tcPr.append(ln)


def chrome(prs, n, section, title, lede):
    """A blank slide with the section label, title, lede line and footer."""
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    text(slide, MX, 0.42, 6, 0.3, section.upper(), size=11, color=INK2, bold=True)
    text(slide, MX, 0.72, W - 2 * MX, 0.7, title, size=32, bold=True)
    text(slide, MX, 1.42, W - 2 * MX, 0.4, lede, size=15, color=INK2)
    footer(slide, n)
    return slide


def footer(slide, n):
    text(slide, MX, H - 0.42, 5, 0.25, D.FOOTER, size=9.5, color=INK2)
    text(slide, W / 2 - 1, H - 0.42, 2, 0.25, f"{n} / {D.N_SLIDES}", size=9.5, color=INK2, align="c")
    text(slide, W - MX - 3, H - 0.42, 3, 0.25, D.DATE, size=9.5, color=INK2, align="r")


def card(slide, x, y, w, h, title, body, title_size=15, size=12.5, fill=CARD, bullets=False, pad=0.2):
    dark = fill == DARK
    rect(slide, x, y, w, h, fill=fill)
    top = y + pad
    if title:
        text(slide, x + pad, top, w - 2 * pad, 0.3, title, size=title_size, bold=True, color=WHITE if dark else INK)
        top += title_size / 72 * 1.25 + 0.1
    text(
        slide,
        x + pad,
        top,
        w - 2 * pad,
        y + h - pad - top,
        body,
        size=size,
        color=DARK_TEXT2 if dark else INK,
        bullets=bullets,
        gap=5,
    )


# ------------------------------------------------------------------------------------------------ slides
def slide_title(prs):
    T = D.TITLE
    s = prs.slides.add_slide(prs.slide_layouts[6])
    text(s, MX, 0.7, 7.2, 0.3, T["kicker"], size=12, color=INK2, bold=True)
    text(s, MX, 1.35, 7.2, 1.0, T["title"], size=54, bold=True)
    text(s, MX, 2.5, 6.9, 1.2, T["subtitle"], size=22, color=INK, spacing=1.12)
    rect(s, MX, 4.25, 6.9, 2.05, fill=DARK, radius=0.12)
    text(s, MX + 0.35, 4.25, 6.2, 2.05, T["card"], size=17, color=WHITE, anchor="m", spacing=1.18)

    # right: the bands collected, coloured by whether they decide the coarse class
    bx, bw = 8.25, 4.45
    text(s, bx, 0.7, bw, 0.3, T["bands_title"], size=14, bold=True)
    y, bh, gap = 1.15, 0.64, 0.1
    for label, detail, decides in T["bands"]:
        rect(s, bx, y, bw, bh, fill=BLUE if decides else CARD, line=None if decides else LINE)
        text(s, bx + 0.2, y, 1.5, bh, label, size=14, bold=True, color=WHITE if decides else INK, anchor="m")
        text(s, bx + 1.72, y, bw - 1.85, bh, detail, size=11, color=WHITE if decides else INK2, anchor="m")
        y += bh + gap
    y += 0.08
    rect(s, bx, y + 0.03, 0.2, 0.2, fill=BLUE, radius=0.03)
    text(s, bx + 0.3, y, 2.2, 0.26, T["legend_yes"], size=11, anchor="m")
    rect(s, bx, y + 0.35, 0.2, 0.2, fill=CARD, line=LINE, radius=0.03)
    text(s, bx + 0.3, y + 0.32, 3.5, 0.26, T["legend_no"], size=11, anchor="m")
    text(s, bx, y + 0.75, bw, 0.6, T["bands_note"], size=11, color=INK2)
    footer(s, 1)


def slide_glance(prs):
    G = D.GLANCE
    s = chrome(prs, 2, G["section"], G["title"], G["lede"])
    n = len(G["tiles"])
    gap = 0.2
    tw = (W - 2 * MX - gap * (n - 1)) / n
    for i, (num, label, detail) in enumerate(G["tiles"]):
        x = MX + i * (tw + gap)
        rect(s, x, 2.0, tw, 1.45, fill=CARD)
        text(s, x + 0.2, 2.08, 1.2, 0.7, num, size=38, bold=True)
        text(s, x + 1.25, 2.2, tw - 1.4, 0.5, label, size=14, bold=True, anchor="m")
        text(s, x + 0.2, 2.82, tw - 0.4, 0.55, detail, size=11, color=INK2)
    cw = (W - 2 * MX - gap) / 2
    card(s, MX, 3.65, cw, 3.2, G["is_title"], G["is_items"], size=12.5, bullets=True)
    card(s, MX + cw + gap, 3.65, cw, 3.2, G["not_title"], G["not_items"], size=12, fill=DARK, bullets=True)


def slide_pipeline(prs):
    P = D.PIPELINE
    s = chrome(prs, 3, P["section"], P["title"], P["lede"])
    cols, gap = 4, 0.42
    bw = (W - 2 * MX - gap * (cols - 1)) / cols
    bh, y0, vgap = 1.86, 2.0, 0.44
    for i, (num, name, module, body, hot) in enumerate(P["stages"]):
        r, c = divmod(i, cols)
        x, y = MX + c * (bw + gap), y0 + r * (bh + vgap)
        rect(s, x, y, bw, bh, fill=BLUE_TINT if hot else CARD, line=BLUE if hot else None, line_w=1.75)
        text(s, x + 0.18, y + 0.14, 0.9, 0.25, num, size=11, color=INK2, bold=True)
        text(s, x + 0.18, y + 0.36, bw - 0.36, 0.35, name, size=17, bold=True)
        text(s, x + 0.18, y + 0.72, bw - 0.36, 0.22, module, size=9.5, color=INK2)
        text(s, x + 0.18, y + 1.0, bw - 0.36, bh - 1.08, body, size=11)
        if hot:
            text(s, x, y + bh + 0.04, bw, 0.25, P["highlight_label"], size=10.5, bold=True, color=BLUE, align="c")
        if c < cols - 1:
            arrow(s, x + bw + 0.06, y + bh / 2, x + bw + gap - 0.06, y + bh / 2)
    # the turn from the first row to the second
    xr, xl, ym = W - MX - bw / 2, MX + bw / 2, y0 + bh + 0.15
    rect(s, xr - 0.008, y0 + bh + 0.03, 0.016, ym - y0 - bh - 0.03, fill=INK2, rounded=False)
    rect(s, xl - 0.008, ym - 0.008, xr - xl + 0.016, 0.016, fill=INK2, rounded=False)
    arrow(s, xl, ym, xl, y0 + bh + vgap - 0.03)
    rect(s, MX, 6.48, W - 2 * MX, 0.5, fill=None, line=LINE)
    text(s, MX + 0.2, 6.48, W - 2 * MX - 0.4, 0.5, P["outputs"], size=10.5, anchor="m")


def slide_sources(prs):
    S = D.SOURCES
    s = chrome(prs, 4, S["section"], S["title"], S["lede"])
    t = S["table"]
    table(s, MX, 1.98, W - 2 * MX, t["head"], t["rows"], [0.15, 0.43, 0.42], size=11, row_h=0.4, pad=0.045)
    text(s, MX, 6.48, W - 2 * MX, 0.5, S["note"], size=11, color=INK2)


def _pair(cell: str) -> tuple[int, int]:
    a, b = cell.split("/")
    return int(a.strip().replace(",", "")), int(b.strip().replace(",", ""))


def slide_decides(prs):
    X = D.DECIDES
    s = chrome(prs, 5, X["section"], X["title"], X["lede"])
    # columns: group | bright bars | cosmos bars | reading
    cx = [MX, 3.15, 6.0, 9.35]
    cw = [2.45, 2.65, 3.15, W - MX - 9.35]
    y = 2.0
    for i, h in enumerate(X["head"]):
        text(s, cx[i], y, cw[i], 0.3, h, size=11.5, bold=True, color=INK2)
    y += 0.36
    rh = 0.44
    pairs = [(_pair(b), _pair(c)) for _, b, c in X["rows"]]
    for col in (0, 1):
        peak = max(sum(p[col]) for p in pairs) or 1
        num_w = 1.05  # room for "935 / 1,895"
        bar_w = cw[col + 1] - num_w - 0.15
        for r, p in enumerate(pairs):
            right, wrong = p[col]
            yy = y + r * rh
            x0 = cx[col + 1]
            text(
                s,
                x0,
                yy,
                num_w - 0.1,
                rh,
                f"{right:,} / {wrong:,}",
                size=12,
                anchor="m",
                bold=(right + wrong == 0 and r == len(pairs) - 1),
            )
            bx = x0 + num_w
            rect(s, bx - 0.012, yy + 0.07, 0.012, rh - 0.14, fill=INK2, rounded=False)  # baseline
            # same order as the numbers: "right" (orange) first, then "wrong" (blue), with a small gap between
            wr = max(bar_w * right / peak, 0.03) if right else 0.0
            ww = max(bar_w * wrong / peak, 0.03) if wrong else 0.0
            if right:
                rect(s, bx, yy + 0.11, wr, rh - 0.22, fill=ORANGE, rounded=False)
            if wrong:
                rect(s, bx + (wr + 0.025 if right else 0), yy + 0.11, ww, rh - 0.22, fill=BLUE, rounded=False)
    for r, ((name, _, _), reading) in enumerate(zip(X["rows"], X["readings"])):
        yy = y + r * rh
        last = r == len(pairs) - 1
        if r:
            rect(s, MX, yy - 0.004, W - 2 * MX, 0.008, fill=LINE, rounded=False)
        text(s, cx[0], yy, cw[0], rh, name, size=13, bold=True, anchor="m")
        text(s, cx[3], yy, cw[3], rh, reading, size=11.5, color=INK if last else INK2, anchor="m")
    yl = y + len(pairs) * rh + 0.14
    rect(s, cx[1], yl + 0.04, 0.2, 0.17, fill=ORANGE, rounded=False)
    text(s, cx[1] + 0.28, yl, 3.0, 0.25, X["legend_right"], size=10.5, anchor="m")
    rect(s, cx[1] + 3.2, yl + 0.04, 0.2, 0.17, fill=BLUE, rounded=False)
    text(s, cx[1] + 3.48, yl, 5.0, 0.25, X["legend_wrong"], size=10.5, anchor="m")
    text(s, cx[1], yl + 0.28, 9, 0.25, X["scale_note"], size=10.5, color=INK2)
    rect(s, MX, 6.12, W - 2 * MX, 0.8, fill=DARK)
    text(s, MX + 0.3, 6.12, W - 2 * MX - 0.6, 0.8, X["takeaway"], size=14.5, color=WHITE, anchor="m")


def slide_fusion(prs):
    F = D.FUSION
    s = chrome(prs, 6, F["section"], F["title"], F["lede"])
    lw = 4.35
    rows = [list(r) for r in F["rules_rows"]] + [["**Total**", "**35**"]]
    table(s, MX, 2.0, lw, F["rules_head"], rows, [0.8, 0.2], size=11.5, row_h=0.36, pad=0.05)
    text(s, MX, 5.5, lw, 1.3, F["rules_note"], size=10.5, color=INK2)
    # right: the four steps, top to bottom, then the answer
    x0 = MX + lw + 0.75
    sw = W - MX - x0
    y, sh, gap = 2.0, 0.88, 0.2
    for i, (name, body) in enumerate(F["steps"]):
        rect(s, x0, y, sw, sh, fill=CARD)
        text(s, x0 + 0.2, y, 2.0, sh, name, size=14, bold=True, anchor="m")
        text(s, x0 + 2.25, y, sw - 2.45, sh, body, size=11, anchor="m")
        if i < len(F["steps"]) - 1:
            arrow(s, x0 + 1.0, y + sh + 0.02, x0 + 1.0, y + sh + gap - 0.02)
        y += sh + gap
    arrow(s, x0 + 1.0, y - gap + 0.02, x0 + 1.0, y - 0.02)
    n = len(F["classes"])
    cg = 0.15
    cw = (sw - cg * (n - 1)) / n
    for i, name in enumerate(F["classes"]):
        x = x0 + i * (cw + cg)
        unknown = name == "UNKNOWN"
        rect(s, x, y, cw, 0.5, fill=WHITE if unknown else DARK, line=INK2 if unknown else None, dash=unknown)
        text(s, x, y, cw, 0.5, name, size=13, bold=True, color=INK if unknown else WHITE, align="c", anchor="m")
    arrow(s, MX + lw + 0.1, 3.6, x0 - 0.1, 3.6)


def slide_provenance(prs):
    P = D.PROVENANCE
    s = chrome(prs, 7, P["section"], P["title"], P["lede"])
    n, gap = len(P["kinds"]), 0.2
    w = (W - 2 * MX - gap * (n - 1)) / n
    for i, (name, body) in enumerate(P["kinds"]):
        x = MX + i * (w + gap)
        hot = name == "INFERRED"
        rect(s, x, 2.0, w, 1.75, fill=BLUE_TINT if hot else CARD, line=BLUE if hot else None, line_w=1.75)
        text(s, x + 0.2, 2.17, w - 0.4, 0.3, f"`{name}`", size=14.5, bold=True)
        text(s, x + 0.2, 2.62, w - 0.4, 1.1, body, size=12.5)
    text(s, MX, 3.95, W - 2 * MX, 0.6, P["rule"], size=13)
    n = len(P["cards"])
    w = (W - 2 * MX - gap * (n - 1)) / n
    for i, (name, body) in enumerate(P["cards"]):
        card(s, MX + i * (w + gap), 4.75, w, 2.1, name, body, title_size=15, size=12.5)


def slide_validation(prs):
    V = D.VALIDATION
    s = chrome(prs, 8, V["section"], V["title"], V["lede"])
    cols, gap = 3, 0.2
    w = (W - 2 * MX - gap * (cols - 1)) / cols
    h, vgap = 2.0, 0.15
    for i, (name, body) in enumerate(V["cards"]):
        r, c = divmod(i, cols)
        card(s, MX + c * (w + gap), 2.0 + r * (h + vgap), w, h, name, body, title_size=15, size=12, pad=0.18)
    rect(s, MX, 6.3, W - 2 * MX, 0.6, fill=DARK)
    text(s, MX + 0.25, 6.3, W - 2 * MX - 0.5, 0.6, V["gate"], size=12.5, color=WHITE, anchor="m")


def slide_performance(prs):
    P = D.PERFORMANCE
    s = chrome(prs, 9, P["section"], P["title"], P["lede"])
    table(s, MX, 1.98, W - 2 * MX, P["head"], P["rows"], P["widths"], size=11, row_h=0.66, pad=0.05)
    text(s, MX, 6.72, W - 2 * MX, 0.25, P["note"], size=10.5, color=INK2)


def slide_faint(prs):
    F = D.FAINT
    s = chrome(prs, 10, F["section"], F["title"], F["lede"])
    # left: bar chart, one series, every bar labelled with its value (so no y axis is needed)
    cx, cw = MX, 6.0
    text(s, cx, 2.0, cw, 0.5, F["chart_title"], size=12.5, bold=True)
    base_y, top_y = 5.75, 2.95
    n = len(F["bars"])
    slot = cw / n
    bw = slot * 0.56
    for i, (label, value, vlabel) in enumerate(F["bars"]):
        x = cx + i * slot + (slot - bw) / 2
        h = (base_y - top_y) * value / 100.0
        if value > 0:
            rect(s, x, base_y - h, bw, h, fill=BLUE, rounded=False)
        text(s, cx + i * slot, base_y - h - 0.36, slot, 0.3, vlabel, size=14, bold=True, align="c")
        text(s, cx + i * slot, base_y + 0.08, slot, 0.3, label, size=12, color=INK2, align="c")
    rect(s, cx, base_y, cw, 0.014, fill=INK2, rounded=False)
    text(s, cx, 6.2, cw, 0.5, F["chart_source"], size=10.5, color=INK2)
    # right: the candidate flag
    rx = cx + cw + 0.5
    rw = W - MX - rx
    rect(s, rx, 2.0, rw, 2.55, fill=CARD)
    text(s, rx + 0.22, 2.14, rw - 0.44, 0.3, F["flag_title"], size=15, bold=True)
    text(s, rx + 0.22, 2.5, rw - 0.44, 0.3, F["flag_def"], size=11)
    half = (rw - 0.44) / 2
    for i, (num, label, detail) in enumerate(F["flag_stats"]):
        x = rx + 0.22 + i * half
        text(s, x, 2.85, 1.55, 0.65, num, size=34, bold=True)
        text(s, x + 1.5, 2.9, half - 1.5, 0.28, label, size=13, bold=True)
        text(s, x + 1.5, 3.16, half - 1.5, 0.4, detail, size=10, color=INK2, gap=0)
    text(s, rx + 0.22, 3.72, rw - 0.44, 0.8, F["flag_note"], size=11, color=INK2)
    text(s, rx, 4.78, rw, 2.1, F["items"], size=12, bullets=True, gap=7)


def slide_operation(prs):
    O = D.OPERATION
    s = chrome(prs, 11, O["section"], O["title"], O["lede"])
    lw = 6.35
    text(s, MX, 2.0, lw, 0.3, O["time_title"], size=12, bold=True)
    t = O["time_table"]
    table(s, MX, 2.36, lw, t["head"], t["rows"], [0.33, 0.24, 0.23, 0.20], size=10.5, row_h=0.46, pad=0.04)
    text(s, MX, 3.95, lw, 1.3, O["time_items"], size=11.5, bullets=True, gap=5)
    rx = MX + lw + 0.4
    rw = W - MX - rx
    text(s, rx, 2.0, rw, 0.3, O["fallback_title"], size=12, bold=True)
    table(s, rx, 2.36, rw, O["fallback_head"], O["fallback_rows"], [0.36, 0.64], size=10.5, row_h=0.33, pad=0.035)
    n, gap = len(O["marks"]), 0.2
    w = (W - 2 * MX - gap * (n - 1)) / n
    for i, (name, body) in enumerate(O["marks"]):
        card(
            s,
            MX + i * (w + gap),
            5.3,
            w,
            1.6,
            name,
            body,
            title_size=13.5,
            size=11,
            fill=DARK if i == 0 else CARD,
            pad=0.17,
        )


def slide_stack(prs):
    K = D.STACK
    s = chrome(prs, 12, K["section"], K["title"], K["lede"])
    lw = 7.3
    y, h, gap = 2.0, 0.78, 0.12
    for layer, tools, detail in K["layers"]:
        rect(s, MX, y, lw, h, fill=CARD)
        text(s, MX + 0.2, y, 1.5, h, layer, size=12.5, bold=True, color=INK2, anchor="m")
        text(s, MX + 1.75, y + 0.1, lw - 1.95, 0.3, tools, size=14, bold=True)
        text(s, MX + 1.75, y + 0.4, lw - 1.95, 0.36, detail, size=10.5, color=INK2)
        y += h + gap
    rx = MX + lw + 0.4
    rw = W - MX - rx
    text(s, rx, 2.0, rw, 0.3, K["map_title"], size=14, bold=True)
    yy = 2.42
    for path, role in K["map_rows"]:
        rect(s, rx, yy - 0.05, rw, 0.008, fill=LINE, rounded=False)
        text(s, rx, yy, 1.75, 0.5, f"`{path}`", size=11, bold=True, anchor="m")
        text(s, rx + 1.8, yy, rw - 1.8, 0.5, role, size=10.5, anchor="m")
        yy += 0.58
    text(s, MX, 6.55, W - 2 * MX, 0.3, K["rules"], size=11.5, color=INK2)


SLIDES = [
    slide_title,
    slide_glance,
    slide_pipeline,
    slide_sources,
    slide_decides,
    slide_fusion,
    slide_provenance,
    slide_validation,
    slide_performance,
    slide_faint,
    slide_operation,
    slide_stack,
]


# ------------------------------------------------------------------------------------------------ output
_FIXED = _dt.datetime(2026, 11, 25, 0, 0, 0)


def build_pptx(path: Path) -> int:
    prs = Presentation()
    prs.slide_width, prs.slide_height = Inches(W), Inches(H)
    cp = prs.core_properties
    cp.title = f"Finding Objects: pipeline and tech stack (program version {D.PROGRAM_VERSION})"
    cp.author = cp.last_modified_by = "Finding Objects"
    cp.created = cp.modified = _FIXED
    for fn in SLIDES:
        fn(prs)
    assert len(prs.slides) == D.N_SLIDES
    with tempfile.TemporaryDirectory() as tmp:
        raw = Path(tmp) / "raw.pptx"
        prs.save(str(raw))
        # rewrite the zip with fixed timestamps so the same content gives the same file
        with zipfile.ZipFile(raw) as zin, zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zout:
            for item in zin.infolist():
                info = zipfile.ZipInfo(item.filename, date_time=(2026, 11, 25, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = item.external_attr
                zout.writestr(info, zin.read(item.filename))
    return len(prs.slides)


def build_pdf(pptx: Path, pdf: Path) -> None:
    """Convert with LibreOffice headless (the same slides, so the two files cannot differ in content)."""
    soffice = shutil.which("soffice") or shutil.which("libreoffice")
    if not soffice:
        raise SystemExit("LibreOffice (soffice) not found: install it or run with --no-pdf")
    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run(
            [
                soffice,
                f"-env:UserInstallation=file://{tmp}/profile",
                "--headless",
                "--convert-to",
                "pdf",
                "--outdir",
                tmp,
                str(pptx),
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=300,
        )
        shutil.move(str(Path(tmp) / (pptx.stem + ".pdf")), str(pdf))


def build_preview(pdf: Path, png: Path) -> bool:
    tool = shutil.which("pdftoppm")
    if not tool:
        return False
    subprocess.run(
        [tool, "-f", "1", "-l", "1", "-r", "96", "-png", "-singlefile", str(pdf), str(png.with_suffix(""))], check=True
    )
    return True


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", type=Path, default=HERE, help="output directory (default: v2/document)")
    ap.add_argument("--no-pdf", action="store_true", help="write the PPTX only")
    a = ap.parse_args(argv)
    a.out.mkdir(parents=True, exist_ok=True)
    pptx = a.out / pptx_name()
    n = build_pptx(pptx)
    print(f"{pptx}: {n} slides")
    if not a.no_pdf:
        pdf = a.out / pdf_name()
        build_pdf(pptx, pdf)
        print(pdf)
        if build_preview(pdf, a.out / preview_name()):
            print(a.out / preview_name())
    return 0


if __name__ == "__main__":
    sys.exit(main())
