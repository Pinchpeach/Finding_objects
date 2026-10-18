#!/usr/bin/env python3
"""Finding Objects — Qt desktop app for the v2 multi-wavelength classifier.

    python v2/app/qt_app.py                 # GUI
    python v2/app/qt_app.py --pipeline ...  # worker mode (same arguments as v2/pipeline.py)

The pipeline runs in a separate process (QProcess): the window stays
responsive, a run can be cancelled for real, and log lines stream into the
progress bar.  The app re-invokes itself in worker mode, which also works
when frozen with PyInstaller (sys.executable is then the app itself).
"""

from __future__ import annotations
import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(APP_DIR))
from app_paths import v2_root, version  # noqa: E402

V2 = v2_root()


def _worker_stdio() -> None:
    """A windowed (no-console) frozen build starts with sys.stdout / stderr set
    to None, but the GUI reads the worker's progress from its stdout pipe:
    re-open the inherited standard handles when they exist."""
    import os

    for name, fd in (("stdout", 1), ("stderr", 2)):
        if getattr(sys, name) is None:
            try:
                setattr(sys, name, os.fdopen(fd, "w", buffering=1, encoding="utf-8", errors="replace"))
            except OSError:
                setattr(sys, name, open(os.devnull, "w"))


def _load_v2(module_name: str, file_name: str):
    """Import a top-level v2 script (v2/<file_name>) as ``module_name``."""
    import importlib.util

    spec = importlib.util.spec_from_file_location(module_name, V2 / file_name)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _worker_main(argv: list[str]) -> int:
    """Run v2/pipeline.py's CLI in this process (``--pipeline`` mode)."""
    _worker_stdio()
    sys.path.insert(0, str(V2))
    mod = _load_v2("v2_pipeline", "pipeline.py")
    sys.argv = ["pipeline.py", *argv]
    mod.main()
    mod.exit_now(0)  # results are written; skip interpreter teardown (see pipeline.exit_now)
    return 0


if __name__ == "__main__" and len(sys.argv) > 1 and sys.argv[1] == "--pipeline":
    raise SystemExit(_worker_main(sys.argv[2:]))

import pandas as pd  # noqa: E402
from PySide6.QtCore import (
    QModelIndex,
    QProcess,
    QProcessEnvironment,
    QSettings,
    Qt,
    QThreadPool,
    QRunnable,
    QObject,
    QTimer,
    Signal,
)  # noqa: E402
from PySide6.QtGui import QAction, QKeySequence  # noqa: E402
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,  # noqa: E402
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QSplitter,
    QTableView,
    QTabWidget,
    QVBoxLayout,
    QWidget,
    QAbstractItemView,
    QCheckBox,
)

from progress import ProgressTracker  # noqa: E402
from qt_models import DataFrameModel, ResultsFilter  # noqa: E402
from qt_widgets import DetailPanel, LogWindow, SkyView  # noqa: E402
from app_log import AppLog  # noqa: E402
from bookmarks import BookmarkStore  # noqa: E402
from qt_bookmarks import BookmarksPage  # noqa: E402

APP_NAME = f"Finding Objects {version()}"
RESULT_FILE = "classified_objects.csv"
RADIUS_UNITS = {"arcsec": 1 / 60.0, "arcmin": 1.0, "deg": 60.0}  # -> arcmin
RADIUS_DECIMALS = {"arcsec": 1, "arcmin": 3, "deg": 5}
RADIUS_RANGE_ARCMIN = (0.1 / 60.0, 180.0)  # 0.1 arcsec .. 3 deg
MAX_QUERY_ARCMIN = 30.0  # largest cone the archive collectors were exercised with
# Spin boxes kept between sessions: (settings key, MainWindow attribute, default).
SPINS = (
    ("ra", "sp_ra", 245.0),
    ("dec", "sp_dec", 43.0),
    ("radius", "sp_rad", 3.0),
    ("minconf", "sp_minconf", 0.0),
    ("workers", "sp_workers", 6),
)


def parse_coordinates(text: str) -> tuple[float, float] | None:
    """ICRS (ra, dec) in degrees from typed coordinates, or None if the text is
    not a coordinate (then it is treated as an object name).  Accepts decimal
    degrees ("188.4155 +9.1751") and sexagesimal with RA in hours
    ("12:33:39.7 +09:10:30", "12 33 39.7 +09 10 30", "12h33m39.7s +9d10m30s")."""
    import re

    t = text.strip().replace(",", " ")
    t = re.sub(r"[hHdD°:mM'′sS\"″]", " ", t)  # unit marks -> separators
    if not t or not re.fullmatch(r"[0-9+\-. ]+", t):
        return None
    m = re.fullmatch(r"\s*(\S+(?:\s+\S+)*?)\s+([+-]\S*(?:\s+\S+)*)\s*", t)
    parts = t.split()
    if len(parts) == 2:
        ra_f, dec_f = [parts[0]], [parts[1]]
    elif m:  # split at the signed Dec
        ra_f, dec_f = m.group(1).split(), m.group(2).split()
    elif len(parts) == 6:
        ra_f, dec_f = parts[:3], parts[3:]
    else:
        return None
    try:
        nums_ra = [float(x) for x in ra_f]
        nums_dec = [abs(float(x)) for x in dec_f]
    except ValueError:
        return None
    if not (1 <= len(nums_ra) <= 3 and 1 <= len(nums_dec) <= 3):
        return None
    sexa = lambda v: v[0] + sum(x / 60 ** (i + 1) for i, x in enumerate(v[1:]))
    if len(nums_ra) == 1 and len(nums_dec) == 1:  # decimal degrees
        ra = nums_ra[0]
    else:
        if any(x >= 60 for x in nums_ra[1:] + nums_dec[1:]):
            return None
        ra = sexa(nums_ra) * 15.0
    dec = sexa(nums_dec) * (-1 if dec_f[0].startswith("-") else 1)
    if not (0 <= ra < 360 and -90 <= dec <= 90):
        return None
    return ra, dec


def _designations():
    return _load_v2("v2_designations", "designations.py")


class _NameResolver(QRunnable):
    """Resolve an object name to ICRS coordinates (CDS Sesame) off the GUI thread."""

    class Signals(QObject):
        done = Signal(int, float, float, str)
        failed = Signal(int, str)

    def __init__(self, request: int, name: str):
        super().__init__()
        self.request = request
        self.name = name
        self.signals = self.Signals()

    def run(self):
        try:
            from astropy.coordinates import SkyCoord

            c = SkyCoord.from_name(self.name)
            self.signals.done.emit(self.request, float(c.icrs.ra.deg), float(c.icrs.dec.deg), self.name)
        except Exception as exc:  # network / unknown name
            self.signals.failed.emit(self.request, f"{self.name}: {exc}")


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.resize(1400, 860)
        self.settings = QSettings("FindingObjects", "v2")
        self.proc: QProcess | None = None
        self._out_buf = b""
        self.tracker: ProgressTracker | None = None
        self.work_dir: Path | None = None
        self.model = DataFrameModel(parent=self)
        self.proxy = ResultsFilter(self)
        self.proxy.setSourceModel(self.model)
        self.applog = AppLog()
        self.log_window = None
        self.bookmarks = BookmarkStore()
        self._lookup_id = 0  # latest name / coordinate request
        self._pending_name: str | None = None
        self.results_path: Path | None = None
        self._build_ui()
        self._build_menu()
        self._restore()

    # ---------------------------------------------------------------- UI
    def _build_ui(self):
        # Two pages (2.23.0): the classifier and the bookmarks.
        self.pages = QTabWidget(self)
        self.pages.setDocumentMode(True)
        self.setCentralWidget(self.pages)
        root = QSplitter(Qt.Horizontal)
        self.pages.addTab(root, "Classifier")
        self.bookmark_page = BookmarksPage(self.bookmarks)
        self.pages.addTab(self.bookmark_page, "Bookmarks")
        self.pages.currentChanged.connect(self._page_changed)
        self.bookmark_page.openRequested.connect(self.open_bookmark)
        self.bookmark_page.searchRequested.connect(self.search_bookmark)
        root.addWidget(self._build_controls())

        center = QSplitter(Qt.Vertical)
        table_box = QWidget()
        tl = QVBoxLayout(table_box)
        tl.setContentsMargins(0, 0, 0, 0)
        bar = QHBoxLayout()
        self.cmb_class = QComboBox()
        self.cmb_class.addItems(["ALL", "STAR", "GALAXY", "QSO", "UNKNOWN"])
        self.cmb_status = QComboBox()
        self.cmb_status.addItems(
            ["ALL", "CLASSIFIED", "LOW_CONFIDENCE", "NO_EVIDENCE", "CONFLICT", "WITHIN_LARGE_GALAXY", "SOLAR_SYSTEM"]
        )
        self.txt_search = QLineEdit()
        self.txt_search.setPlaceholderText("Search name / catalog…")
        self.lbl_counts = QLabel("")
        self.chk_parts = QCheckBox("Show galaxy parts")
        self.chk_parts.setToolTip(
            "Catalogue entries that are pieces of a large galaxy (HII regions, nucleus, shreds)\n"
            "are grouped under the galaxy and hidden unless this is on."
        )
        for w in (QLabel("Class"), self.cmb_class, QLabel("Status"), self.cmb_status, self.txt_search, self.chk_parts):
            bar.addWidget(w)
        bar.addStretch(1)
        bar.addWidget(self.lbl_counts)
        tl.addLayout(bar)
        self.table = QTableView()
        self.table.setModel(self.proxy)
        self.table.setSortingEnabled(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._table_menu)
        tl.addWidget(self.table)
        center.addWidget(table_box)
        # No log panel in the main window (2.21.0): run output goes to one
        # persistent log file, shown in its own window (View > Log).
        root.addWidget(center)

        tabs = QTabWidget()
        self.detail = DetailPanel()
        self.sky_view = SkyView()
        self.sky = self.sky_view.map
        tabs.addTab(self.detail, "Object")
        tabs.addTab(self.sky_view, "Sky map")
        self.tabs = tabs
        root.addWidget(tabs)
        root.setStretchFactor(0, 0)
        root.setStretchFactor(1, 3)
        root.setStretchFactor(2, 2)
        root.setSizes([330, 700, 420])

        self.cmb_class.currentTextChanged.connect(self._filters_changed)
        self.cmb_status.currentTextChanged.connect(self._filters_changed)
        # Debounced: every keystroke refiltered the table and repainted the map.
        self._filter_timer = QTimer(self)
        self._filter_timer.setSingleShot(True)
        self._filter_timer.setInterval(200)
        self._filter_timer.timeout.connect(self._filters_changed)
        self.txt_search.textChanged.connect(self._filter_timer.start)
        self.chk_parts.toggled.connect(self._filters_changed)
        self.table.selectionModel().currentRowChanged.connect(self._row_changed)
        self.sky.objectClicked.connect(self._select_source_row)
        self.sky.centerPicked.connect(self._center_from_map)
        self.detail.btn_bookmark.clicked.connect(self.toggle_bookmark)

        self.progress = QProgressBar()
        self.progress.setMaximumWidth(260)
        self.progress.setVisible(False)
        self.statusBar().addPermanentWidget(self.progress)

    def _build_controls(self) -> QWidget:
        box = QWidget()
        box.setMinimumWidth(340)
        lay = QVBoxLayout(box)
        area = QGroupBox("Search area")
        f = QFormLayout(area)
        tgt_row = QHBoxLayout()
        self.txt_name = QLineEdit()
        self.txt_name.setPlaceholderText("NGC 4522  ·  188.4155 +9.1751  ·  12:33:39.7 +09:10:30")
        self.txt_name.setToolTip(
            "Object name (resolved with CDS Sesame) or coordinates:\n"
            "decimal degrees, hh:mm:ss ±dd:mm:ss, or 12h33m39.7s +9d10m30s"
        )
        self.btn_resolve = QPushButton("Set")
        tgt_row.addWidget(self.txt_name)
        tgt_row.addWidget(self.btn_resolve)
        f.addRow("Centre", tgt_row)
        self.sp_ra = _spin(0, 360, 6, " °")
        self.sp_dec = _spin(-90, 90, 6, " °")
        self.sp_ra.setWrapping(True)
        f.addRow("RA", self.sp_ra)
        f.addRow("Dec", self.sp_dec)
        rad_row = QHBoxLayout()
        self.sp_rad = _spin(0.001, 180, 3, "")
        self.cmb_rad_unit = QComboBox()
        self.cmb_rad_unit.addItems(list(RADIUS_UNITS))
        rad_row.addWidget(self.sp_rad, 1)
        rad_row.addWidget(self.cmb_rad_unit)
        f.addRow("Radius", rad_row)
        self.lbl_area = QLabel("")
        self.lbl_area.setStyleSheet("color: gray;")
        self.lbl_area.setWordWrap(True)
        f.addRow(self.lbl_area)
        lay.addWidget(area)

        src = QGroupBox("Data source")
        fs = QFormLayout(src)
        self.rb_sky = QRadioButton("Query archives for the search area")
        self.rb_raw = QRadioButton("Use collected catalogs")
        self.rb_sky.setChecked(True)
        fs.addRow(self.rb_sky)
        fs.addRow(self.rb_raw)
        raw_row = QHBoxLayout()
        self.txt_raw = QLineEdit()
        b = QPushButton("…")
        b.clicked.connect(lambda: self._pick_dir(self.txt_raw))
        raw_row.addWidget(self.txt_raw)
        raw_row.addWidget(b)
        fs.addRow("Folder", raw_row)
        self.chk_area = QCheckBox("Keep only objects inside the search area")
        self.chk_area.setChecked(True)
        fs.addRow(self.chk_area)
        lay.addWidget(src)

        opt = QGroupBox("Options")
        fo = QFormLayout(opt)
        out_row = QHBoxLayout()
        self.txt_work = QLineEdit()
        b2 = QPushButton("…")
        b2.clicked.connect(lambda: self._pick_dir(self.txt_work))
        out_row.addWidget(self.txt_work)
        out_row.addWidget(b2)
        fo.addRow("Output", out_row)
        self.sp_minconf = _spin(0.0, 0.99, 2, "")
        self.sp_minconf.setSpecialValueText("model default")
        fo.addRow("Min confidence", self.sp_minconf)
        self.chk_prior = QCheckBox("Re-weight by field class mix (EM)")
        self.chk_prior.setToolTip("Off by default: on real fields the estimate lowered accuracy in 4 of 5 checks.")
        fo.addRow(self.chk_prior)
        self.sp_workers = QDoubleSpinBox()
        self.sp_workers.setDecimals(0)
        self.sp_workers.setRange(1, 16)
        self.sp_workers.setValue(6)
        fo.addRow("Parallel queries", self.sp_workers)
        lay.addWidget(opt)

        run_row = QHBoxLayout()
        self.btn_run = QPushButton("Run")
        self.btn_run.setDefault(True)
        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.setEnabled(False)
        self.btn_log = QPushButton("Log")
        self.btn_log.setToolTip(f"Show the log file\n{self.applog.path}")
        run_row.addWidget(self.btn_run)
        run_row.addWidget(self.btn_cancel)
        run_row.addWidget(self.btn_log)
        lay.addLayout(run_row)
        self.lbl_state = QLabel("")
        self.lbl_state.setWordWrap(True)
        lay.addWidget(self.lbl_state)
        lay.addStretch(1)

        self.btn_run.clicked.connect(self.start_run)
        self.btn_cancel.clicked.connect(self.cancel_run)
        self.btn_log.clicked.connect(self.show_log)
        self.btn_resolve.clicked.connect(self._resolve_name)
        self.txt_name.returnPressed.connect(self._resolve_name)
        self.rb_sky.toggled.connect(self._mode_changed)
        self.chk_area.toggled.connect(self._area_changed)
        self.cmb_rad_unit.currentTextChanged.connect(self._unit_changed)
        for w in (self.sp_ra, self.sp_dec, self.sp_rad):
            w.valueChanged.connect(self._area_changed)
        self._rad_unit = self.cmb_rad_unit.currentText()
        self._mode_changed()
        return box

    def _action(self, menu, text, slot, shortcut=None) -> QAction:
        a = QAction(text, self)
        if shortcut is not None:
            a.setShortcut(shortcut)
        a.triggered.connect(slot)
        menu.addAction(a)
        return a

    def _build_menu(self):
        m = self.menuBar().addMenu("&File")
        self._action(m, "&Open results…", self._open_results, QKeySequence.Open)
        self._action(m, "&Export table as CSV…", self._export, "Ctrl+E")
        m.addSeparator()
        self._action(m, "&Quit", self.close, QKeySequence.Quit)
        v = self.menuBar().addMenu("&View")
        self._action(v, "&Log", self.show_log, "Ctrl+L")
        b = self.menuBar().addMenu("&Bookmarks")
        self.a_bookmark = self._action(b, "&Bookmark selected object", self.toggle_bookmark, "Ctrl+D")
        self._action(b, "&Show bookmarks", lambda: self.pages.setCurrentWidget(self.bookmark_page), "Ctrl+B")
        h = self.menuBar().addMenu("&Help")
        self._action(h, "&About", self._about)

    # ----------------------------------------------------------- inputs
    def _mode_changed(self):
        sky = self.rb_sky.isChecked()
        self.sp_workers.setEnabled(sky)
        self.txt_raw.setEnabled(not sky)
        self.chk_area.setEnabled(not sky)
        self._area_changed()

    def _area_used(self) -> bool:
        return self.rb_sky.isChecked() or self.chk_area.isChecked()

    def radius_arcmin(self) -> float:
        return self.sp_rad.value() * RADIUS_UNITS[self.cmb_rad_unit.currentText()]

    def _unit_changed(self, unit: str):
        """Keep the same angle when the unit changes."""
        arcmin = self.sp_rad.value() * RADIUS_UNITS[self._rad_unit]
        self._rad_unit = unit
        self._apply_unit_range(unit)
        self.sp_rad.setValue(arcmin / RADIUS_UNITS[unit])

    def _apply_unit_range(self, unit: str):
        k = RADIUS_UNITS[unit]
        self.sp_rad.setDecimals(RADIUS_DECIMALS[unit])
        self.sp_rad.setRange(RADIUS_RANGE_ARCMIN[0] / k, RADIUS_RANGE_ARCMIN[1] / k)
        self.sp_rad.setSingleStep(10 ** -max(RADIUS_DECIMALS[unit] - 1, 0))

    def _area_changed(self, *_):
        used = self._area_used()
        for w in (self.txt_name, self.btn_resolve, self.sp_ra, self.sp_dec, self.sp_rad, self.cmb_rad_unit):
            w.setEnabled(used)
        r = self.radius_arcmin()
        text = (
            f"Cone r = {r * 60:.1f}″ = {r:.3f}′ = {r / 60:.4f}° around RA {self.sp_ra.value():.5f}, "
            f"Dec {self.sp_dec.value():+.5f}"
        )
        if self.rb_sky.isChecked() and r > MAX_QUERY_ARCMIN:
            text += f"  ⚠ above {MAX_QUERY_ARCMIN:g}′ archive queries get slow and may time out"
        self.lbl_area.setText(text if used else "Whole folder (no area cut)")
        if hasattr(self, "sky"):
            self.sky.set_area((self.sp_ra.value(), self.sp_dec.value(), r) if used else None)

    def _pick_dir(self, edit: QLineEdit):
        d = QFileDialog.getExistingDirectory(self, "Choose folder", edit.text() or str(Path.home()))
        if d:
            edit.setText(d)

    def _resolve_name(self):
        name = self.txt_name.text().strip()
        if not name:
            return
        coords = parse_coordinates(name)
        # Every request, typed coordinates included, gets a new number; only
        # the answer to the latest one is applied (2.19.0 for names; 2.23.0:
        # an older name lookup no longer overwrites coordinates typed after it).
        if coords is not None:  # typed coordinates: no network needed
            self._lookup_id += 1
            self._pending_name = None
            self._apply_position(*coords, name)
            return
        if self._pending_name == name:
            return  # same lookup already running (Return pressed again)
        self._lookup_id += 1
        self._pending_name = name
        self.btn_resolve.setEnabled(False)
        self._status(f"Resolving {name}…")
        job = _NameResolver(self._lookup_id, name)
        job.signals.done.connect(self._resolved)
        # Bound methods, not lambdas: the runnable's signal object is deleted
        # after run(), and queued calls to a lambda slot were then dropped.
        job.signals.failed.connect(self._resolve_failed)
        QThreadPool.globalInstance().start(job)

    def _center_from_map(self, ra, dec):
        if self._area_used():
            self.sp_ra.setValue(ra)
            self.sp_dec.setValue(dec)
            self._status(f"Centre set from map: RA {ra:.6f}, Dec {dec:+.6f}")

    def _resolve_failed(self, request, msg):
        if request != self._lookup_id:
            return  # failure of a superseded lookup
        self._pending_name = None
        self.btn_resolve.setEnabled(True)
        self._status(f"Could not resolve {msg}")

    def _resolved(self, request, ra, dec, name):
        if request != self._lookup_id:
            return  # answer of a superseded lookup
        self._pending_name = None
        self._apply_position(ra, dec, name)

    def _apply_position(self, ra, dec, name):
        self.sp_ra.setValue(ra)
        self.sp_dec.setValue(dec)
        self.btn_resolve.setEnabled(True)
        self._status(f"{name}: RA {ra:.6f}, Dec {dec:+.6f}")

    def pipeline_args(self) -> list[str]:
        work = Path(self.txt_work.text().strip() or Path.home() / "finding_objects_runs" / "run")
        args = ["--work", str(work)]
        area = [
            "--ra",
            f"{self.sp_ra.value():.7f}",
            "--dec",
            f"{self.sp_dec.value():.7f}",
            "--radius",
            f"{self.radius_arcmin():.6f}",
        ]
        if self.rb_sky.isChecked():
            args += area + ["--workers", str(int(self.sp_workers.value()))]
        else:
            raw = self.txt_raw.text().strip()
            if not raw or not Path(raw).is_dir():
                raise ValueError("Choose a folder of collected catalog CSV files.")
            args += ["--raw-dir", raw] + (area if self.chk_area.isChecked() else [])
        if self.sp_minconf.value() > 0:
            args += ["--min-confidence", f"{self.sp_minconf.value():.2f}"]
        if self.chk_prior.isChecked():
            args.append("--field-prior")
        return args

    # -------------------------------------------------------------- run
    def start_run(self):
        try:
            args = self.pipeline_args()
        except ValueError as exc:
            QMessageBox.warning(self, APP_NAME, str(exc))
            return
        self._save()
        self.work_dir = Path(args[1])
        self.tracker = ProgressTracker(collecting=self.rb_sky.isChecked())
        self.applog.start_run(f"run {APP_NAME}")
        self._log("$ pipeline " + " ".join(args))
        self._out_buf = b""
        self.proc = QProcess(self)
        self.proc.setProcessChannelMode(QProcess.MergedChannels)
        env = QProcessEnvironment.systemEnvironment()
        env.insert("PYTHONUNBUFFERED", "1")
        # The worker writes UTF-8, which _read_output decodes: on Windows a pipe
        # otherwise uses the ANSI code page (mojibake, or a UnicodeEncodeError
        # on a non-ASCII path after the results were written; 2.23.0).
        env.insert("PYTHONIOENCODING", "utf-8")
        self.proc.setProcessEnvironment(env)
        self.proc.readyReadStandardOutput.connect(self._read_output)
        self.proc.finished.connect(self._finished)
        # A worker that cannot start emits only errorOccurred, never finished.
        self.proc.errorOccurred.connect(self._proc_error)
        program, pre = worker_command()
        self.proc.start(program, [*pre, "--pipeline", *args])
        self.btn_run.setEnabled(False)
        self.btn_cancel.setEnabled(True)
        self.progress.setVisible(True)
        self.progress.setRange(0, 1000)
        self.progress.setValue(0)
        self._status("Running…")

    def cancel_run(self):
        if self.proc and self.proc.state() != QProcess.NotRunning:
            self._log("Cancelled by user.")
            self.proc.kill()

    def _proc_error(self, error):
        if error == QProcess.FailedToStart:
            self._log("The pipeline worker could not be started.")
            self._finished(-1, QProcess.CrashExit)

    def _read_output(self):
        if self.proc is None:
            return
        # Keep partial lines (and split UTF-8 sequences) until the newline arrives.
        self._out_buf += bytes(self.proc.readAllStandardOutput())
        *complete, self._out_buf = self._out_buf.split(b"\n")
        lines = [raw.decode("utf-8", "replace").rstrip("\r") for raw in complete]
        self.applog.write_lines(lines)  # one file write per output chunk
        for line in lines:
            msg = self.tracker.feed(line) if self.tracker else None
            if msg:
                self.progress.setValue(int(self.tracker.fraction * 1000))
                self._status(msg)

    def _finished(self, code, status):
        if self.proc is not None:
            self._read_output()
            if self._out_buf:
                self._log(self._out_buf.decode("utf-8", "replace"))
                self._out_buf = b""
            self._log(f"worker exited: code {code}, {'crashed' if status == QProcess.CrashExit else 'normal exit'}")
            self.proc.deleteLater()  # one QProcess per run, released when it ends
            self.proc = None
        self.btn_run.setEnabled(True)
        self.btn_cancel.setEnabled(False)
        self.progress.setVisible(False)
        failed = self.tracker.failed_archives if self.tracker else []
        if status == QProcess.NormalExit and code == 0 and self.work_dir and (self.work_dir / RESULT_FILE).exists():
            self.load_results(self.work_dir / RESULT_FILE)
            note = f" — unavailable archives: {', '.join(failed)}" if failed else ""
            self._status(f"Done{note}")
        else:
            self._status("Run failed or was cancelled; see View > Log.")

    # ---------------------------------------------------------- results
    def load_results(self, path: Path) -> bool:
        """Show a results file; False (and the previous results kept) if it cannot be read."""
        try:
            df = pd.read_csv(path, low_memory=False)
        except Exception as exc:  # unreadable / malformed file chosen by the user
            QMessageBox.warning(self, APP_NAME, f"Could not read {path}:\n{exc}")
            return False
        assoc = path.parent / "source_association.csv"
        if "designation" not in df.columns and assoc.exists():  # results written before designations existed
            df = _designations().annotate(
                df, pd.read_csv(assoc, low_memory=False, dtype={"catalog_object_id": "string"})
            )
        self.model.set_frame(df)
        self.results_path = path
        self.sky.set_frame(self.model.frame(), self.model.kinds())
        cols = [self.model.column_name(i) for i in range(self.model.columnCount())]
        if "separation_arcmin" in cols:  # nearest to the search centre first
            self.table.sortByColumn(cols.index("separation_arcmin"), Qt.AscendingOrder)
        self.table.resizeColumnsToContents()
        self.detail.show_object(None)
        self._filters_changed()
        self.setWindowTitle(f"{APP_NAME} — {path.parent}")
        return True

    def _visible_source_rows(self) -> list[int]:
        """Results-frame rows the filtered table shows, in table order."""
        return [self.proxy.mapToSource(self.proxy.index(i, 0)).row() for i in range(self.proxy.rowCount())]

    def _filters_changed(self):
        self.proxy.set_class(self.cmb_class.currentText())
        self.proxy.set_status(self.cmb_status.currentText())
        self.proxy.set_text(self.txt_search.text())
        self.proxy.set_show_components(self.chk_parts.isChecked())
        self.sky.set_visible_rows(self._visible_source_rows())
        df = self.model.frame()
        if not df.empty and "primary_class" in df:
            top = df[df.parent_object_id.isna()] if "parent_object_id" in df else df
            counts = top.primary_class.value_counts()
            parts = len(df) - len(top)
            self.lbl_counts.setText(
                f"{self.proxy.rowCount()} shown / {len(top)} objects"
                + (f" (+{parts} galaxy parts)" if parts else "")
                + " · "
                + " · ".join(f"{k} {v}" for k, v in counts.items())
            )
        else:
            self.lbl_counts.setText("0 objects")

    def _row_changed(self, current: QModelIndex, _prev):
        if not current.isValid():
            self.detail.show_object(None)
            self.sky.set_selected(None)
            return
        src = self.proxy.mapToSource(current).row()
        row = self.model.frame().iloc[src]
        self.detail.show_object(row)
        self.detail.set_bookmarked(self._is_bookmarked(row))
        self.sky.set_selected(src)

    # -------------------------------------------------------- bookmarks
    def selected_row(self):
        idx = self.table.selectionModel().currentIndex() if self.table.selectionModel() else QModelIndex()
        if not idx.isValid():
            return None
        return self.model.frame().iloc[self.proxy.mapToSource(idx).row()]

    def _is_bookmarked(self, row) -> bool:
        return row is not None and self.bookmarks.find(row) is not None

    def toggle_bookmark(self):
        """Bookmark the selected object, or remove its bookmark."""
        row = self.selected_row()
        if row is None:
            self._status("Select an object to bookmark.")
            return
        # toggle() only appends a new item or drops one (existing dicts are
        # not changed), so the old list restores the in-memory state that
        # matches the file when saving fails.
        items = list(self.bookmarks.items)
        try:
            on = self.bookmarks.toggle(row, str(self.results_path) if self.results_path else None)
        except OSError as exc:  # bookmark folder not writable, disk full, ...
            self.bookmarks.items = items
            QMessageBox.warning(self, APP_NAME, f"Could not save bookmarks to {self.bookmarks.path}:\n{exc}")
            return
        self.detail.set_bookmarked(on)
        self.bookmark_page.refresh()
        name = self.bookmarks.snapshot(row)["name"] or "object"
        self._status(f"Bookmarked {name}" if on else f"Removed bookmark of {name}")

    def _table_menu(self, pos):
        idx = self.table.indexAt(pos)
        if not idx.isValid():
            return
        self.table.selectRow(idx.row())
        row = self.selected_row()
        menu = QMenu(self)
        on = self._is_bookmarked(row)
        act = menu.addAction("Remove bookmark" if on else "Bookmark")
        act.triggered.connect(self.toggle_bookmark)
        menu.exec(self.table.viewport().mapToGlobal(pos))

    def _page_changed(self, index):
        if self.pages.widget(index) is self.bookmark_page:
            self.bookmark_page.refresh()
        else:
            self.detail.set_bookmarked(self._is_bookmarked(self.selected_row()))

    def open_bookmark(self, b: dict):
        """Load the results the bookmark came from and select the object."""
        path = Path(b["source"])
        if self.results_path != path and not self.load_results(path):
            return  # unreadable: do not pick a row of the results still shown
        df = self.model.frame()
        hit = None
        for col, key in (("designation", "name"), ("object_name", "name"), ("object_id", "object_id")):
            if col in df and b.get(key):
                m = df.index[df[col].astype(str) == str(b[key])]
                if len(m):
                    hit = df.index.get_loc(m[0])
                    break
        self.pages.setCurrentIndex(0)
        if hit is None:
            self._status(f"{b.get('name') or 'Object'} is not in {path.name} any more.")
            return
        if (
            not self.chk_parts.isChecked()
            and "parent_object_id" in df
            and pd.notna(df.iloc[hit].get("parent_object_id"))
        ):
            self.chk_parts.setChecked(True)  # a bookmarked galaxy part is hidden by default
        self.cmb_class.setCurrentText("ALL")
        self.cmb_status.setCurrentText("ALL")
        self.txt_search.clear()
        self._filters_changed()
        self._select_source_row(hit)

    def search_bookmark(self, ra: float, dec: float, name: str):
        """Use a bookmark's position as the centre of a new search."""
        self.rb_sky.setChecked(True)
        self.sp_ra.setValue(ra)
        self.sp_dec.setValue(dec)
        self.txt_name.setText(name or f"{ra:.6f} {dec:+.6f}")
        self.pages.setCurrentIndex(0)
        self._status(f"Search centre set to {name or 'bookmark'} — press Run.")

    def _select_source_row(self, src_row: int):
        idx = self.proxy.mapFromSource(self.model.index(src_row, 0))
        if idx.isValid():
            self.table.selectRow(idx.row())
            self.table.scrollTo(idx)

    def _open_results(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Open results",
            self.txt_work.text() or str(Path.home()),
            "Classified objects (classified_objects.csv);;CSV (*.csv)",
        )
        if path:
            self.load_results(Path(path))

    def _export(self):
        df = self.model.frame()
        if df.empty:
            QMessageBox.information(self, APP_NAME, "No results to export yet.")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Export", str(Path.home() / "classified.csv"), "CSV (*.csv)")
        if path:
            rows = self._visible_source_rows()
            try:
                df.iloc[rows].to_csv(path, index=False)
            except OSError as exc:  # e.g. the file is open in Excel
                QMessageBox.warning(self, APP_NAME, f"Could not write {path}:\n{exc}")
                return
            self._status(f"Exported {len(rows)} rows to {path}")

    def _about(self):
        QMessageBox.about(
            self,
            APP_NAME,
            "Finding Objects — multi-wavelength STAR/GALAXY/QSO classifier (v2).\n"
            "Coarse fusion fitted on SDSS + DESI spectroscopic benchmarks; "
            "see v2/Preprocess/COARSE_BENCHMARK_RESULTS.md.",
        )

    # ------------------------------------------------------------ misc
    def _log(self, text):
        self.applog.write(text)

    def show_log(self):
        """Open (or raise) the separate log window; the file is created if missing."""
        if self.log_window is None:
            self.log_window = LogWindow(self.applog, self)
        self.applog.ensure()
        self.log_window.show()
        self.log_window.raise_()
        self.log_window.activateWindow()

    def _status(self, text):
        self.lbl_state.setText(text)
        self.statusBar().showMessage(text)

    def _save(self):
        s = self.settings
        for k, attr, _ in SPINS:
            s.setValue(k, getattr(self, attr).value())
        s.setValue("radius_unit", self.cmb_rad_unit.currentText())
        s.setValue("area_cut", self.chk_area.isChecked())
        s.setValue("work", self.txt_work.text())
        s.setValue("raw", self.txt_raw.text())
        s.setValue("name", self.txt_name.text())
        s.setValue("mode_raw", self.rb_raw.isChecked())
        s.setValue("field_prior", self.chk_prior.isChecked())

    def _restore(self):
        s = self.settings
        unit = str(s.value("radius_unit", "arcmin"))
        if unit in RADIUS_UNITS:
            self.cmb_rad_unit.blockSignals(True)
            self.cmb_rad_unit.setCurrentText(unit)
            self.cmb_rad_unit.blockSignals(False)
            self._rad_unit = unit
        self._apply_unit_range(self._rad_unit)
        self.chk_area.setChecked(str(s.value("area_cut", "true")).lower() == "true")
        for k, attr, d in SPINS:
            getattr(self, attr).setValue(float(s.value(k, d)))
        self.txt_work.setText(str(s.value("work", Path.home() / "finding_objects_runs" / "run")))
        self.txt_raw.setText(str(s.value("raw", "")))
        self.txt_name.setText(str(s.value("name", "")))
        (self.rb_raw if str(s.value("mode_raw", "false")).lower() == "true" else self.rb_sky).setChecked(True)
        self.chk_prior.setChecked(str(s.value("field_prior", "false")).lower() == "true")
        self._mode_changed()

    def closeEvent(self, event):
        self._save()
        # A note typed just before closing is still waiting for its debounce timer.
        try:
            self.bookmark_page._save_note()
        except OSError as exc:  # closing must not fail on an unwritable bookmark file
            QMessageBox.warning(self, APP_NAME, f"Could not save the bookmark note:\n{exc}")
        if self.proc and self.proc.state() != QProcess.NotRunning:
            self.proc.kill()
            self.proc.waitForFinished(3000)
        super().closeEvent(event)


def worker_command() -> tuple[str, list[str]]:
    """Program + leading args that start this app in ``--pipeline`` worker mode."""
    if getattr(sys, "frozen", False):  # PyInstaller: the executable is the app
        return sys.executable, []
    return sys.executable, [str(Path(__file__).resolve())]


def _spin(lo, hi, decimals, suffix):
    s = QDoubleSpinBox()
    s.setRange(lo, hi)
    s.setDecimals(decimals)
    s.setSuffix(suffix)
    s.setSingleStep(10 ** -min(decimals, 2))
    return s


def main():
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    w = MainWindow()
    w.show()
    if len(sys.argv) > 1 and Path(sys.argv[1]).is_file():  # optional: open a results CSV directly
        w.load_results(Path(sys.argv[1]))
    code = app.exec()
    # Destroy the window (and its children) while QApplication still exists;
    # Qt objects outliving it at interpreter exit can crash on shutdown.
    w.deleteLater()
    app.processEvents()
    del w
    return code


if __name__ == "__main__":
    raise SystemExit(main())
