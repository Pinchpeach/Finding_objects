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
