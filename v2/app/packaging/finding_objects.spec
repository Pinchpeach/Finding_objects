# PyInstaller spec for the Finding Objects desktop app (one-folder build).
#
#   pyinstaller v2/app/packaging/finding_objects.spec --noconfirm
#
# The pipeline loads its stages by file path (importlib), so the v2 source tree
# is bundled as data under <bundle>/v2 (app_paths.v2_root() finds it via
# sys._MEIPASS), and every third-party package those files import is listed
# as a hidden import: PyInstaller's analysis only follows the entry script.
# Runtime packages: pandas, numpy, astropy, astroquery, pyvo, requests,
# PySide6.  scikit-learn / joblib are used only by training and validation
# scripts and are excluded.
import os
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

SPEC_DIR = Path(SPECPATH)
V2 = SPEC_DIR.parents[1]
ENTRY = str(V2 / "app" / "qt_app.py")

# v2 tree as data: only what the app and pipeline read at run time.
INCLUDE_DIRS = ("app", "Get_data", "Preprocess", "Classifier")
INCLUDE_FILES = ("pipeline.py", "designations.py", "host_groups.py", "VERSION", "CHANGELOG.md")
SKIP_PARTS = {"__pycache__", "tests", "packaging"}
datas = []
for d in INCLUDE_DIRS:
    for path in (V2 / d).rglob("*"):
        if path.is_file() and not (SKIP_PARTS & set(path.relative_to(V2).parts)):
            datas.append((str(path), str(Path("v2") / path.relative_to(V2).parent)))
for f in INCLUDE_FILES:
    datas.append((str(V2 / f), "v2"))

datas += collect_data_files("astroquery")
datas += collect_data_files("pyvo")
datas += collect_data_files("astropy", includes=["**/*.cfg", "**/*.dat", "**/*.txt", "**/*.json",
                                                  "**/*.csv", "**/*.ecsv", "**/data/**"])

hiddenimports = (collect_submodules("astroquery", filter=lambda n: ".tests" not in n)
                 + collect_submodules("pyvo", filter=lambda n: ".tests" not in n)
                 + ["astropy.coordinates", "astropy.units", "astropy.table", "astropy.io.votable",
                    "astropy.io.fits", "astropy.time", "pandas", "numpy", "requests",
                    "html5lib", "bs4", "keyring", "keyring.backends"])

a = Analysis(
    [ENTRY],
    pathex=[str(V2 / "app"), str(V2)],
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=["sklearn", "joblib", "tkinter", "matplotlib", "pytest", "IPython"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="FindingObjects",
    console=False,          # GUI; the --pipeline worker restores stdout itself (qt_app._worker_stdio)
    disable_windowed_traceback=False,
)
coll = COLLECT(exe, a.binaries, a.datas, name="FindingObjects")
