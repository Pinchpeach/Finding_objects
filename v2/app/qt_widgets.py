"""Custom widgets: a sky map of the classified objects and an object detail panel."""
from __future__ import annotations
import json, math
import pandas as pd
from PySide6.QtCore import QPointF, QRectF, Qt, QUrl, Signal
from PySide6.QtGui import QBrush, QColor, QDesktopServices, QGuiApplication, QPainter, QPen
from PySide6.QtWidgets import (QFormLayout, QGroupBox, QHBoxLayout, QLabel, QProgressBar, QPushButton,
                               QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget)

from qt_models import CLASS_COLORS, class_color

AXES = ("physical", "variability", "compact", "extragalactic", "phenomenon")


class SkyMap(QWidget):
    """Tangent-plane scatter of the field (east to the left, as on the sky).
    Points are coloured by coarse class; clicking selects the nearest object."""
    objectClicked = Signal(int)          # row in the results DataFrame

    MARGIN = 28
    LEGEND_H = 24

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(260, 260)
        self._x = self._y = None
        self._cls: list[str] = []
        self._visible = None
        self._selected: int | None = None
        self._extent = 1.0

    def set_frame(self, df: pd.DataFrame) -> None:
        ra = pd.to_numeric(df.get("ra"), errors="coerce").to_numpy(float) if "ra" in df else None
        dec = pd.to_numeric(df.get("dec"), errors="coerce").to_numpy(float) if "dec" in df else None
        if ra is None or dec is None or not len(ra):
            self._x = self._y = None; self.update(); return
        import numpy as np
        ok = np.isfinite(ra) & np.isfinite(dec)
        ra0, dec0 = float(np.nanmedian(ra)), float(np.nanmedian(dec))
        # Offsets in arcmin; RA wrap handled by taking the signed difference.
        dra = ((ra - ra0 + 180.0) % 360.0) - 180.0
        self._x = np.where(ok, dra * math.cos(math.radians(dec0)) * 60.0, np.nan)
        self._y = np.where(ok, (dec - dec0) * 60.0, np.nan)
        self._extent = max(float(np.nanmax(np.abs(np.r_[self._x, self._y]))) if ok.any() else 1.0, 1e-3)
        self._cls = df.get("primary_class", pd.Series(["UNKNOWN"] * len(df))).astype(str).tolist()
        self._visible = None
        self._selected = None
        self.update()

    def set_visible_rows(self, rows) -> None:
        self._visible = None if rows is None else set(rows)
        self.update()

    def set_selected(self, row: int | None) -> None:
        self._selected = row
        self.update()

    def _to_screen(self, x, y):
        side = min(self.width(), self.height() - self.LEGEND_H) - 2 * self.MARGIN
        cx, cy = self.width() / 2, (self.height() - self.LEGEND_H) / 2
        s = side / (2 * self._extent * 1.05)
        return cx - x * s, cy - y * s           # east (+RA) to the left, north up

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), self.palette().base())
        if self._x is None:
            p.setPen(self.palette().text().color())
            p.drawText(self.rect(), Qt.AlignCenter, "No results yet")
            return
        side = min(self.width(), self.height() - self.LEGEND_H) - 2 * self.MARGIN
        frame = QRectF((self.width() - side) / 2, (self.height() - self.LEGEND_H - side) / 2, side, side)
        p.setPen(QPen(self.palette().mid().color(), 1))
        p.drawRect(frame)
        p.drawText(frame.adjusted(4, 2, 0, 0), Qt.AlignLeft | Qt.AlignTop, "N↑  E←")
        p.drawText(frame.adjusted(0, 0, -4, -2), Qt.AlignRight | Qt.AlignBottom, f"±{self._extent:.1f}′")
        for i, (x, y) in enumerate(zip(self._x, self._y)):
            if x != x or (self._visible is not None and i not in self._visible):
                continue
            sx, sy = self._to_screen(x, y)
            c = QColor(CLASS_COLORS.get(self._cls[i], CLASS_COLORS["UNKNOWN"]))
            r = 2.0 if self._cls[i] == "UNKNOWN" else 3.0
            if self._cls[i] == "UNKNOWN":
                c.setAlpha(110)
            p.setPen(Qt.NoPen); p.setBrush(QBrush(c))
            p.drawEllipse(QPointF(sx, sy), r, r)
        if self._selected is not None and self._x[self._selected] == self._x[self._selected]:
            sx, sy = self._to_screen(self._x[self._selected], self._y[self._selected])
            p.setBrush(Qt.NoBrush); p.setPen(QPen(self.palette().text().color(), 2))
            p.drawEllipse(QPointF(sx, sy), 8, 8)
        # legend, one row under the map
        lx, ly = frame.left(), frame.bottom() + self.LEGEND_H - 6
        for name, col in CLASS_COLORS.items():
            p.setPen(Qt.NoPen); p.setBrush(QColor(col)); p.drawEllipse(QPointF(lx + 4, ly - 4), 4, 4)
            p.setPen(self.palette().text().color()); p.drawText(QPointF(lx + 12, ly), name)
            lx += 18 + p.fontMetrics().horizontalAdvance(name)

    def mousePressEvent(self, event):
        if self._x is None:
            return
        pos = event.position()
        best, best_d = None, 12.0 ** 2
        for i, (x, y) in enumerate(zip(self._x, self._y)):
            if x != x or (self._visible is not None and i not in self._visible):
                continue
            sx, sy = self._to_screen(x, y)
            d = (sx - pos.x()) ** 2 + (sy - pos.y()) ** 2
            if d < best_d:
                best, best_d = i, d
        if best is not None:
            self.objectClicked.emit(best)


class DetailPanel(QWidget):
    """Everything known about one object: coarse probabilities, the evidence
    that produced them, the detailed classifier axes, and external links."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._row: pd.Series | None = None
        lay = QVBoxLayout(self)
        self.title = QLabel("Select an object"); self.title.setStyleSheet("font-weight: 600; font-size: 14px;")
        lay.addWidget(self.title)
        info = QFormLayout()
        self.lbl_pos, self.lbl_status, self.lbl_cats = QLabel("–"), QLabel("–"), QLabel("–")
        self.lbl_cats.setWordWrap(True)
        for k, w in (("Position", self.lbl_pos), ("Status", self.lbl_status), ("Catalogs", self.lbl_cats)):
            w.setTextInteractionFlags(Qt.TextSelectableByMouse); info.addRow(k, w)
        lay.addLayout(info)

        probs = QGroupBox("Coarse class probability")
        pl = QFormLayout(probs)
        self.bars = {}
        for cls in ("STAR", "GALAXY", "QSO"):
            bar = QProgressBar(); bar.setRange(0, 1000); bar.setFormat("%p%")
            bar.setStyleSheet(f"QProgressBar::chunk {{ background: {CLASS_COLORS[cls]}; }}")
            self.bars[cls] = bar; pl.addRow(cls, bar)
        lay.addWidget(probs)

        self.evidence = QTreeWidget(); self.evidence.setHeaderLabels(["Rule", "Class", "Score", "Value", "Note"])
        self.evidence.setRootIsDecorated(False); self.evidence.setAlternatingRowColors(True)
        ev = QGroupBox("Evidence"); QVBoxLayout(ev).addWidget(self.evidence)
        lay.addWidget(ev, 1)

        self.axes = QTreeWidget(); self.axes.setHeaderLabels(["Axis", "Class", "Subtype", "Confidence", "Status"])
        self.axes.setRootIsDecorated(False)
        ax = QGroupBox("Detailed classification"); QVBoxLayout(ax).addWidget(self.axes)
        lay.addWidget(ax)

        links = QHBoxLayout()
        self.btn_ls = QPushButton("Legacy Surveys viewer"); self.btn_simbad = QPushButton("SIMBAD")
        self.btn_copy = QPushButton("Copy coordinates")
        for b in (self.btn_ls, self.btn_simbad, self.btn_copy):
            b.setEnabled(False); links.addWidget(b)
        self.btn_ls.clicked.connect(lambda: self._open("ls"))
        self.btn_simbad.clicked.connect(lambda: self._open("simbad"))
        self.btn_copy.clicked.connect(self._copy)
        lay.addLayout(links)

    def show_object(self, row: pd.Series | None) -> None:
        self._row = row
        self.evidence.clear(); self.axes.clear()
        enabled = row is not None
        for b in (self.btn_ls, self.btn_simbad, self.btn_copy):
            b.setEnabled(enabled)
        if row is None:
            self.title.setText("Select an object")
            self.title.setStyleSheet("font-weight: 600; font-size: 14px;")
            for w in (self.lbl_pos, self.lbl_status, self.lbl_cats):
                w.setText("–")
            for bar in self.bars.values():
                bar.setValue(0)
            return
        cls = str(row.get("primary_class", "UNKNOWN"))
        self.title.setText(f"{row.get('object_id', '')} — {cls}")
        self.title.setStyleSheet(f"font-weight: 600; font-size: 14px; color: {class_color(cls).name()};")
        self.lbl_pos.setText(f"{_f(row.get('ra'), 6)}, {_f(row.get('dec'), 6)}")
        self.lbl_status.setText(f"{row.get('classification_status', '')}  (confidence {_f(row.get('primary_confidence'), 3)})")
        self.lbl_cats.setText(str(row.get("catalogs", "")).replace("|", ", "))
        for c, bar in self.bars.items():
            v = _num(row.get(f"p_{c.lower()}"))
            bar.setValue(0 if v is None else int(round(v * 1000)))
        for e in _json(row.get("evidence_json")):
            item = QTreeWidgetItem([str(e.get("rule_id", "")), str(e.get("class", "")),
                                    _f(e.get("score"), 2), _short(e.get("value")), str(e.get("note", ""))])
            self.evidence.addTopLevelItem(item)
        for axis in AXES:
            label = row.get(f"{axis}_class")
            if label is None or (isinstance(label, float) and label != label):
                continue
            self.axes.addTopLevelItem(QTreeWidgetItem([axis, str(label), _short(row.get(f"{axis}_subtype")),
                                                       _f(row.get(f"{axis}_confidence"), 2), str(row.get(f"{axis}_status", ""))]))
        for t in (self.evidence, self.axes):
            for i in range(t.columnCount()):
                t.resizeColumnToContents(i)

    def _open(self, which):
        if self._row is None:
            return
        ra, dec = _num(self._row.get("ra")), _num(self._row.get("dec"))
        if ra is None or dec is None:
            return
        url = (f"https://www.legacysurvey.org/viewer?ra={ra:.6f}&dec={dec:.6f}&layer=ls-dr10&zoom=16&mark={ra:.6f},{dec:.6f}"
               if which == "ls" else
               f"https://simbad.cds.unistra.fr/simbad/sim-coo?Coord={ra:.6f}%20{dec:+.6f}&Radius=5&Radius.unit=arcsec")
        QDesktopServices.openUrl(QUrl(url))

    def _copy(self):
        if self._row is not None:
            QGuiApplication.clipboard().setText(f"{_f(self._row.get('ra'), 6)} {_f(self._row.get('dec'), 6)}")


def _num(v):
    try:
        x = float(v)
        return x if math.isfinite(x) else None
    except (TypeError, ValueError):
        return None


def _f(v, nd):
    x = _num(v)
    return "–" if x is None else f"{x:.{nd}f}"


def _short(v, n=40):
    if v is None or (isinstance(v, float) and v != v):
        return ""
    s = f"{v:.3g}" if isinstance(v, float) else str(v)
    return s if len(s) <= n else s[: n - 1] + "…"


def _json(v):
    if not isinstance(v, str) or not v:
        return []
    try:
        out = json.loads(v)
        return out if isinstance(out, list) else []
    except json.JSONDecodeError:
        return []
