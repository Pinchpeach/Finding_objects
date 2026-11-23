import sys, time, pandas as pd
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[2] / "Get_data"))
from _catalog_utils import _sdss
S = _sdss(); out = sys.argv[1]; parts = []
for lo in range(0, 360, 10):
    q = (f"SELECT ra, dec, class, subclass, z FROM SpecObj WHERE zWarning=0 AND class IN ('STAR','QSO') "
         f"AND ra >= {lo} AND ra < {lo+10}")
    for attempt in range(4):
        try:
            t = S.query_sql(q, data_release=18, timeout=600); break
        except Exception as e:
            print(lo, "retry", type(e).__name__, str(e)[:100], flush=True); time.sleep(10)
    else:
        raise SystemExit(f"chunk {lo} failed")
    d = t.to_pandas(); parts.append(d); print(lo, len(d), flush=True)
pd.concat(parts, ignore_index=True).to_csv(out, index=False)
print("done", sum(map(len, parts)))
