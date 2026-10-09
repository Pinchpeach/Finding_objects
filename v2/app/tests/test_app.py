import os
import sys
from pathlib import Path

import pytest

APP = Path(__file__).resolve().parents[1]
V2 = APP.parent
sys.path.insert(0, str(APP))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def test_progress_tracker_counts_archives_and_stages():
    from progress import ProgressTracker, STAGES
    t = ProgressTracker(collecting=True, n_collectors=2)
    assert t.feed("[gaia_dr3] ok: 114 rows (33.2 s)") == "gaia_dr3: ok"
    assert t.feed("[ned] timeout: abandoned after 300 s") == "ned: timeout"
    assert t.feed("[pipeline] collect: 47.6 s") is None          # not one of the counted stages
    for s in STAGES:
        t.feed(f"[pipeline] {s}: 0.1 s")
    assert t.fraction == 1.0 and t.failed_archives == ["ned"]
    assert ProgressTracker(collecting=False).total == len(STAGES)


def test_worker_command_points_at_this_app():
    pytest.importorskip("PySide6")
    import qt_app
    program, pre = qt_app.worker_command()
    assert program == sys.executable and pre and pre[0].endswith("qt_app.py")


def test_gui_runs_pipeline_and_shows_results(tmp_path):
    pytest.importorskip("PySide6")
    raw = V2 / "rawdata"
    if not any(raw.glob("*.csv")):
        pytest.skip("no bundled raw catalogs")
    from PySide6.QtCore import QEventLoop, QTimer
    from PySide6.QtWidgets import QApplication
    import qt_app
    app = QApplication.instance() or QApplication([])
    w = qt_app.MainWindow()
    w.rb_raw.setChecked(True); w.txt_raw.setText(str(raw)); w.txt_work.setText(str(tmp_path / "run"))
    w.start_run()
    loop = QEventLoop(); w.proc.finished.connect(loop.quit); QTimer.singleShot(120000, loop.quit); loop.exec()
    app.processEvents()
    assert w.proc.exitCode() == 0, w.log.toPlainText()[-2000:]
    n = w.model.rowCount()
    assert n > 0 and w.proxy.rowCount() == n and w.tracker.fraction == 1.0
    w.cmb_class.setCurrentText("GALAXY")
    assert 0 < w.proxy.rowCount() < n
    w.table.selectRow(0); app.processEvents()
    assert "GALAXY" in w.detail.title.text() and w.detail.evidence.topLevelItemCount() > 0
    w.cmb_class.setCurrentText("ALL")
    w.table.sortByColumn(2, qt_app.Qt.DescendingOrder)            # confidence, numeric sort
    top, bottom = float(w.proxy.index(0, 2).data()), float(w.proxy.index(w.proxy.rowCount() - 1, 2).data() or 0)
    assert top >= bottom
    w.close()
