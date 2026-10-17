"""Bookmarks page of the desktop app (2.23.0).

A page of its own (tab "Bookmarks" next to "Classifier"): every bookmarked
object with its classes, position and a note.  From here an object can be
opened in the results it came from, used as the centre of a new search,
copied, removed or exported.  Storage is bookmarks.BookmarkStore.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from bookmarks import BookmarkStore
from qt_models import class_color

HEADERS = ("Name", "Class", "Sub-class", "RA", "Dec", "Note", "Added")
ID_ROLE = Qt.UserRole + 1


class _NumberItem(QTableWidgetItem):
    """Sorts by value, not by text."""

    def __init__(self, value):
        super().__init__("" if value is None else f"{value:.6f}")
        self._value = value if value is not None else float("-inf")

    def __lt__(self, other):
        if isinstance(other, _NumberItem):
            return self._value < other._value
        return super().__lt__(other)


class BookmarksPage(QWidget):
    openRequested = Signal(dict)  # show the bookmark in its results
    searchRequested = Signal(float, float, str)  # use as the centre of a new search

    def __init__(self, store: BookmarkStore, parent=None):
        super().__init__(parent)
        self.store = store
        lay = QVBoxLayout(self)

        top = QHBoxLayout()
        self.lbl_count = QLabel("")
        self.lbl_count.setStyleSheet("font-weight: 600;")
        self.txt_search = QLineEdit()
        self.txt_search.setPlaceholderText("Search name / class / note…")
        self.txt_search.setClearButtonEnabled(True)
        self.btn_export = QPushButton("Export CSV…")
        top.addWidget(self.lbl_count)
        top.addWidget(self.txt_search, 1)
        top.addWidget(self.btn_export)
        lay.addLayout(top)

        split = QSplitter(Qt.Horizontal)
        self.table = QTableWidget(0, len(HEADERS))
        self.table.setHorizontalHeaderLabels(HEADERS)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setSortingEnabled(True)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.table.horizontalHeader().setStretchLastSection(True)
        split.addWidget(self.table)

        side = QWidget()
        sl = QVBoxLayout(side)
        self.title = QLabel("Select a bookmark")
        self.title.setStyleSheet("font-weight: 600; font-size: 14px;")
        self.title.setWordWrap(True)
        sl.addWidget(self.title)
        info = QFormLayout()
        self.lbl_pos, self.lbl_axes, self.lbl_source = QLabel("–"), QLabel("–"), QLabel("–")
        for w in (self.lbl_pos, self.lbl_axes, self.lbl_source):
            w.setWordWrap(True)
            w.setTextInteractionFlags(Qt.TextSelectableByMouse)
        info.addRow("Position", self.lbl_pos)
        info.addRow("Classes", self.lbl_axes)
        info.addRow("From", self.lbl_source)
        sl.addLayout(info)
        sl.addWidget(QLabel("Note"))
        self.note = QPlainTextEdit()
        self.note.setPlaceholderText("Write a note about this object…")
        sl.addWidget(self.note, 1)
        buttons = QHBoxLayout()
        self.btn_open = QPushButton("Open in results")
        self.btn_search = QPushButton("Search here")
        self.btn_copy = QPushButton("Copy coordinates")
        self.btn_remove = QPushButton("Remove")
        for b in (self.btn_open, self.btn_search, self.btn_copy, self.btn_remove):
            buttons.addWidget(b)
        sl.addLayout(buttons)
        self.btn_open.setToolTip("Load the results file this bookmark came from and select the object")
        self.btn_search.setToolTip("Use this position as the centre of a new search")
        split.addWidget(side)
        split.setStretchFactor(0, 3)
        split.setStretchFactor(1, 2)
        split.setSizes([900, 480])
        lay.addWidget(split, 1)

        # Notes are saved shortly after typing stops, not on every keystroke.
        self._note_timer = QTimer(self)
        self._note_timer.setSingleShot(True)
        self._note_timer.setInterval(400)
        self._note_timer.timeout.connect(self._save_note)
        self._current: str | None = None

        self.txt_search.textChanged.connect(self._apply_filter)
        self.table.itemSelectionChanged.connect(self._selection_changed)
        self.table.doubleClicked.connect(lambda *_: self._open())
        self.note.textChanged.connect(self._note_timer.start)
        self.btn_open.clicked.connect(self._open)
        self.btn_search.clicked.connect(self._search)
        self.btn_copy.clicked.connect(self._copy)
        self.btn_remove.clicked.connect(self._remove)
        self.btn_export.clicked.connect(self._export)
        self.refresh()

    # ------------------------------------------------------------ table
    def refresh(self, select_id: str | None = None) -> None:
        """Rebuild the table from the store (keeps or sets the selection)."""
        self._save_note()
        select_id = select_id or self._current
        # Rows are rewritten in place: a kept selection would now point at
        # whatever bookmark landed in that row (after a removal elsewhere the
        # table showed another bookmark while the panel still edited the old
        # one).  Start unselected and select by id below.
        self.table.clearSelection()
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(self.store.items))
        for r, b in enumerate(self.store.items):
            cls = b.get("primary_class") or ""
            values = (
                b.get("name") or b.get("object_id") or "?",
                cls,
                b.get("subclass") or "",
                b.get("ra"),
                b.get("dec"),
                (b.get("note") or "").replace("\n", " "),
                b.get("added") or "",
            )
            for c, v in enumerate(values):
                item = _NumberItem(v) if c in (3, 4) else QTableWidgetItem(str(v))
                item.setData(ID_ROLE, b["id"])
                if c == 1 and cls:
                    item.setForeground(class_color(cls))
                self.table.setItem(r, c, item)
        self.table.setSortingEnabled(True)
        self.table.resizeColumnsToContents()
        self._apply_filter()
        self._select_id(select_id)
        self._show(self.selected())  # also when the selection signal did not fire

    def _apply_filter(self) -> None:
        text = self.txt_search.text().strip().lower()
        shown = 0
        for r in range(self.table.rowCount()):
            row_text = " ".join(self.table.item(r, c).text().lower() for c in range(self.table.columnCount()))
            hide = bool(text) and text not in row_text
            self.table.setRowHidden(r, hide)
            shown += not hide
        n = len(self.store.items)
        self.lbl_count.setText(f"{n} bookmark{'s' if n != 1 else ''}" + (f" · {shown} shown" if text else ""))

    def _select_id(self, bookmark_id: str | None) -> None:
        if not bookmark_id:
            return
        for r in range(self.table.rowCount()):
            if self.table.item(r, 0).data(ID_ROLE) == bookmark_id:
                self.table.selectRow(r)
                self.table.scrollToItem(self.table.item(r, 0))
                return

    def selected(self) -> dict | None:
        items = self.table.selectedItems()
        return self.store.get(items[0].data(ID_ROLE)) if items else None

    # ------------------------------------------------------------ details
    def _selection_changed(self) -> None:
        self._save_note()
        self._show(self.selected())

    def _show(self, b: dict | None) -> None:
        self._current = b["id"] if b else None
        for w in (self.btn_open, self.btn_search, self.btn_copy, self.btn_remove, self.note):
            w.setEnabled(b is not None)
        self.note.blockSignals(True)
        self.note.setPlainText((b.get("note") or "") if b else "")
        self.note.blockSignals(False)
        if b is None:
            self.title.setText("Select a bookmark")
            self.title.setStyleSheet("font-weight: 600; font-size: 14px;")
            for w in (self.lbl_pos, self.lbl_axes, self.lbl_source):
                w.setText("–")
            return
        cls = b.get("primary_class") or "UNKNOWN"
        self.title.setText(f"{b.get('name') or b.get('object_id') or '?'} — {cls}")
        self.title.setStyleSheet(f"font-weight: 600; font-size: 14px; color: {class_color(cls).name()};")
        self.lbl_pos.setText(self._coords(b) or "–")
        axes = [
            f"{k}: {b[k]}"
            for k in ("physical", "variability", "compact", "extragalactic", "phenomenon")
            if b.get(k) and b[k] != "UNKNOWN"
        ]
        sub = b.get("subclass")
        self.lbl_axes.setText("\n".join(([sub] if sub else []) + axes) or "–")
        src = b.get("source")
        exists = bool(src) and Path(src).exists()
        self.lbl_source.setText((src or "–") + ("" if exists or not src else "  (file not found)"))
        self.btn_open.setEnabled(exists)

    @staticmethod
    def _coords(b: dict) -> str:
        if b.get("ra") is None or b.get("dec") is None:
            return ""
        return f"{b['ra']:.6f} {b['dec']:+.6f}"

    def _save_note(self) -> None:
        self._note_timer.stop()
        if self._current is not None:
            text = self.note.toPlainText()
            b = self.store.get(self._current)
            if b is not None and (b.get("note") or "") != text:
                self.store.set_note(self._current, text)
                for r in range(self.table.rowCount()):
                    if self.table.item(r, 0).data(ID_ROLE) == self._current:
                        self.table.item(r, 5).setText(text.replace("\n", " "))

    # ------------------------------------------------------------ actions
    def _open(self) -> None:
        b = self.selected()
        if b and b.get("source") and Path(b["source"]).exists():
            self.openRequested.emit(dict(b))

    def _search(self) -> None:
        b = self.selected()
        if b and b.get("ra") is not None and b.get("dec") is not None:
            self.searchRequested.emit(float(b["ra"]), float(b["dec"]), str(b.get("name") or ""))

    def _copy(self) -> None:
        b = self.selected()
        if b:
            QGuiApplication.clipboard().setText(self._coords(b))

    def _remove(self) -> None:
        b = self.selected()
        if b is None:
            return
        name = b.get("name") or b.get("object_id") or "this bookmark"
        if QMessageBox.question(self, "Remove bookmark", f"Remove {name}?") != QMessageBox.Yes:
            return
        self._current = None
        self.store.remove(b["id"])
        self.refresh()

    def _export(self) -> None:
        if not self.store.items:
            QMessageBox.information(self, "Bookmarks", "No bookmarks yet.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export bookmarks", str(Path.home() / "bookmarks.csv"), "CSV (*.csv)"
        )
        if path:
            try:
                self.store.to_frame().to_csv(path, index=False)
            except OSError as exc:  # e.g. the file is open in Excel
                QMessageBox.warning(self, "Bookmarks", f"Could not write {path}:\n{exc}")
