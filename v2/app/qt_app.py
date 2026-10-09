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
from app_paths import v2_root  # noqa: E402
V2 = v2_root()


def _worker_main(argv: list[str]) -> int:
    """Run v2/pipeline.py's CLI in this process (``--pipeline`` mode)."""
    import importlib.util
    sys.path.insert(0, str(V2))
    spec = importlib.util.spec_from_file_location("v2_pipeline", V2 / "pipeline.py")
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    sys.argv = ["pipeline.py", *argv]
    mod.main()
    return 0


if __name__ == "__main__" and len(sys.argv) > 1 and sys.argv[1] == "--pipeline":
    raise SystemExit(_worker_main(sys.argv[2:]))

import pandas as pd  # noqa: E402
from PySide6.QtCore import QModelIndex, QProcess, QProcessEnvironment, QSettings, Qt, QThreadPool, QRunnable, QObject, Signal  # noqa: E402
from PySide6.QtGui import QAction, QKeySequence  # noqa: E402
from PySide6.QtWidgets import (QApplication, QComboBox, QDoubleSpinBox, QFileDialog, QFormLayout, QGroupBox,  # noqa: E402
                               QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMainWindow, QMessageBox,
                               QPlainTextEdit, QProgressBar, QPushButton, QRadioButton, QSplitter,
                               QTableView, QTabWidget, QVBoxLayout, QWidget, QAbstractItemView, QCheckBox)

from progress import ProgressTracker  # noqa: E402
from qt_models import DataFrameModel, ResultsFilter  # noqa: E402
from qt_widgets import DetailPanel, SkyMap  # noqa: E402

APP_NAME = "Finding Objects"
RESULT_FILE = "classified_objects.csv"


class _NameResolver(QRunnable):
    """Resolve an object name to ICRS coordinates (CDS Sesame) off the GUI thread."""

    class Signals(QObject):
        done = Signal(float, float, str)
        failed = Signal(str)

    def __init__(self, name: str):
        super().__init__()
        self.name = name
        self.signals = self.Signals()

    def run(self):
        try:
            from astropy.coordinates import SkyCoord
            c = SkyCoord.from_name(self.name)
            self.signals.done.emit(float(c.icrs.ra.deg), float(c.icrs.dec.deg), self.name)
        except Exception as exc:  # network / unknown name
            self.signals.failed.emit(f"{self.name}: {exc}")


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.resize(1400, 860)
        self.settings = QSettings("FindingObjects", "v2")
        self.proc: QProcess | None = None
        self.tracker: ProgressTracker | None = None
        self.work_dir: Path | None = None
        self.model = DataFrameModel(parent=self)
        self.proxy = ResultsFilter(self); self.proxy.setSourceModel(self.model)
        self._build_ui()
        self._build_menu()
        self._restore()

    # ---------------------------------------------------------------- UI
    def _build_ui(self):
        root = QSplitter(Qt.Horizontal, self)
        self.setCentralWidget(root)
        root.addWidget(self._build_controls())

        center = QSplitter(Qt.Vertical)
        table_box = QWidget(); tl = QVBoxLayout(table_box); tl.setContentsMargins(0, 0, 0, 0)
        bar = QHBoxLayout()
        self.cmb_class = QComboBox(); self.cmb_class.addItems(["ALL", "STAR", "GALAXY", "QSO", "UNKNOWN"])
        self.cmb_status = QComboBox(); self.cmb_status.addItems(["ALL", "CLASSIFIED", "LOW_CONFIDENCE", "NO_EVIDENCE",
                                                                 "CONFLICT", "WITHIN_LARGE_GALAXY"])
        self.txt_search = QLineEdit(); self.txt_search.setPlaceholderText("Search object id / catalog…")
        self.lbl_counts = QLabel("")
        for w in (QLabel("Class"), self.cmb_class, QLabel("Status"), self.cmb_status, self.txt_search):
            bar.addWidget(w)
        bar.addStretch(1); bar.addWidget(self.lbl_counts)
        tl.addLayout(bar)
        self.table = QTableView(); self.table.setModel(self.proxy); self.table.setSortingEnabled(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows); self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setAlternatingRowColors(True); self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.table.horizontalHeader().setStretchLastSection(True)
        tl.addWidget(self.table)
        center.addWidget(table_box)
        self.log = QPlainTextEdit(); self.log.setReadOnly(True); self.log.setMaximumBlockCount(5000)
        center.addWidget(self.log)
        center.setStretchFactor(0, 4); center.setStretchFactor(1, 1)
        root.addWidget(center)

        tabs = QTabWidget()
        self.detail = DetailPanel(); self.sky = SkyMap()
        tabs.addTab(self.detail, "Object"); tabs.addTab(self.sky, "Sky map")
        root.addWidget(tabs)
        root.setStretchFactor(0, 0); root.setStretchFactor(1, 3); root.setStretchFactor(2, 2)
        root.setSizes([330, 700, 420])

        self.cmb_class.currentTextChanged.connect(self._filters_changed)
        self.cmb_status.currentTextChanged.connect(self._filters_changed)
        self.txt_search.textChanged.connect(self._filters_changed)
        self.table.selectionModel().currentRowChanged.connect(self._row_changed)
        self.sky.objectClicked.connect(self._select_source_row)

        self.progress = QProgressBar(); self.progress.setMaximumWidth(260); self.progress.setVisible(False)
        self.statusBar().addPermanentWidget(self.progress)

    def _build_controls(self) -> QWidget:
        box = QWidget(); box.setMinimumWidth(320); lay = QVBoxLayout(box)
        tgt = QGroupBox("Target"); f = QFormLayout(tgt)
        self.rb_sky = QRadioButton("Query archives"); self.rb_raw = QRadioButton("Use collected catalogs")
        self.rb_sky.setChecked(True)
        f.addRow(self.rb_sky)
        name_row = QHBoxLayout()
        self.txt_name = QLineEdit(); self.txt_name.setPlaceholderText("e.g. NGC 4522")
        self.btn_resolve = QPushButton("Resolve"); name_row.addWidget(self.txt_name); name_row.addWidget(self.btn_resolve)
        f.addRow("Name", name_row)
        self.sp_ra = _spin(0, 360, 6, " °"); self.sp_dec = _spin(-90, 90, 6, " °"); self.sp_rad = _spin(0.05, 30, 2, " ′")
        f.addRow("RA", self.sp_ra); f.addRow("Dec", self.sp_dec); f.addRow("Radius", self.sp_rad)
        f.addRow(self.rb_raw)
        raw_row = QHBoxLayout(); self.txt_raw = QLineEdit(); b = QPushButton("…")
        b.clicked.connect(lambda: self._pick_dir(self.txt_raw)); raw_row.addWidget(self.txt_raw); raw_row.addWidget(b)
        f.addRow("Folder", raw_row)
        lay.addWidget(tgt)

        opt = QGroupBox("Options"); fo = QFormLayout(opt)
        out_row = QHBoxLayout(); self.txt_work = QLineEdit(); b2 = QPushButton("…")
        b2.clicked.connect(lambda: self._pick_dir(self.txt_work)); out_row.addWidget(self.txt_work); out_row.addWidget(b2)
        fo.addRow("Output", out_row)
        self.sp_minconf = _spin(0.0, 0.99, 2, ""); self.sp_minconf.setSpecialValueText("model default")
        fo.addRow("Min confidence", self.sp_minconf)
        self.chk_prior = QCheckBox("Re-weight by field class mix (EM)")
        self.chk_prior.setToolTip("Off by default: on real fields the estimate lowered accuracy in 4 of 5 checks.")
        fo.addRow(self.chk_prior)
        self.sp_workers = QDoubleSpinBox(); self.sp_workers.setDecimals(0); self.sp_workers.setRange(1, 16); self.sp_workers.setValue(6)
        fo.addRow("Parallel queries", self.sp_workers)
        lay.addWidget(opt)

        run_row = QHBoxLayout()
        self.btn_run = QPushButton("Run"); self.btn_run.setDefault(True)
        self.btn_cancel = QPushButton("Cancel"); self.btn_cancel.setEnabled(False)
        run_row.addWidget(self.btn_run); run_row.addWidget(self.btn_cancel)
        lay.addLayout(run_row)
        self.lbl_state = QLabel(""); self.lbl_state.setWordWrap(True)
        lay.addWidget(self.lbl_state)
        lay.addStretch(1)

        self.btn_run.clicked.connect(self.start_run)
        self.btn_cancel.clicked.connect(self.cancel_run)
        self.btn_resolve.clicked.connect(self._resolve_name)
        self.txt_name.returnPressed.connect(self._resolve_name)
        self.rb_sky.toggled.connect(self._mode_changed)
        self._mode_changed()
        return box

    def _build_menu(self):
        m = self.menuBar().addMenu("&File")
        a_open = QAction("&Open results…", self); a_open.setShortcut(QKeySequence.Open); a_open.triggered.connect(self._open_results)
        a_exp = QAction("&Export table as CSV…", self); a_exp.setShortcut("Ctrl+E"); a_exp.triggered.connect(self._export)
        a_quit = QAction("&Quit", self); a_quit.setShortcut(QKeySequence.Quit); a_quit.triggered.connect(self.close)
        for a in (a_open, a_exp):
            m.addAction(a)
        m.addSeparator(); m.addAction(a_quit)
        h = self.menuBar().addMenu("&Help")
        a_about = QAction("&About", self); a_about.triggered.connect(self._about); h.addAction(a_about)

    # ----------------------------------------------------------- inputs
    def _mode_changed(self):
        sky = self.rb_sky.isChecked()
        for w in (self.txt_name, self.btn_resolve, self.sp_ra, self.sp_dec, self.sp_rad, self.sp_workers):
            w.setEnabled(sky)
        self.txt_raw.setEnabled(not sky)

    def _pick_dir(self, edit: QLineEdit):
        d = QFileDialog.getExistingDirectory(self, "Choose folder", edit.text() or str(Path.home()))
        if d:
            edit.setText(d)

    def _resolve_name(self):
        name = self.txt_name.text().strip()
        if not name:
            return
        self.btn_resolve.setEnabled(False); self._status(f"Resolving {name}…")
        job = _NameResolver(name)
        job.signals.done.connect(self._resolved)
        job.signals.failed.connect(lambda msg: (self.btn_resolve.setEnabled(True), self._status(f"Could not resolve {msg}")))
        QThreadPool.globalInstance().start(job)

    def _resolved(self, ra, dec, name):
        self.sp_ra.setValue(ra); self.sp_dec.setValue(dec); self.btn_resolve.setEnabled(True)
        self._status(f"{name}: RA {ra:.6f}, Dec {dec:+.6f}")

    def pipeline_args(self) -> list[str]:
        work = Path(self.txt_work.text().strip() or Path.home() / "finding_objects_runs" / "run")
        args = ["--work", str(work)]
        if self.rb_sky.isChecked():
            args += ["--ra", f"{self.sp_ra.value():.7f}", "--dec", f"{self.sp_dec.value():.7f}",
                     "--radius", f"{self.sp_rad.value():.4f}", "--workers", str(int(self.sp_workers.value()))]
        else:
            raw = self.txt_raw.text().strip()
            if not raw or not Path(raw).is_dir():
                raise ValueError("Choose a folder of collected catalog CSV files.")
            args += ["--raw-dir", raw]
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
            QMessageBox.warning(self, APP_NAME, str(exc)); return
        self._save()
        self.work_dir = Path(args[1])
        self.tracker = ProgressTracker(collecting=self.rb_sky.isChecked())
        self.log.clear(); self._log("$ pipeline " + " ".join(args))
        self.proc = QProcess(self)
        self.proc.setProcessChannelMode(QProcess.MergedChannels)
        env = QProcessEnvironment.systemEnvironment(); env.insert("PYTHONUNBUFFERED", "1")
        self.proc.setProcessEnvironment(env)
        self.proc.readyReadStandardOutput.connect(self._read_output)
        self.proc.finished.connect(self._finished)
        program, pre = worker_command()
        self.proc.start(program, [*pre, "--pipeline", *args])
        self.btn_run.setEnabled(False); self.btn_cancel.setEnabled(True)
        self.progress.setVisible(True); self.progress.setRange(0, 1000); self.progress.setValue(0)
        self._status("Running…")

    def cancel_run(self):
        if self.proc and self.proc.state() != QProcess.NotRunning:
            self._log("Cancelled by user.")
            self.proc.kill()

    def _read_output(self):
        data = bytes(self.proc.readAllStandardOutput()).decode("utf-8", "replace")
        for line in data.splitlines():
            self._log(line)
            msg = self.tracker.feed(line) if self.tracker else None
            if msg:
                self.progress.setValue(int(self.tracker.fraction * 1000)); self._status(msg)

    def _finished(self, code, status):
        self.btn_run.setEnabled(True); self.btn_cancel.setEnabled(False); self.progress.setVisible(False)
        failed = self.tracker.failed_archives if self.tracker else []
        if status == QProcess.NormalExit and code == 0 and self.work_dir and (self.work_dir / RESULT_FILE).exists():
            self.load_results(self.work_dir / RESULT_FILE)
            note = f" — unavailable archives: {', '.join(failed)}" if failed else ""
            self._status(f"Done{note}")
        else:
            self._status("Run failed or was cancelled; see the log.")

    # ---------------------------------------------------------- results
    def load_results(self, path: Path):
        df = pd.read_csv(path, low_memory=False)
        self.model.set_frame(df)
        self.sky.set_frame(self.model.frame())
        self.table.resizeColumnsToContents()
        self.detail.show_object(None)
        self._filters_changed()
        self.setWindowTitle(f"{APP_NAME} — {path.parent}")

    def _filters_changed(self):
        self.proxy.set_class(self.cmb_class.currentText())
        self.proxy.set_status(self.cmb_status.currentText())
        self.proxy.set_text(self.txt_search.text())
        rows = [self.proxy.mapToSource(self.proxy.index(i, 0)).row() for i in range(self.proxy.rowCount())]
        self.sky.set_visible_rows(rows)
        df = self.model.frame()
        if not df.empty and "primary_class" in df:
            counts = df.primary_class.value_counts()
            self.lbl_counts.setText(f"{self.proxy.rowCount()} shown / {len(df)} · " +
                                    " · ".join(f"{k} {v}" for k, v in counts.items()))

    def _row_changed(self, current: QModelIndex, _prev):
        if not current.isValid():
            self.detail.show_object(None); self.sky.set_selected(None); return
        src = self.proxy.mapToSource(current).row()
        self.detail.show_object(self.model.frame().iloc[src])
        self.sky.set_selected(src)

    def _select_source_row(self, src_row: int):
        idx = self.proxy.mapFromSource(self.model.index(src_row, 0))
        if idx.isValid():
            self.table.selectRow(idx.row()); self.table.scrollTo(idx)

    def _open_results(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open results", self.txt_work.text() or str(Path.home()),
                                              "Classified objects (classified_objects.csv);;CSV (*.csv)")
        if path:
            self.load_results(Path(path))

    def _export(self):
        df = self.model.frame()
        if df.empty:
            QMessageBox.information(self, APP_NAME, "No results to export yet."); return
        path, _ = QFileDialog.getSaveFileName(self, "Export", str(Path.home() / "classified.csv"), "CSV (*.csv)")
        if path:
            rows = [self.proxy.mapToSource(self.proxy.index(i, 0)).row() for i in range(self.proxy.rowCount())]
            df.iloc[rows].to_csv(path, index=False)
            self._status(f"Exported {len(rows)} rows to {path}")

    def _about(self):
        QMessageBox.about(self, APP_NAME,
                          "Finding Objects — multi-wavelength STAR/GALAXY/QSO classifier (v2).\n"
                          "Coarse fusion fitted on SDSS + DESI spectroscopic benchmarks; "
                          "see v2/Preprocess/COARSE_BENCHMARK_RESULTS.md.")

    # ------------------------------------------------------------ misc
    def _log(self, text):
        self.log.appendPlainText(text)

    def _status(self, text):
        self.lbl_state.setText(text); self.statusBar().showMessage(text)

    def _save(self):
        s = self.settings
        for k, w in (("ra", self.sp_ra), ("dec", self.sp_dec), ("radius", self.sp_rad), ("minconf", self.sp_minconf), ("workers", self.sp_workers)):
            s.setValue(k, w.value())
        s.setValue("work", self.txt_work.text()); s.setValue("raw", self.txt_raw.text()); s.setValue("name", self.txt_name.text())
        s.setValue("mode_raw", self.rb_raw.isChecked()); s.setValue("field_prior", self.chk_prior.isChecked())

    def _restore(self):
        s = self.settings
        for k, w, d in (("ra", self.sp_ra, 245.0), ("dec", self.sp_dec, 43.0), ("radius", self.sp_rad, 3.0),
                        ("minconf", self.sp_minconf, 0.0), ("workers", self.sp_workers, 6)):
            w.setValue(float(s.value(k, d)))
        self.txt_work.setText(str(s.value("work", Path.home() / "finding_objects_runs" / "run")))
        self.txt_raw.setText(str(s.value("raw", ""))); self.txt_name.setText(str(s.value("name", "")))
        (self.rb_raw if str(s.value("mode_raw", "false")).lower() == "true" else self.rb_sky).setChecked(True)
        self.chk_prior.setChecked(str(s.value("field_prior", "false")).lower() == "true")

    def closeEvent(self, event):
        self._save()
        if self.proc and self.proc.state() != QProcess.NotRunning:
            self.proc.kill(); self.proc.waitForFinished(3000)
        super().closeEvent(event)


def worker_command() -> tuple[str, list[str]]:
    """Program + leading args that start this app in ``--pipeline`` worker mode."""
    if getattr(sys, "frozen", False):           # PyInstaller: the executable is the app
        return sys.executable, []
    return sys.executable, [str(Path(__file__).resolve())]


def _spin(lo, hi, decimals, suffix):
    s = QDoubleSpinBox(); s.setRange(lo, hi); s.setDecimals(decimals); s.setSuffix(suffix); s.setSingleStep(10 ** -min(decimals, 2))
    return s


def main():
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    w = MainWindow(); w.show()
    if len(sys.argv) > 1 and Path(sys.argv[1]).is_file():   # optional: open a results CSV directly
        w.load_results(Path(sys.argv[1]))
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
