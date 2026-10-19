"""Mark street junctions that sit on bridges or in tunnels, so planned routes and community lines
are never joined to a road passing over or under them, and re-snap the planned City Network links."""
import json, requests, numpy as np, geopandas as gpd, pandas as pd
from scipy.spatial import cKDTree
import pyproj
U="https://services-eu1.arcgis.com/zci5bUiJ8olAal7N/arcgis/rest/services/OpenStreetMap_Highways_for_Europe/FeatureServer/0/query"
G='{"xmin":-4.42,"ymin":55.78,"xmax":-4.07,"ymax":55.93,"spatialReference":{"wkid":4326}}'
rows=[]; off=0
while True:
    r=requests.get(U,params=dict(where="bridge IS NOT NULL OR tunnel IS NOT NULL OR (layer IS NOT NULL AND layer <> '0')",geometry=G,geometryType="esriGeometryEnvelope",inSR=4326,
       outFields="osm_id,bridge,tunnel,layer",returnGeometry="false",f="json",resultOffset=off,resultRecordCount=2000,orderByFields="OBJECTID"),timeout=60).json()
    fs=r.get('features',[]); rows+=[f['attributes'] for f in fs]
    if len(fs)<2000: break
    off+=2000
gs=pd.DataFrame(rows); gs=gs[gs.osm_id.notna()]; gs['osm_id']=gs.osm_id.map(lambda v:str(int(v)))
def off_grade(r):
    b=str(r.bridge).lower(); t=str(r.tunnel).lower(); l=str(r.layer)
    return (b not in ('none','no','nan')) or (t not in ('none','no','nan')) or (l not in ('none','nan','0'))
gs=gs[gs.apply(off_grade,axis=1)]
ids=set(gs.osm_id); print('ways on bridges, in tunnels or on another layer',len(ids))
N=json.load(open('data/network4.json'))
g=gpd.read_file('data/net_city.gpkg').explode(index_parts=False).reset_index(drop=True)
g=g[~((g.highway=='service') & g['name'].isna() & (g['Infrastructure type']=='Mixed Traffic Street'))].reset_index(drop=True)
wayosm=g.osm_id.astype(str).tolist()
P=len(N['pu']); n=len(N['hard'])
pg=[1 if wayosm[N['way'][k]] in ids else 0 for k in range(P)]
inc=np.zeros(n,int); incg=np.zeros(n,int)
for k in range(P):
    for v in (N['pu'][k],N['pv'][k]): inc[v]+=1; incg[v]+=pg[k]
gsn=((inc>0)&(incg==inc)).astype(int)
print('pieces off grade',sum(pg),'| junctions only on bridges or in tunnels',int(gsn.sum()))
N['gs']=[int(x) for x in gsn]
N['gst']=[int(x) for x in (incg>0)]  # junctions touching any bridge or tunnel piece
# re-snap the planned City Network to at-grade junctions only
def dec(a):
    out=[];x=y=0
    for i in range(0,len(a),2): x+=a[i];y+=a[i+1]; out.append((x/1e5,y/1e5))
    return np.array(out)
nodes=dec(N['nodes']); T=pyproj.Transformer.from_crs(4326,27700,always_xy=True)
xy=np.c_[T.transform(nodes[:,0],nodes[:,1])]
ok=np.where(gsn==0)[0]; tree=cKDTree(xy[ok])
cn=gpd.read_file('data/city_network.geojson').explode(index_parts=False).reset_index(drop=True).to_crs(27700)
old=len(N['cnEdges'])//3; E=[]
for ci,geom in enumerate(cn.geometry):
    L=geom.length; ds=np.arange(0,L+0.1,20.0)
    if ds[-1]<L: ds=np.append(ds,L)
    pts=np.array([geom.interpolate(d).coords[0] for d in ds])
    dd,ii=tree.query(pts,distance_upper_bound=35)
    seq=[int(ok[i]) for d,i in zip(dd,ii) if np.isfinite(d)]
    seq=[v for j,v in enumerate(seq) if j==0 or v!=seq[j-1]]
    E+=[x for a,b in zip(seq,seq[1:]) for x in (a,b,ci)]
N['cnEdges']=E
print('planned links before',old,'after',len(E)//3)
json.dump(N,open('data/network5.json','w'),separators=(',',':'),allow_nan=False)
# the Kelvinbridge case
kb=(-4.2795,55.8752); kx,ky=T.transform(*kb)
near=np.where(np.hypot(xy[:,0]-kx,xy[:,1]-ky)<120)[0]
print('junctions within 120 m of Kelvinbridge',len(near),'of which off grade',int(gsn[near].sum()))
