"""Delete leftover Qt objects while the QApplication still exists.

Parentless widgets/models created in tests were otherwise destroyed by the
garbage collector after QApplication at interpreter exit, which crashed Qt
(segfault / bus error after all tests had passed)."""
import gc

import pytest


@pytest.fixture(autouse=True, scope="session")
def _qt_cleanup():
    yield
    try:
        from PySide6.QtCore import QCoreApplication, QEvent
        from PySide6.QtWidgets import QApplication
    except ImportError:
        return
    app = QApplication.instance()
    if app is None:
        return
    for w in QApplication.topLevelWidgets():
        w.close(); w.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    app.processEvents()
    gc.collect()
