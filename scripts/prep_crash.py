"""Bike-involved road collisions (DfT STATS19, Glasgow City Council open data) matched to the street network,
with hotspots where several cluster together."""
import json, numpy as np, pandas as pd, pyproj, collections
from scipy.spatial import cKDTree
from shapely.geometry import LineString, Point
c=pd.read_pickle('data/bike_crashes.pkl')
N=json.load(open('data/network5.json'))
T=pyproj.Transformer.from_crs(27700,4326,always_xy=True); T2=pyproj.Transformer.from_crs(4326,27700,always_xy=True)
lon,lat=T.transform(c.E.values,c.N.values); c['lon']=lon; c['lat']=lat
SEV={'Slight':1,'Serious':2,'Fatal':3}; W={1:1,2:3,3:6}
c['s']=c.sev.map(SEV)
def dec(a):
    out=[];x=y=0
    for i in range(0,len(a),2): x+=a[i];y+=a[i+1]; out.append((x/1e5,y/1e5))
    return out
P=len(N['pu'])
lines=[]; 
for g in N['geom']:
    pts=np.array(dec(g)); x,y=T2.transform(pts[:,0],pts[:,1]); lines.append(LineString(np.c_[x,y]))
mids=np.array([l.interpolate(0.5,normalized=True).coords[0] for l in lines]); tree=cKDTree(mids)
road=np.array([N['inf'][k] in (0,1) for k in range(P)])
assign=[]
for e,n in zip(c.E.values,c.N.values):
    pt=Point(e,n); cand=tree.query_ball_point((e,n),400)
    best=None
    for k in cand:
        d=lines[k].distance(pt)
        if d>25: continue
        score=d-(5 if road[k] else 0)   # prefer the carriageway when a track runs alongside
        if best is None or score<best[0]: best=(score,k)
    assign.append(best[1] if best else -1)
c['piece']=assign
print('collisions',len(c),'matched to a street',int((c.piece>=0).sum()))
agg=collections.defaultdict(lambda:[0,0,0])
for k,s in zip(c.piece,c.s):
    if k>=0: agg[int(k)][s-1]+=1
N['crp']=[x for k,v in sorted(agg.items()) for x in (k,*v)]
N['crash']=[x for lo,la,s,y in zip(c.lon,c.lat,c.s,c.yr) for x in (int(round(lo*1e5)),int(round(la*1e5)),int(s),int(y)-2000)]
# hotspots: places with at least 4 bike collisions within 50 m, greedily picked from the densest
xy=np.c_[c.E.values,c.N.values]; ct=cKDTree(xy)
nb=[ct.query_ball_point(p,50) for p in xy]
w=np.array([W[s] for s in c.s])
order=sorted(range(len(c)),key=lambda i:(-len(nb[i]),-w[nb[i]].sum()))
used=np.zeros(len(c),bool); hot=[]
names=N['names']
for i in order:
    m=[j for j in nb[i] if not used[j]]
    if len(m)<4: continue
    used[m]=True
    sub=c.iloc[m]; ks=int((sub.s>=2).sum())
    nm=collections.Counter(names[N['nm'][k]] for k in sub.piece if k>=0 and names[N['nm'][k]])
    hot.append(dict(lat=round(float(sub.lat.mean()),5),lng=round(float(sub.lon.mean()),5),n=len(m),ksi=ks,f=int((sub.s==3).sum()),nm=' and '.join(x for x,_ in nm.most_common(2))))
hot.sort(key=lambda h:(-h['n'],-h['ksi']))
N['hot']=hot
print('hotspots',len(hot),'collisions in hotspots',sum(h['n'] for h in hot))
for h in hot[:12]: print(' ',h)
json.dump(N,open('data/network6.json','w'),separators=(',',':'),allow_nan=False)
