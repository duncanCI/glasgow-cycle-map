import json, requests, numpy as np, geopandas as gpd, pandas as pd, collections
from scipy.spatial import cKDTree
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components, dijkstra
U="https://services-eu1.arcgis.com/zci5bUiJ8olAal7N/arcgis/rest/services/OpenStreetMap_Highways_for_Europe/FeatureServer/0/query"
G='{"xmin":-4.42,"ymin":55.78,"xmax":-4.07,"ymax":55.93,"spatialReference":{"wkid":4326}}'
r=requests.get(U,params=dict(where="oneway_bicycle IS NOT NULL OR cycleway LIKE 'opposite%'",geometry=G,geometryType="esriGeometryEnvelope",inSR=4326,
   outFields="osm_id,oneway,oneway_bicycle,cycleway",returnGeometry="false",f="json",resultRecordCount=2000),timeout=60).json()
cf=pd.DataFrame([f['attributes'] for f in r['features']]); cf=cf[cf.osm_id.notna()]; cf['osm_id']=cf.osm_id.map(lambda v:str(int(v)))
print('ways with bicycle one-way tags',len(cf)); print(cf.oneway_bicycle.value_counts(dropna=False).to_dict()); print(cf.cycleway.value_counts(dropna=False).head(6).to_dict())
contra=set(cf[(cf.oneway_bicycle.astype(str).str.lower()=='no')|(cf.cycleway.astype(str).str.startswith('opposite'))].osm_id)
N=json.load(open('data/network3.json'))
g=gpd.read_file('data/net_city.gpkg').explode(index_parts=False).reset_index(drop=True)
g=g[~((g.highway=='service') & g['name'].isna() & (g['Infrastructure type']=='Mixed Traffic Street'))].reset_index(drop=True)
wayosm=g.osm_id.astype(str).tolist(); wayhw=g.highway.tolist()
P=len(N['pu']); L=np.array(N['lens'],float)
ow=list(N['ow']); fixed=0
for k in range(P):
    if ow[k] and wayosm[N['way'][k]] in contra: ow[k]=0; fixed+=1
N['ow']=ow
quiet=[1 if (ow[k] and N['inf'][k]==0 and N['los'][k]<=1) else 0 for k in range(P)]
N['qow']=quiet
print('pieces made two-way for bikes by contraflow tags',fixed,'| one-way km',round(L[np.array(ow)!=0].sum()/1000,1),
      '| quiet one-way streets without contraflow km',round(L[np.array(quiet)==1].sum()/1000,1),'pieces',sum(quiet))
# dead ends that almost touch another street: candidate missing links (a dropped kerb or a filtered link could join them)
def dec(a):
    out=[];x=y=0
    for i in range(0,len(a),2): x+=a[i];y+=a[i+1]; out.append((x/1e5,y/1e5))
    return np.array(out)
nodes=dec(N['nodes']); n=len(nodes)
pu=np.array(N['pu']);pv=np.array(N['pv'])
deg=np.bincount(np.r_[pu,pv],minlength=n)
lat0=55.86; XY=np.c_[nodes[:,0]*np.cos(np.radians(lat0))*111320,nodes[:,1]*110540]
road=np.zeros(n,bool); tgt=np.zeros(n,bool)
for k in range(P):
    h=wayhw[N['way'][k]]
    if h in ('residential','unclassified','living_street'): road[pu[k]]=road[pv[k]]=True
    if h!='service': tgt[pu[k]]=tgt[pv[k]]=True
dead=np.where((deg==1)&road)[0]
A=coo_matrix((np.r_[L,L],(np.r_[pu,pv],np.r_[pv,pu])),shape=(n,n)).tocsr()
E=json.load(open('data/elev.json'))
import base64
z=np.frombuffer(base64.b64decode(E['b64']),dtype='<u2').reshape(E['ny'],E['nx'])/10
def elev(lon,lat):
    i=int(round((lat-E['y0'])/E['dy'])); j=int(round((lon-E['x0'])/E['dx'])); return z[min(max(i,0),E['ny']-1),min(max(j,0),E['nx']-1)]
tree=cKDTree(XY)
cands=[]
for d in dead:
    near=tree.query_ball_point(XY[d],25)
    near=[m for m in near if m!=d and tgt[m]]
    if not near: continue
    nd=dijkstra(A,indices=d,limit=400)
    best=None
    for m in near:
        if np.isfinite(nd[m]): continue          # already joined within 400 m
        gap=np.hypot(*(XY[m]-XY[d]))
        if abs(elev(*nodes[d])-elev(*nodes[m]))>2: continue
        if best is None or gap<best[1]: best=(m,gap)
    if best: cands.append((int(d),int(best[0]),round(float(best[1]),1)))
# drop pairs listed twice
seen=set(); ml=[]
for a,b,gp in cands:
    key=tuple(sorted((a,b)))
    if key in seen: continue
    seen.add(key); ml.append([a,b,gp])
print('dead-end street ends',len(dead),'| candidate missing links',len(ml),'| median gap m',np.median([x[2] for x in ml]) if ml else None)
N['ml']=[x for c in ml for x in c[:2]]
N['mlg']=[c[2] for c in ml]
json.dump(N,open('data/network4.json','w'),separators=(',',':'),allow_nan=False)
json.dump(ml[:400],open('ml_sample.json','w'))
