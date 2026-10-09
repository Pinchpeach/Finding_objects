"""Custom widgets: a sky map of the classified objects and an object detail panel."""
from __future__ import annotations
import json, math
import pandas as pd
from PySide6.QtCore import QPointF, QRectF, Qt, QUrl, Signal
from PySide6.QtGui import QBrush, QColor, QDesktopServices, QGuiApplication, QPainter, QPen
from PySide6.QtWidgets import (QCheckBox, QFormLayout, QGroupBox, QHBoxLayout, QLabel, QProgressBar, QPushButton,
                               QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget)

from qt_models import CLASS_COLORS, class_color

RELATION_TEXT = {
    "foreground_star": "Foreground star seen against a large galaxy (significant Gaia parallax/proper motion)",
    "background_source": "Background source behind a large galaxy (higher redshift)",
    "foreground_source": "Foreground source in front of a large galaxy (lower redshift)",
    "transient": "Transient event inside a large galaxy (kept separate from the host)",
}
AXES = ("physical", "variability", "compact", "extragalactic", "phenomenon")


class SkyMap(QWidget):
    """Tangent-plane map of the field (north up, east to the left).

    Each object is drawn with the glyph of its class/sub-class (qt_icons);
    large galaxies also show their true SGA D26 ellipse. Mouse wheel zooms
    about the cursor, dragging pans, right-click (or Home) resets the view,
    a click selects the nearest object and a double-click sets the search
    centre there."""
    objectClicked = Signal(int)          # row in the results DataFrame
    centerPicked = Signal(float, float)  # double-click: (ra, dec) for a new search centre
    viewChanged = Signal()

    MARGIN = 24
    ICON = 7.5
    LABEL_LIMIT = 40                     # draw names when at most this many objects are in view

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(260, 260)
        self.setMouseTracking(False)
        self.setFocusPolicy(Qt.StrongFocus)
        self._x = self._y = None
        self._ra = self._dec = None
        self._kinds: list[dict] = []
        self._names: list[str] = []
        self._hosts: list[tuple[int, float, float, float]] = []   # (row, d26 arcmin, pa, b/a)
        self._visible = None
        self._selected: int | None = None
        self._extent = 1.0
        self._area: tuple[float, float, float] | None = None
        self._c0: tuple[float, float] | None = None
        self._zoom = 1.0
        self._pan = [0.0, 0.0]
        self._press = None
        self._dragging = False
        self.setToolTip("Wheel: zoom · Drag: pan · Right-click: reset view\n"
                        "Click: select object · Double-click: set search centre here")

    # ---------------------------------------------------------------- data
    def set_frame(self, df: pd.DataFrame) -> None:
        from qt_icons import kind_of
        ra = pd.to_numeric(df["ra"], errors="coerce").to_numpy(float) if "ra" in df else None
        dec = pd.to_numeric(df["dec"], errors="coerce").to_numpy(float) if "dec" in df else None
        self._ra, self._dec = (ra, dec) if ra is not None and dec is not None and len(ra) else (None, None)
        rows = df.to_dict("records")
        self._kinds = [kind_of(r) for r in rows]
        name_col = "designation" if "designation" in df else "object_id" if "object_id" in df else None
        self._names = df[name_col].astype(str).tolist() if name_col else [""] * len(df)
        self._hosts = []
        for i, r in enumerate(rows):
            d26 = _num(r.get("sga_d26_arcmin", r.get("sga_2020__sga_d26_arcmin")))
            if d26 and _num(r.get("sga_2020__catalog_object_id")) is not None:
                self._hosts.append((i, d26, _num(r.get("sga_pa_deg", r.get("sga_2020__sga_pa_deg"))) or 0.0,
                                    _num(r.get("sga_ba", r.get("sga_2020__sga_ba"))) or 1.0))
        self._visible = None
        self._selected = None
        self._project(reset=True)

    def set_area(self, area: tuple[float, float, float] | None) -> None:
        """Search cone drawn on the map; the map is centred on it."""
        self._area = area
        self._project(reset=True)

    def set_visible_rows(self, rows) -> None:
        self._visible = None if rows is None else set(rows)
        self.update()

    def set_selected(self, row: int | None) -> None:
        self._selected = row
        self.update()

    def reset_view(self) -> None:
        self._zoom, self._pan = 1.0, [0.0, 0.0]
        self.update(); self.viewChanged.emit()

    def zoom_by(self, factor: float, anchor: QPointF | None = None) -> None:
        if self._c0 is None:
            return
        anchor = anchor or QPointF(self.width() / 2, self.height() / 2)
        x, y = self._to_offsets(anchor.x(), anchor.y())
        self._zoom = min(max(self._zoom * factor, 0.5), 5000.0)
        cx, cy, s = self._scale()
        self._pan = [x - (cx - anchor.x()) / s, y - (cy - anchor.y()) / s]
        self.update(); self.viewChanged.emit()

    @property
    def zoom(self) -> float:
        return self._zoom

    def _project(self, reset=False) -> None:
        import numpy as np
        if self._area is not None:
            self._c0 = (self._area[0], self._area[1])
        elif self._ra is not None and np.isfinite(self._ra).any():
            self._c0 = (float(np.nanmedian(self._ra)), float(np.nanmedian(self._dec)))
        else:
            self._c0 = None
        self._x = self._y = None
        extent = self._area[2] if self._area is not None else 0.0
        if self._c0 is not None and self._ra is not None:
            ok = np.isfinite(self._ra) & np.isfinite(self._dec)
            x, y = self._offsets(self._ra, self._dec)
            self._x, self._y = np.where(ok, x, np.nan), np.where(ok, y, np.nan)
            if ok.any() and self._area is None:
                extent = max(extent, float(np.nanmax(np.abs(np.r_[self._x, self._y]))))
        self._extent = max(extent, 1e-3)
        if reset:
            self._zoom, self._pan = 1.0, [0.0, 0.0]
        self.update()

    def _offsets(self, ra, dec):
        """Offsets from the centre in arcmin (RA wrap via the signed difference)."""
        import numpy as np
        ra0, dec0 = self._c0
        dra = ((np.asarray(ra, float) - ra0 + 180.0) % 360.0) - 180.0
        return dra * math.cos(math.radians(dec0)) * 60.0, (np.asarray(dec, float) - dec0) * 60.0

    # ---------------------------------------------------------- transforms
    def _scale(self):
        side = min(self.width(), self.height()) - 2 * self.MARGIN
        return self.width() / 2, self.height() / 2, max(side, 10) / (2 * self._extent * 1.05) * self._zoom

    def _to_screen(self, x, y):
        cx, cy, s = self._scale()
        return cx - (x - self._pan[0]) * s, cy - (y - self._pan[1]) * s   # east (+RA) to the left, north up

    def _to_offsets(self, sx, sy):
        cx, cy, s = self._scale()
        return self._pan[0] + (cx - sx) / s, self._pan[1] + (cy - sy) / s

    def _to_sky(self, sx, sy):
        x, y = self._to_offsets(sx, sy)
        dec = max(-90.0, min(90.0, self._c0[1] + y / 60.0))
        ra = (self._c0[0] + x / 60.0 / max(math.cos(math.radians(self._c0[1])), 1e-6)) % 360.0
        return ra, dec

    def _shown(self, i) -> bool:
        return self._x is not None and self._x[i] == self._x[i] and (self._visible is None or i in self._visible)

    # ------------------------------------------------------------- painting
    def paintEvent(self, event):
        from qt_icons import draw
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), self.palette().base())
        if self._c0 is None:
            p.setPen(self.palette().text().color())
            p.drawText(self.rect(), Qt.AlignCenter, "No results yet")
            return
        cx, cy, s = self._scale()
        text = self.palette().text().color()
        if self._area is not None:              # search cone + centre cross
            ox, oy = self._to_screen(0.0, 0.0)
            pen = QPen(QColor("#2f9e44"), 1.5, Qt.DashLine); p.setPen(pen); p.setBrush(Qt.NoBrush)
            r = self._area[2] * s
            p.drawEllipse(QPointF(ox, oy), r, r)
            p.setPen(QPen(QColor("#2f9e44"), 1.5))
            p.drawLine(QPointF(ox - 7, oy), QPointF(ox + 7, oy)); p.drawLine(QPointF(ox, oy - 7), QPointF(ox, oy + 7))
        # true extent of large galaxies (SGA D26 ellipse; PA from north through east)
        for i, d26, pa, ba in self._hosts:
            if not self._shown(i):
                continue
            sx, sy = self._to_screen(self._x[i], self._y[i])
            a = d26 / 2 * s
            if a < 4:
                continue
            p.save(); p.translate(sx, sy); p.rotate(-pa)          # screen y is down, east is left
            p.setPen(QPen(QColor("#4f8fdc"), 1.2, Qt.DashDotLine)); p.setBrush(QColor(79, 143, 220, 25))
            p.drawEllipse(QPointF(0, 0), a * ba, a)
            p.restore()
        in_view = []
        for i in range(len(self._kinds)):
            if not self._shown(i):
                continue
            sx, sy = self._to_screen(self._x[i], self._y[i])
            if -20 <= sx <= self.width() + 20 and -20 <= sy <= self.height() + 20:
                in_view.append((i, sx, sy))
        # draw unclassified first so classified glyphs stay on top
        for i, sx, sy in sorted(in_view, key=lambda t: self._kinds[t[0]].get("cls") != "UNKNOWN"):
            draw(p, self._kinds[i], QPointF(sx, sy), self.ICON, selected=(i == self._selected))
        if len(in_view) <= self.LABEL_LIMIT:
            p.setPen(text)
            f = p.font(); f.setPointSizeF(max(f.pointSizeF() - 1, 7)); p.setFont(f)
            for i, sx, sy in in_view:
                if self._kinds[i].get("cls") != "UNKNOWN" or i == self._selected:
                    p.drawText(QPointF(sx + self.ICON * 1.6, sy - self.ICON * 0.6), self._names[i])
        # orientation, scale bar, zoom
        p.setPen(text)
        p.drawText(QRectF(6, 4, 200, 16), Qt.AlignLeft | Qt.AlignTop, "N↑  E←")
        self._scale_bar(p, s)
        p.drawText(QRectF(self.width() - 126, 4, 120, 16), Qt.AlignRight | Qt.AlignTop, f"zoom ×{self._zoom:.3g}")

    def _scale_bar(self, p, s):
        target = 80 / s                                   # arcmin per ~80 px
        steps = [x / 60 for x in (0.1, 0.2, 0.5, 1, 2, 5, 10, 20, 30)] + [1, 2, 5, 10, 20, 30, 60, 120, 300, 600]
        length = min(steps, key=lambda v: abs(math.log(v / target)))
        px = length * s
        x0, y0 = 12, self.height() - 14
        p.setPen(QPen(self.palette().text().color(), 2))
        p.drawLine(QPointF(x0, y0), QPointF(x0 + px, y0))
        p.drawText(QPointF(x0, y0 - 5), _angle(length).lstrip("±"))

    # ---------------------------------------------------------------- input
    def wheelEvent(self, event):
        steps = event.angleDelta().y() / 120.0
        if steps:
            self.zoom_by(1.25 ** steps, event.position())
        event.accept()

    def mousePressEvent(self, event):
        if event.button() == Qt.RightButton:
            self.reset_view(); return
        self._press = event.position(); self._dragging = False

    def mouseMoveEvent(self, event):
        if self._press is None or self._c0 is None:
            return
        d = event.position() - self._press
        if not self._dragging and abs(d.x()) + abs(d.y()) < 4:
            return
        self._dragging = True
        _, _, s = self._scale()
        self._pan[0] += d.x() / s; self._pan[1] += d.y() / s
        self._press = event.position()
        self.setCursor(Qt.ClosedHandCursor)
        self.update(); self.viewChanged.emit()

    def mouseReleaseEvent(self, event):
        was_drag, self._press, self._dragging = self._dragging, None, False
        self.unsetCursor()
        if was_drag or event.button() != Qt.LeftButton or self._x is None:
            return
        pos = event.position()
        best, best_d = None, 14.0 ** 2
        for i in range(len(self._kinds)):
            if not self._shown(i):
                continue
            sx, sy = self._to_screen(self._x[i], self._y[i])
            d = (sx - pos.x()) ** 2 + (sy - pos.y()) ** 2
            if d < best_d:
                best, best_d = i, d
        if best is not None:
            self.objectClicked.emit(best)

    def mouseDoubleClickEvent(self, event):
        if self._c0 is not None and event.button() == Qt.LeftButton:
            pos = event.position()
            self.centerPicked.emit(*self._to_sky(pos.x(), pos.y()))

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Home, Qt.Key_R, Qt.Key_0):
            self.reset_view()
        elif event.key() in (Qt.Key_Plus, Qt.Key_Equal):
            self.zoom_by(1.5)
        elif event.key() == Qt.Key_Minus:
            self.zoom_by(1 / 1.5)
        else:
            super().keyPressEvent(event)


class SkyLegend(QWidget):
    """Icon legend for the sky map (wraps into rows)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        from qt_icons import LEGEND, icon
        from PySide6.QtWidgets import QGridLayout
        grid = QGridLayout(self); grid.setContentsMargins(6, 2, 6, 2); grid.setHorizontalSpacing(10); grid.setVerticalSpacing(1)
        for n, (label, kind) in enumerate(LEGEND):
            w = QLabel(); w.setPixmap(icon(kind, 18).pixmap(18, 18))
            t = QLabel(label); t.setStyleSheet("font-size: 11px;")
            grid.addWidget(w, n // 3, (n % 3) * 2); grid.addWidget(t, n // 3, (n % 3) * 2 + 1)


class SkyView(QWidget):
    """SkyMap with zoom buttons and the icon legend."""

    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self); lay.setContentsMargins(0, 0, 0, 0); lay.setSpacing(2)
        bar = QHBoxLayout(); bar.setContentsMargins(4, 2, 4, 0)
        self.map = SkyMap()
        for text, tip, fn in (("+", "Zoom in", lambda: self.map.zoom_by(1.5)), ("−", "Zoom out", lambda: self.map.zoom_by(1 / 1.5)),
                              ("Fit", "Reset view (right-click / Home)", self.map.reset_view)):
            b = QPushButton(text); b.setToolTip(tip); b.setFixedWidth(44 if text == "Fit" else 30); b.clicked.connect(fn); bar.addWidget(b)
        self.chk_labels = QCheckBox("Names"); self.chk_labels.setChecked(True)
        self.chk_labels.toggled.connect(lambda on: (setattr(self.map, "LABEL_LIMIT", 40 if on else -1), self.map.update()))
        bar.addWidget(self.chk_labels)
        bar.addStretch(1)
        lay.addLayout(bar)
        lay.addWidget(self.map, 1)
        lay.addWidget(SkyLegend())


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
        self.lbl_names = QLabel("–"); self.lbl_sub = QLabel("–"); self.lbl_parts = QLabel("–")
        for w in (self.lbl_cats, self.lbl_names, self.lbl_sub, self.lbl_parts):
            w.setWordWrap(True)
        for k, w in (("Sub-class", self.lbl_sub), ("Position", self.lbl_pos), ("Status", self.lbl_status),
                     ("Structure", self.lbl_parts), ("Catalog IDs", self.lbl_names), ("Catalogs", self.lbl_cats)):
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
            for w in (self.lbl_pos, self.lbl_status, self.lbl_cats, self.lbl_names, self.lbl_sub, self.lbl_parts):
                w.setText("–")
            for bar in self.bars.values():
                bar.setValue(0)
            return
        cls = str(row.get("primary_class", "UNKNOWN"))
        name = row.get("designation")
        name = row.get("object_id", "") if name is None or (isinstance(name, float) and name != name) else name
        self.title.setText(f"{name} — {cls}")
        self.title.setStyleSheet(f"font-weight: 600; font-size: 14px; color: {class_color(cls).name()};")
        sep = _num(row.get("separation_arcmin"))
        self.lbl_pos.setText(f"{_f(row.get('ra'), 6)}, {_f(row.get('dec'), 6)}"
                             + ("" if sep is None else f"   ({sep * 60:.1f}″ from centre)"))
        sub = row.get("subclass")
        if isinstance(sub, str) and sub:
            conf = _num(row.get("subclass_confidence"))
            basis = row.get("subclass_basis")
            self.lbl_sub.setText(f"<b>{sub}</b>" + (f"  (rule precision {conf:.2f})" if conf is not None else "")
                                 + (f"<br><span style='color:gray'>{basis}</span>" if isinstance(basis, str) else ""))
            self.title.setText(f"{name} — {sub}")
        else:
            status = row.get("subclass_status")
            self.lbl_sub.setText(f"–  ({status})" if isinstance(status, str) else "–")
        ncomp = int(_num(row.get("n_components")) or 0)
        parent = row.get("parent_object_id")
        if ncomp:
            z = _num(row.get("host_redshift"))
            self.lbl_parts.setText(f"Large galaxy: {ncomp} catalogue entries grouped as its parts"
                                   + (f", z = {z:.4f}" if z is not None else ""))
        elif isinstance(parent, str) and parent:
            self.lbl_parts.setText(f"Part of a large galaxy ({row.get('component_role', 'component')})")
        elif row.get("component_role") in RELATION_TEXT:
            self.lbl_parts.setText(RELATION_TEXT[row.get("component_role")])
        else:
            self.lbl_parts.setText("Single object")
        names = row.get("catalog_designations")
        self.lbl_names.setText(str(names).replace("; ", "\n") if isinstance(names, str) and names else "–")
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


def _angle(arcmin: float) -> str:
    if arcmin < 1.0:
        return f"±{arcmin * 60:.1f}″"
    return f"±{arcmin:.1f}′" if arcmin < 60 else f"±{arcmin / 60:.2f}°"


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
