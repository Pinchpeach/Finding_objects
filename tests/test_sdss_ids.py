from finding_objects.sdss import read_skyserver_csv


def test_large_objid_is_preserved_exactly():
    objid = "1237651753997239000"
    df = read_skyserver_csv("#Table1\nobjid,ra,u\n" + objid + ",150.1,23.5\n")
    assert df.loc[0, "objid"] == objid
    assert isinstance(df.loc[0, "objid"], str)
