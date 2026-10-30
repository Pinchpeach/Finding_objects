"""Probe Data Lab ls_dr10.tractor columns needed for 2.44.0 (dchisq, shape_r_ivar, fiberflux, fracflux)."""
import pyvo

s = pyvo.dal.TAPService("https://datalab.noirlab.edu/tap")
cols = s.search(
    "SELECT column_name, datatype, description FROM TAP_SCHEMA.columns WHERE table_name = 'ls_dr10.tractor' "
    "AND (column_name LIKE '%dchisq%' OR column_name LIKE '%shape_r%' OR column_name LIKE 'fiberflux%' "
    "OR column_name LIKE 'fracflux%' OR column_name LIKE 'fracin%' OR column_name LIKE 'fitbits%')"
).to_table()
for r in cols:
    print(r["column_name"], r["datatype"], str(r["description"])[:90])
t = s.search("SELECT TOP 3 ls_id, type, dchisq_1, dchisq_2, dchisq_3, dchisq_4, dchisq_5 FROM ls_dr10.tractor "
             "WHERE ra BETWEEN 150 AND 150.01 AND dec BETWEEN 2 AND 2.01").to_table()
print(t)

# Training set of LS-GBM (desi_dr1.photometry, LS DR9): are dchisq / shape_r_ivar there,
# and does ls_dr9.tractor answer by ls_id derived from TARGETID?
for table in ("desi_dr1.photometry", "ls_dr9.tractor"):
    c = s.search(
        f"SELECT column_name FROM TAP_SCHEMA.columns WHERE table_name = '{table}' "
        "AND (column_name LIKE '%dchisq%' OR column_name LIKE '%shape_r%' OR column_name LIKE 'fracflux%' "
        "OR column_name LIKE 'fiberflux%' OR column_name = 'ls_id' OR column_name LIKE 'brick%' OR column_name = 'objid')"
    ).to_table()
    print(table, [str(x) for x in c["column_name"]])
tid = 39627808913231254
objid, brickid, release = tid & (2**22 - 1), (tid >> 22) & (2**22 - 1), (tid >> 44) & (2**16 - 1)
lsid = (release << 40) | (brickid << 16) | objid
print("targetid", tid, "release", release, "brickid", brickid, "objid", objid, "ls_id", lsid)
print(s.search(f"SELECT ls_id, type, ra, dec, dchisq_1, dchisq_2, shape_r, shape_r_ivar FROM ls_dr9.tractor WHERE ls_id = {lsid}").to_table())
