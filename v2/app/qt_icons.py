"""Vector glyphs for each kind of object, drawn with QPainter.

One glyph family per coarse class, varied by the sub-class:

* STAR    five-pointed star, filled with the blackbody colour of its
          spectral type (O blue ... M red; colours of Mitchell Charity's
          "What color are the stars?" table, D58 white point).  Giants
          (III) are drawn larger with a halo; white dwarfs are small white
          discs with a ring; carbon stars deep red; CVs get a burst.
* GALAXY  ellipse.  Early-type / quiescent: smooth warm ellipse.
          Star-forming / disc: blue ellipse with two spiral arms.
          AGN host: ellipse with a bright nucleus and short rays.
          Large galaxies (SGA host) additionally show their true D26
          ellipse on the map.
* QSO     diamond with four rays.  Radio-loud: two opposite jets.
          X-ray detected: small cross badge.
* UNKNOWN hollow grey circle.
"""

from __future__ import annotations
import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap, QPolygonF

# Representative stellar colours by spectral letter (sRGB, approximate
# blackbody colours at the dwarf-scale Teff of each class).
STAR_COLORS = {
    "O": "#9bb0ff",
    "B": "#aabfff",
    "A": "#cad7ff",
    "F": "#f8f7ff",
    "G": "#fff4ea",
    "K": "#ffd2a1",
    "M": "#ffb46c",
    "L": "#ff8a4c",
    "T": "#e0603a",
    "Y": "#b04020",
}
OUTLINE = QColor("#3b3f45")
GAL_EARLY, GAL_DISK, GAL_AGN, GAL_UNK, GAL_GV = "#e8a85a", "#4f8fdc", "#d64f9a", "#8fa3c8", "#4caf50"
QSO_COLOR = "#7b3fb5"
UNKNOWN_COLOR = "#8a8f98"


def kind_of(row) -> dict:
    """Glyph parameters from a result row (dict / pandas Series)."""
    get = row.get if hasattr(row, "get") else (lambda k, d=None: d)
    cls = str(get("primary_class", "UNKNOWN") or "UNKNOWN")
    code = str(get("subclass_code", "") or "")
    parts = code.split(":")
    k = {"cls": cls, "code": code}
    tags = str(get("subclass_tags", "") or "").lower()
    k["binary"] = "binary" in tags
    k["halo"] = "halo star" in tags
    k["dwarf"] = "dwarf galaxy" in tags
    if cls == "STAR":
        k["letter"] = parts[1] if len(parts) > 1 and parts[1] not in ("", "?") else None
        k["lum"] = parts[2] if len(parts) > 2 and parts[2] not in ("", "?") else None
    elif cls == "GALAXY":
        k["activity"] = parts[1] if len(parts) > 1 and parts[1] != "?" else None
        k["profile"] = parts[2] if len(parts) > 2 and parts[2] != "?" else None
        try:
            k["host"] = int(float(get("n_components", 0) or 0)) > 0
        except (TypeError, ValueError):
            k["host"] = False
    elif cls == "QSO":
        k["radio"] = parts[1] if len(parts) > 1 else None
        k["xray"] = len(parts) > 3 and parts[3] == "X"
    return k


def _star_path(c: QPointF, r: float, points=5, inner=0.45) -> QPolygonF:
    poly = QPolygonF()
    for i in range(points * 2):
        rr = r if i % 2 == 0 else r * inner
        a = -math.pi / 2 + i * math.pi / points
        poly.append(QPointF(c.x() + rr * math.cos(a), c.y() + rr * math.sin(a)))
    return poly


def draw(p: QPainter, k: dict, c: QPointF, size: float = 9.0, selected: bool = False) -> None:
    """Draw the glyph for kind ``k`` centred on ``c``; ``size`` is the radius in px."""
    p.save()
    p.setRenderHint(QPainter.Antialiasing)
    cls = k.get("cls")
    if cls == "STAR":
        code = k.get("code", "")
        if code == "STAR:WD":
            p.setPen(QPen(QColor("#5b7bd5"), 1.2))
            p.setBrush(QColor("white"))
            p.drawEllipse(c, size * 0.45, size * 0.45)
            p.setBrush(Qt.NoBrush)
            p.drawEllipse(c, size * 0.8, size * 0.8)
        else:
            col = QColor("#b3261e") if code == "STAR:C" else QColor(STAR_COLORS.get(k.get("letter") or "", "#d8d8d8"))
            r = size * (1.35 if k.get("lum") in ("III", "II", "Ib", "Ia") else 1.0)
            if k.get("lum") in ("III", "II", "Ib", "Ia"):
                halo = QColor(col)
                halo.setAlpha(70)
                p.setPen(Qt.NoPen)
                p.setBrush(halo)
                p.drawEllipse(c, r * 1.15, r * 1.15)
            p.setPen(QPen(OUTLINE, 1.0, Qt.DashLine if k.get("halo") else Qt.SolidLine))
            p.setBrush(col)
            p.drawPolygon(_star_path(c, r))
            if k.get("binary"):  # unresolved companion
                p.setPen(QPen(OUTLINE, 0.8))
                p.setBrush(col.darker(130))
                p.drawEllipse(QPointF(c.x() + r * 0.95, c.y() - r * 0.75), r * 0.32, r * 0.32)
            if code == "STAR:CV":
                p.setPen(QPen(QColor("#e0a000"), 1.2))
                for i in range(8):
                    a = i * math.pi / 4
                    p.drawLine(
                        QPointF(c.x() + r * 1.1 * math.cos(a), c.y() + r * 1.1 * math.sin(a)),
                        QPointF(c.x() + r * 1.5 * math.cos(a), c.y() + r * 1.5 * math.sin(a)),
                    )
    elif cls == "GALAXY":
        act, prof = k.get("activity"), k.get("profile")
        disk = act in ("STAR_FORMING", "STARBURST") or prof in ("DISK", "LATE_TYPE")
        early = act == "QUIESCENT" or prof == "EARLY_TYPE"
        col = QColor(
            GAL_AGN
            if act == "AGN"
            else GAL_GV if act == "GREEN_VALLEY" else GAL_DISK if disk else GAL_EARLY if early else GAL_UNK
        )
        p.translate(c)
        p.rotate(-30)
        sz = size * (0.7 if k.get("dwarf") else 1.0)
        rx, ry = sz * 1.25, sz * (0.55 if disk else 0.8)
        fill = QColor(col)
        fill.setAlpha(170)
        p.setPen(QPen(col.darker(150), 1.0))
        p.setBrush(fill)
        p.drawEllipse(QPointF(0, 0), rx, ry)
        if disk:  # two spiral arms
            p.setPen(QPen(QColor("white"), 1.1))
            p.setBrush(Qt.NoBrush)
            path = QPainterPath()
            path.moveTo(0, 0)
            path.cubicTo(rx * 0.5, -ry * 0.9, rx * 0.95, -ry * 0.2, rx * 0.8, ry * 0.35)
            path.moveTo(0, 0)
            path.cubicTo(-rx * 0.5, ry * 0.9, -rx * 0.95, ry * 0.2, -rx * 0.8, -ry * 0.35)
            p.drawPath(path)
        core = QColor("white") if act == "AGN" else col.lighter(160)
        p.setPen(Qt.NoPen)
        p.setBrush(core)
        p.drawEllipse(QPointF(0, 0), size * 0.25, size * 0.25)
        if act == "AGN":
            p.setPen(QPen(QColor("white"), 1.0))
            for a in (0, 90, 180, 270):
                t = math.radians(a)
                p.drawLine(
                    QPointF(size * 0.3 * math.cos(t), size * 0.3 * math.sin(t)),
                    QPointF(size * 0.6 * math.cos(t), size * 0.6 * math.sin(t)),
                )
        if k.get("host"):  # large resolved galaxy: double outline
            p.setPen(QPen(col.darker(170), 1.2))
            p.setBrush(Qt.NoBrush)
            p.drawEllipse(QPointF(0, 0), rx * 1.25, ry * 1.25)
    elif cls == "QSO":
        col = QColor(QSO_COLOR)
        r = size * 0.85
        if k.get("radio") == "RADIO_LOUD":  # jets
            p.setPen(QPen(QColor("#c0392b"), 1.6))
            p.drawLine(QPointF(c.x() - r * 2.0, c.y() + r * 0.9), QPointF(c.x() + r * 2.0, c.y() - r * 0.9))
        p.setPen(QPen(col, 1.0))
        for a in (0, 90, 180, 270):
            t = math.radians(a + 45)
            p.drawLine(
                QPointF(c.x() + r * 0.7 * math.cos(t), c.y() + r * 0.7 * math.sin(t)),
                QPointF(c.x() + r * 1.45 * math.cos(t), c.y() + r * 1.45 * math.sin(t)),
            )
        diamond = QPolygonF(
            [QPointF(c.x(), c.y() - r), QPointF(c.x() + r, c.y()), QPointF(c.x(), c.y() + r), QPointF(c.x() - r, c.y())]
        )
        p.setPen(QPen(col.darker(140), 1.0))
        p.setBrush(col)
        p.drawPolygon(diamond)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("white"))
        p.drawEllipse(c, r * 0.28, r * 0.28)
        if k.get("xray"):
            p.setPen(QPen(QColor("#0b7a3b"), 1.6))
            bx, by = c.x() + r * 1.1, c.y() - r * 1.1
            p.drawLine(QPointF(bx - 3, by - 3), QPointF(bx + 3, by + 3))
            p.drawLine(QPointF(bx - 3, by + 3), QPointF(bx + 3, by - 3))
    else:
        col = QColor(UNKNOWN_COLOR)
        p.setPen(QPen(col, 1.2))
        p.setBrush(Qt.NoBrush)
        p.drawEllipse(c, size * 0.45, size * 0.45)
    if selected:
        p.resetTransform()
        p.setPen(QPen(QColor("#111111"), 2))
        p.setBrush(Qt.NoBrush)
        p.drawEllipse(c, size * 1.9, size * 1.9)
    p.restore()


def icon(k: dict, px: int = 18) -> QIcon:
    pm = QPixmap(px, px)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    draw(p, k, QPointF(px / 2, px / 2), px * 0.36)
    p.end()
    return QIcon(pm)


# Legend entries: (label, kind)
LEGEND = [
    ("G/K dwarf", {"cls": "STAR", "code": "STAR:G:V", "letter": "G", "lum": "V"}),
    ("M dwarf", {"cls": "STAR", "code": "STAR:M:V", "letter": "M", "lum": "V"}),
    ("A/B star", {"cls": "STAR", "code": "STAR:A:V", "letter": "A", "lum": "V"}),
    ("Giant", {"cls": "STAR", "code": "STAR:K:III", "letter": "K", "lum": "III"}),
    ("White dwarf", {"cls": "STAR", "code": "STAR:WD"}),
    ("Star-forming galaxy", {"cls": "GALAXY", "activity": "STAR_FORMING"}),
    ("Quiescent galaxy", {"cls": "GALAXY", "activity": "QUIESCENT"}),
    ("AGN host", {"cls": "GALAXY", "activity": "AGN"}),
    ("Green-valley galaxy", {"cls": "GALAXY", "activity": "GREEN_VALLEY"}),
    ("Binary candidate", {"cls": "STAR", "code": "STAR:K:V", "letter": "K", "lum": "V", "binary": True}),
    ("Halo star (dashed)", {"cls": "STAR", "code": "STAR:G:VI", "letter": "G", "lum": "VI", "halo": True}),
    ("Galaxy", {"cls": "GALAXY"}),
    ("Quasar", {"cls": "QSO"}),
    ("Radio-loud QSO", {"cls": "QSO", "radio": "RADIO_LOUD"}),
    ("Unclassified", {"cls": "UNKNOWN"}),
]
