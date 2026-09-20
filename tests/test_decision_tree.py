from finding_objects.decision_tree import identity_tree
def test_star_branch():
 r=identity_tree({"spectrum_verified":True,"parallax_snr":10,"proper_motion_snr":7,"stellar_absorption_pattern":True})
 assert r["identity"]=="STAR"
def test_qso_branch():
 r=identity_tree({"spectrum_verified":True,"redshift":1.2,"broad_permitted_lines":True,"wise_agn_colors":True})
 assert r["identity"]=="QSO_AGN"
def test_galaxy_branch():
 r=identity_tree({"spectrum_verified":True,"redshift":.05,"extended_morphology":True,"narrow_nebular_lines":True})
 assert r["identity"]=="GALAXY"
def test_unknown_when_association_bad():
 r=identity_tree({"counterpart_status":"likely_not_same_object"})
 assert r["identity"]=="UNKNOWN"
