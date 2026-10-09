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
    w.rb_raw.setChecked(True); w.chk_area.setChecked(False)
    w.txt_raw.setText(str(raw)); w.txt_work.setText(str(tmp_path / "run"))
    assert "--ra" not in w.pipeline_args()
    w.start_run()
    loop = QEventLoop(); w.proc.finished.connect(loop.quit); QTimer.singleShot(120000, loop.quit); loop.exec()
    app.processEvents()
    assert w.proc.exitCode() == 0, w.log.toPlainText()[-2000:]
    n = w.model.rowCount()
    names = w.model.frame().designation
    assert not names.str.match(r"OBJ\d+$").any() and names.is_unique      # real catalogue names only
    assert w.model.headerData(0, qt_app.Qt.Horizontal) == "Name"
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


def test_parse_coordinates_and_radius_units():
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication
    import qt_app
    assert qt_app.parse_coordinates("188.4155 +9.1751") == (188.4155, 9.1751)
    ra, dec = qt_app.parse_coordinates("12:33:39.72 +09:10:30.4")
    assert abs(ra - 188.4155) < 1e-4 and abs(dec - 9.17511) < 1e-4
    ra2, dec2 = qt_app.parse_coordinates("12h33m39.72s +9d10m30.4s")
    assert abs(ra2 - ra) < 1e-9 and abs(dec2 - dec) < 1e-9
    assert qt_app.parse_coordinates("NGC 4522") is None and qt_app.parse_coordinates("400 0") is None
    app = QApplication.instance() or QApplication([])
    w = qt_app.MainWindow()
    w.rb_sky.setChecked(True)
    w.cmb_rad_unit.setCurrentText("arcmin"); w.sp_rad.setValue(0.5)
    w.cmb_rad_unit.setCurrentText("arcsec")
    assert abs(w.sp_rad.value() - 30.0) < 1e-6 and abs(w.radius_arcmin() - 0.5) < 1e-9
    w.txt_name.setText("188.4155 9.1751"); w._resolve_name()
    args = w.pipeline_args()
    assert args[args.index("--ra") + 1].startswith("188.4155") and float(args[args.index("--radius") + 1]) == 0.5
    w.close()


def test_designations_priority_and_area_cut():
    import importlib.util
    import pandas as pd
    spec = importlib.util.spec_from_file_location("v2_designations", V2 / "designations.py")
    d = importlib.util.module_from_spec(spec); spec.loader.exec_module(d)
    assoc = pd.DataFrame({
        "object_id": ["OBJ1", "OBJ1", "OBJ1", "OBJ2", "OBJ2", "OBJ3"],
        "catalog": ["Pan-STARRS1 DR2 MeanObject", "SIMBAD", "Gaia DR3", "Gaia DR3", "AllWISE", "Mystery Cat"],
        "catalog_object_id": ["1", "NGC  4522", "7", "8", "J1", "42"],
        "object_name": ["PSO J1", "NAME  Some  Galaxy", "Gaia DR3 7", "Gaia DR3 8", "AllWISE J1", None],
        "association_confidence": [0.9, 0.8, 0.9, 0.9, 0.9, 0.5]})
    cls = pd.DataFrame({"object_id": ["OBJ1", "OBJ2", "OBJ3"], "ra": [10.0, 10.0, 10.1], "dec": [0.0, 1 / 60, 0.0]})
    out = d.annotate(cls, assoc).set_index("object_id")
    assert out.loc["OBJ1", "designation"] == "Some Galaxy" and out.loc["OBJ1", "designation_catalog"] == "SIMBAD"
    assert out.loc["OBJ2", "designation"] == "Gaia DR3 8"
    assert out.loc["OBJ3", "designation"] == "Mystery Cat 42"
    assert out.loc["OBJ1", "catalog_designations"].split("; ")[0] == "Some Galaxy"
    cut = d.annotate(cls, assoc, center=(10.0, 0.0), radius_arcmin=2.0)
    assert list(cut.object_id) == ["OBJ1", "OBJ2"] and abs(cut.separation_arcmin.iloc[1] - 1.0) < 1e-6
