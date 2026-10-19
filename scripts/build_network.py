import geopandas as gpd, pandas as pd, numpy as np, json, re
from shapely.geometry import LineString, Point
from shapely.ops import transform
from scipy.spatial import cKDTree
from collections import defaultdict
import pyproj
T=pyproj.Transformer.from_crs(4326,27700,always_xy=True)
g=gpd.read_file('data/net_city.gpkg').explode(index_parts=False).reset_index(drop=True)
named=g['name'].notna()
g=g[~((g.highway=='service') & ~named & (g['Infrastructure type']=='Mixed Traffic Street'))].reset_index(drop=True)
print('ways',len(g))
LOS={'High':0,'Medium':1,'Low':2,'Should not be used (mixed traffic)':3}
INF={'Mixed Traffic Street':0,'Painted Cycle Lane':1,'Segregated Track (narrow)':2,'Segregated Track (wide)':3,'Off Road Cycleway':4,'Shared Footway':5}
MAJOR={'primary','primary_link','secondary','secondary_link','tertiary','tertiary_link','trunk','trunk_link','motorway','motorway_link'}
def num(v):
    try: return float(re.match(r'(\d+)',str(v)).group(1))
    except: return None
rows=[]
for i,r in g.iterrows():
    los=LOS.get(r['Level of Service'],-1)
    spd=num(r['maxspeed']) or r['Speed limit']
    spd=None if pd.isna(spd) else float(spd)
    rated=los>=0
    if los<0:
        los=1 if (r.highway not in MAJOR and (spd is None or spd<=30)) else 2
    lanes=num(r['lanes']) or 0
    hard=(los==3) or r.highway in ('trunk','trunk_link','motorway','motorway_link') or (r.highway in ('primary','secondary') and str(r['oneway'])=='yes' and lanes>=2)
    rows.append(dict(los=los,rated=rated,inf=INF[r['Infrastructure type']],spd=spd,vol=r['Traffic volume category'],hard=hard,name=r['name'] if isinstance(r['name'],str) else (r['ref'] if isinstance(r['ref'],str) else ''),hw=r.highway,osm=r.osm_id,cyc=r['cycleway']))
A=pd.DataFrame(rows)
# noding at shared vertices
key=lambda c:(round(c[0],7),round(c[1],7))
cnt=defaultdict(int)
for geom in g.geometry:
    for k in set(key(c) for c in geom.coords): cnt[k]+=1
nid={}; nodes=[]
def node(k):
    if k not in nid: nid[k]=len(nodes); nodes.append(k)
    return nid[k]
P=[]  # pieces
for i,geom in enumerate(g.geometry):
    cs=list(geom.coords); start=0
    for j in range(1,len(cs)):
        k=key(cs[j])
        if j==len(cs)-1 or cnt[k]>1:
            seg=cs[start:j+1]
            if len(seg)>=2: P.append((i,node(key(seg[0])),node(key(seg[-1])),seg))
            start=j
print('pieces',len(P),'nodes',len(nodes))
nodes_xy=np.array([T.transform(*n) for n in nodes])
# node flags
hardnode=np.zeros(len(nodes),bool)
for (i,u,v,seg) in P:
    if A.hard[i]: hardnode[u]=hardnode[v]=True
sig=gpd.read_file('data/signal_crossings.geojson').to_crs(27700)
sigpts=np.vstack([np.array(geom.coords) for geom in sig.geometry])
dsig,_=cKDTree(sigpts).query(nodes_xy,distance_upper_bound=30)
signal=np.isfinite(dsig)
print('hard nodes',hardnode.sum(),'hard&signal',(hardnode&signal).sum())
# City Network
cn=gpd.read_file('data/city_network.geojson').explode(index_parts=False).reset_index(drop=True)
STAGE={'Constructed':0,'Construction':1,'Design':2,'Proposed Cycle Street':3,'Indicative Network':4,'Deferred':5}
cn['st']=cn.STAGE.map(STAGE)
cn27=cn.to_crs(27700)
tree=cKDTree(nodes_xy)
cnEdges=[]
for ci,geom in enumerate(cn27.geometry):
    L=geom.length; ds=np.arange(0,L+0.1,20.0)
    if ds[-1]<L: ds=np.append(ds,L)
    pts=np.array([geom.interpolate(d).coords[0] for d in ds])
    dd,ii=tree.query(pts,distance_upper_bound=35)
    seq=[int(n) for d,n in zip(dd,ii) if np.isfinite(d)]
    seq=[n for k,n in enumerate(seq) if k==0 or n!=seq[k-1]]
    for a,b in zip(seq,seq[1:]): cnEdges.append((a,b,ci))
print('cn edges',len(cnEdges))
# piece -> cn match (mostly within 15m)
pg=gpd.GeoDataFrame({'pi':range(len(P))},geometry=[LineString(p[3]) for p in P],crs=4326).to_crs(27700)
buf=cn27.copy(); buf['geometry']=buf.buffer(15)
j=gpd.sjoin(pg,buf[['geometry','st']],predicate='intersects')
pcn=np.full(len(P),-1)
best={}
for pi,ci in zip(j.pi.values,j.index_right.values):
    pgeom=pg.geometry[pi]; f=pgeom.intersection(buf.geometry[ci]).length/max(pgeom.length,0.1)
    cl=cn27.geometry[ci]; a0,a1=np.array(pgeom.coords[0]),np.array(pgeom.coords[-1])
    d0,d1=cl.project(Point(a0)),cl.project(Point(a1))
    if abs(d1-d0)<1: c1=np.array(cl.interpolate(max(d0-5,0)).coords[0]); c2=np.array(cl.interpolate(d0+5).coords[0])
    else: c1=np.array(cl.interpolate(d0).coords[0]); c2=np.array(cl.interpolate(d1).coords[0])
    va=a1-a0; vb=c2-c1; cos=abs(va@vb)/(np.linalg.norm(va)*np.linalg.norm(vb)+1e-9)
    if f>=0.6 and cos>0.8 and (pi not in best or f>best[pi][0]): best[pi]=(f,ci)
for pi,(f,ci) in best.items(): pcn[pi]=ci
print('pieces on CN',(pcn>=0).sum())
# encode geometry (simplified)
def enc(coords):
    out=[];px=py=0
    for x,y in coords:
        X=int(round(x*1e5));Y=int(round(y*1e5)); out+= [X-px,Y-py]; px,py=X,Y
    return out
def simp(seg):
    return list(LineString(seg).simplify(0.000018).coords)
names=sorted(set(A.name)); nidx={n:i for i,n in enumerate(names)}
VOL={'0 to 999':0,'1000 to 1999':1,'2000 to 3999':2,'4000+':3}
out=dict(nodes=enc(nodes),hard=[int(h) for h in hardnode],signal=[int(s) for s in signal],names=names,
  pu=[],pv=[],los=[],rated=[],inf=[],spd=[],vol=[],nm=[],cn=[],way=[],geom=[],lens=[])
for k,(i,u,v,seg) in enumerate(P):
    a=A.iloc[i]
    out['pu'].append(u);out['pv'].append(v);out['los'].append(int(a.los));out['rated'].append(int(a.rated));out['inf'].append(int(a.inf))
    out['spd'].append(0 if pd.isna(a.spd) else int(a.spd));out['vol'].append(VOL.get(a.vol,-1));out['nm'].append(nidx[a['name']]);out['cn'].append(int(pcn[k]));out['way'].append(i)
    s=simp(seg) if len(seg)>2 else seg
    out['geom'].append(enc(s)); out['lens'].append(int(round(pg.geometry[k].length)))
out['phard']=[int(A.hard[p[0]]) for p in P]
out['cnEdges']=[x for e in cnEdges for x in e]
def clean(v): return None if (isinstance(v,float) and np.isnan(v)) or v in ('n/a','NaN') else v
out['cnInfo']=[dict(r=r.ROUTE_NAME,s=r.ROUTE_SECTION,st=int(r.st),tr=clean(r.DELIVERY_TRANCHE),iss=(r.DELIVERABILITY_ISSUES.strip(' ,') if isinstance(r.DELIVERABILITY_ISSUES,str) else None),km=round(cn27.geometry[i].length/1000,2)) for i,r in cn.iterrows()]
out['cnGeom']=[enc([(round(x,6),round(y,6)) for x,y in geom.coords]) for geom in cn.geometry]
w=gpd.read_file('data/water.geojson')
w=w[w.geometry.notna()].to_crs(27700).simplify(4).to_crs(4326)
polys=[]
for geom in w.geometry:
    for p in getattr(geom,'geoms',[geom]):
        if p.geom_type=='Polygon': polys.append(enc(p.exterior.coords))
out['water']=polys
bnd=gpd.read_file('data/boundary.geojson').to_crs(27700).simplify(10).to_crs(4326)
out['boundary']=[enc(p.exterior.coords) for geom in bnd.geometry for p in getattr(geom,'geoms',[geom])]
DEST=[('George Square',55.8612,-4.2502),('University of Glasgow',55.8721,-4.2882),('Queen Elizabeth University Hospital',55.8622,-4.3392),('Partick station',55.8698,-4.3089),('Glasgow Green',55.8516,-4.2370),('Queens Park',55.8346,-4.2683)]
out['dest']=[]
for nm,la,lo in DEST:
    x,y=T.transform(lo,la); ii=tree.query_ball_point((x,y),250)
    out['dest'].append(dict(n=nm,lat=la,lon=lo,nodes=[int(i) for i in ii]))
json.dump(out,open('data/network.json','w'),separators=(',',':'))
import os; print('json MB',os.path.getsize('data/network.json')/1e6)
# stats for copy
pg['los']=out['los'];pg['inf']=out['inf'];pg['rated']=out['rated'];pg['L']=pg.length/1000
print(pg.groupby(['inf','los']).L.sum().round(1))
pg['cn']=out['cn']; print('matched km',pg[pg.cn>=0].L.sum().round(1))
tot=pg.L.sum(); print('total km',round(tot,1))
