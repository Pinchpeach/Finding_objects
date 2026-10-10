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
    proc = w.proc
    loop = QEventLoop(); proc.finished.connect(loop.quit); QTimer.singleShot(120000, loop.quit); loop.exec()
    app.processEvents()
    assert w.proc is None and w.statusBar().currentMessage().startswith("Done"), w.log.toPlainText()[-2000:]
    n = w.model.rowCount()
    names = w.model.frame().designation
    assert not names.str.match(r"OBJ\d+$").any() and names.is_unique      # real catalogue names only
    assert w.model.headerData(0, qt_app.Qt.Horizontal) == "Name"
    df = w.model.frame()
    top = int(df.parent_object_id.isna().sum())
    assert n > 0 and top < n and w.proxy.rowCount() == top and w.tracker.fraction == 1.0   # galaxy parts hidden
    w.chk_parts.setChecked(True); assert w.proxy.rowCount() == n
    w.chk_parts.setChecked(False)
    host = df[df.n_components.gt(0)].iloc[0]
    assert host.designation == "NGC 4522" and isinstance(host.subclass, str) and "galaxy" in host.subclass.lower()
    w.cmb_class.setCurrentText("GALAXY")
    assert 0 < w.proxy.rowCount() < n
    w.table.selectRow(0); app.processEvents()
    assert "GALAXY" in w.detail.title.text() and w.detail.evidence.topLevelItemCount() > 0
    w.cmb_class.setCurrentText("ALL")
    ci = [w.model.column_name(i) for i in range(w.model.columnCount())].index("primary_confidence")
    w.table.sortByColumn(ci, qt_app.Qt.DescendingOrder)            # confidence, numeric sort
    top, bottom = float(w.proxy.index(0, ci).data()), float(w.proxy.index(w.proxy.rowCount() - 1, ci).data() or 0)
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


def test_sky_map_zoom_pan_and_icons():
    pytest.importorskip("PySide6")
    import pandas as pd
    from PySide6.QtCore import QPointF
    from PySide6.QtWidgets import QApplication
    import qt_widgets, qt_icons
    app = QApplication.instance() or QApplication([])
    df = pd.DataFrame({"ra": [10.0, 10.01, 9.99], "dec": [0.0, 0.01, -0.01], "designation": ["A", "B", "C"],
                       "primary_class": ["STAR", "GALAXY", "QSO"],
                       "subclass_code": ["STAR:K:V", "GALAXY:STAR_FORMING:?", "QSO:RADIO_LOUD:HIGH_Z:X"]})
    v = qt_widgets.SkyView(); v.resize(500, 500); v.show(); app.processEvents()
    m = v.map
    m.set_frame(df); app.processEvents()
    sx0, sy0 = m._to_screen(m._x[1], m._y[1])
    m.zoom_by(4.0, QPointF(sx0, sy0))                     # zoom about object B: it stays under the cursor
    sx1, sy1 = m._to_screen(m._x[1], m._y[1])
    assert m.zoom == 4.0 and abs(sx1 - sx0) < 1e-6 and abs(sy1 - sy0) < 1e-6
    ra, dec = m._to_sky(sx1, sy1)
    assert abs(ra - 10.01) < 1e-6 and abs(dec - 0.01) < 1e-6
    m.reset_view(); assert m.zoom == 1.0
    kinds = [qt_icons.kind_of(r) for r in df.to_dict("records")]
    assert kinds[0]["letter"] == "K" and kinds[1]["activity"] == "STAR_FORMING" and kinds[2]["radio"] == "RADIO_LOUD" and kinds[2]["xray"]
    img = v.grab().toImage(); assert not img.isNull()
    # A parentless widget must be deleted while the QApplication exists;
    # left to the garbage collector at interpreter exit it crashed Qt.
    v.close(); v.deleteLater(); app.processEvents()


def test_literature_row_links_papers_to_ads():
    pytest.importorskip("PySide6")
    from qt_widgets import _paper_html
    row = {"paper_class": "Galaxy in a group", "paper_source": "SIMBAD NGC  4522 (otype GiG, 250 papers)",
           "paper_refs": "2004AJ....127.3361K (2004) Ram pressure <stripping>"}
    out = _paper_html(row)
    assert "<b>Galaxy in a group</b>" in out and "&lt;stripping&gt;" in out
    assert "href='https://ui.adsabs.harvard.edu/abs/2004AJ....127.3361K'" in out
    assert _paper_html({"paper_class": float("nan")}) == "–"


def test_filter_proxy_follows_a_larger_new_frame():
    pytest.importorskip("PySide6")
    import pandas as pd
    from PySide6.QtWidgets import QApplication
    from qt_models import DataFrameModel, ResultsFilter
    app = QApplication.instance() or QApplication([])
    model, proxy = DataFrameModel(), ResultsFilter()
    proxy.setSourceModel(model)
    frame = lambda n: pd.DataFrame({"object_id": [f"O{i}" for i in range(n)], "primary_class": ["STAR"] * n,
                                    "classification_status": ["CLASSIFIED"] * n, "parent_object_id": [None] * n})
    model.set_frame(frame(3)); assert proxy.rowCount() == 3
    model.set_frame(frame(10)); assert proxy.rowCount() == 10      # used to index the 3-row cache
    proxy.set_class("GALAXY"); assert proxy.rowCount() == 0


def test_pipeline_on_an_empty_field_returns_no_objects(tmp_path):
    import importlib.util, sys
    sys.path.insert(0, str(V2))
    spec = importlib.util.spec_from_file_location("v2_pipeline_empty", V2 / "pipeline.py")
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    (tmp_path / "raw").mkdir()
    out = mod.run(tmp_path / "work", raw_dir=tmp_path / "raw")
    assert len(out) == 0 and (tmp_path / "work" / "classified_objects.csv").exists()
