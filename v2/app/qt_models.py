"""Qt models for the Finding Objects desktop app: a pandas-backed table model
and a sort/filter proxy (class, status and free-text filters)."""
from __future__ import annotations
import math
import pandas as pd
from PySide6.QtCore import QAbstractTableModel, QModelIndex, QSortFilterProxyModel, Qt
from PySide6.QtGui import QColor

CLASS_COLORS = {"STAR": "#d9822b", "GALAXY": "#2b6cb0", "QSO": "#7b3fb5", "UNKNOWN": "#8a8f98"}
TABLE_COLUMNS = ["object_id", "primary_class", "primary_confidence", "classification_status",
                 "p_star", "p_galaxy", "p_qso", "ra", "dec", "catalogs"]
HEADERS = {"object_id": "Object", "primary_class": "Class", "primary_confidence": "Confidence",
           "classification_status": "Status", "p_star": "P(star)", "p_galaxy": "P(galaxy)",
           "p_qso": "P(QSO)", "ra": "RA", "dec": "Dec", "catalogs": "Catalogs"}
SORT_ROLE = Qt.UserRole + 1


def class_color(name: str) -> QColor:
    return QColor(CLASS_COLORS.get(str(name), CLASS_COLORS["UNKNOWN"]))


class DataFrameModel(QAbstractTableModel):
    """Read-only view of selected columns of a results DataFrame (rows keep
    their DataFrame position so other widgets can refer to them)."""

    def __init__(self, df: pd.DataFrame | None = None, parent=None):
        super().__init__(parent)
        self._df = pd.DataFrame()
        self._cols: list[str] = []
        if df is not None:
            self.set_frame(df)

    def set_frame(self, df: pd.DataFrame) -> None:
        self.beginResetModel()
        self._df = df.reset_index(drop=True)
        self._cols = [c for c in TABLE_COLUMNS if c in self._df.columns]
        self.endResetModel()

    def frame(self) -> pd.DataFrame:
        return self._df

    def column_name(self, col: int) -> str:
        return self._cols[col]

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self._df)

    def columnCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self._cols)

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role != Qt.DisplayRole:
            return None
        if orientation == Qt.Horizontal:
            return HEADERS.get(self._cols[section], self._cols[section])
        return str(section + 1)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        col = self._cols[index.column()]
        value = self._df.iat[index.row(), self._df.columns.get_loc(col)]
        if hasattr(value, "item"):          # numpy scalar -> Python (Qt cannot take numpy types)
            value = value.item()
        if role == Qt.DisplayRole:
            if isinstance(value, float):
                if math.isnan(value):
                    return ""
                return f"{value:.5f}" if col in ("ra", "dec") else f"{value:.3f}"
            return "" if value is None else str(value)
        if role == SORT_ROLE:
            if isinstance(value, float) and math.isnan(value):
                return float("-inf")
            return value
        if role == Qt.ForegroundRole and col == "primary_class":
            return class_color(value)
        if role == Qt.TextAlignmentRole and isinstance(value, float):
            return int(Qt.AlignRight | Qt.AlignVCenter)
        return None


class ResultsFilter(QSortFilterProxyModel):
    """Filters rows by class, status and a case-insensitive text match on the
    object id and catalogue list."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSortRole(SORT_ROLE)
        self._cls = "ALL"
        self._status = "ALL"
        self._text = ""
        self._a_cls = self._a_status = self._a_text = None

    def set_class(self, cls: str):
        self._cls = cls; self.invalidateFilter()

    def set_status(self, status: str):
        self._status = status; self.invalidateFilter()

    def set_text(self, text: str):
        self._text = text.strip().lower(); self.invalidateFilter()

    def setSourceModel(self, model):
        super().setSourceModel(model)
        model.modelReset.connect(self._cache)
        self._cache()

    def _cache(self):
        # Column arrays once per result set: filtering thousands of rows must
        # not go through per-row pandas indexing.
        df = self.sourceModel().frame()
        col = lambda c: df[c].astype(str).to_numpy() if c in df else None
        self._a_cls, self._a_status = col("primary_class"), col("classification_status")
        ids, cats = col("object_id"), col("catalogs")
        self._a_text = None if ids is None else [f"{i} {c}".lower() for i, c in zip(ids, cats if cats is not None else [""] * len(ids))]

    def filterAcceptsRow(self, row, parent):
        if self._cls != "ALL" and self._a_cls is not None and self._a_cls[row] != self._cls:
            return False
        if self._status != "ALL" and self._a_status is not None and self._a_status[row] != self._status:
            return False
        if self._text and self._a_text is not None and self._text not in self._a_text[row]:
            return False
        return True

    def lessThan(self, left, right):
        a, b = left.data(SORT_ROLE), right.data(SORT_ROLE)
        try:
            return bool(a < b)
        except TypeError:
            return str(a) < str(b)
