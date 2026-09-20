"""Reference-trained object classifier for Method 1 candidates.
Never promotes predictions into Method 2 reference labels.
"""
import numpy as np, pandas as pd
FEATURES=["Halpha","Hbeta","OIII_5007","OII_3727","NII_6583","SII_6716","SII_6731","CaII_K","CaII_H","MgII_2796","MgII_2803","NaI_D","FeII_2600","CIV_1549","Lyalpha"]
def build_line_features(measured):
 d=measured.copy(); d["det"]=(d.detection_status=="detected").astype(float)
 p=d.pivot_table(index="objid",columns="line",values="det",aggfunc="max",fill_value=0)
 return p.reindex(columns=FEATURES,fill_value=0)
def fit_reference_centroids(features,labels):
 x=features.join(labels.set_index("objid")[["class"]],how="inner"); out={}
 for k,g in x.groupby("class"):
  a=g[FEATURES].to_numpy(float); out[k]={"mean":a.mean(0),"scale":np.maximum(a.std(0),.25),"n":len(g)}
 return out
def predict(features,model):
 rows=[]
 for oid,r in features.iterrows():
  scores={k:-.5*np.mean(((r[FEATURES].to_numpy(float)-m["mean"])/m["scale"])**2) for k,m in model.items()}
  ks=list(scores); z=np.array([scores[k] for k in ks]); z=np.exp(z-z.max()); p=z/z.sum(); order=np.argsort(-p)
  rows.append({"objid":oid,"predicted_class":ks[order[0]],"class_probability":float(p[order[0]]),"second_class":ks[order[1]],"second_probability":float(p[order[1]]),"classification_method":"reference_line_centroid_v1","reference_only":True})
 return pd.DataFrame(rows)
