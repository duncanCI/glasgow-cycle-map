"""Normalise bike collisions by how many people cycle there.
Exposure: NPT modelled daily cycle flows (rnet, baseline), scaled to Glasgow City Council's automatic cycle counters,
and checked against DfT counted pedal-cycle AADF on major roads (also published by the council)."""
import json, numpy as np, pandas as pd, geopandas as gpd, requests, pyproj
from shapely.geometry import LineString, Point
from shapely.strtree import STRtree
from scipy.stats import spearmanr
N=json.load(open('data/network6.json')); P=len(N['pu'])
T2=pyproj.Transformer.from_crs(4326,27700,always_xy=True)
def dec(a):
    out=[];x=y=0
    for i in range(0,len(a),2): x+=a[i];y+=a[i+1]; out.append((x/1e5,y/1e5))
    return np.array(out)
lines=[]
for g in N['geom']:
    p=dec(g); x,y=T2.transform(p[:,0],p[:,1]); lines.append(LineString(np.c_[x,y]))
rn=gpd.read_file('rnet.gpkg',bbox=(-4.42,55.78,-4.07,55.93)).to_crs(27700)
rn['f']=(rn.all_fastest_bicycle.fillna(0)+rn.all_quietest_bicycle.fillna(0))/2
print('NPT segments in the area',len(rn),'| median daily flow',rn.f.median())
tree=STRtree(rn.geometry.values); geoms=rn.geometry.values; fl=rn.f.values
npt=np.zeros(P)
for k,l in enumerate(lines):
    mid=l.interpolate(0.5,normalized=True); idx=tree.query(mid.buffer(15))
    best=0
    for i in idx:
        if geoms[i].distance(mid)<=15: best=max(best,fl[i])
    npt[k]=best
print('pieces with a modelled flow',int((npt>0).sum()),'of',P)
mids=[l.interpolate(0.5,normalized=True) for l in lines]; ptree=STRtree(np.array(mids))
def piece_near(x,y,r=30):
    pt=Point(x,y); idx=ptree.query(pt.buffer(r)); best=None
    for i in idx:
        d=lines[i].distance(pt)
        if d<=r and (best is None or (npt[i],-d)>(npt[best],-lines[best].distance(pt))): best=i
    return best
# council counters
A="https://utility.arcgis.com/usrsvcs/servers/415f8b2ed6a143a5899b843922203d5f/rest/services/AGOL/Automatic_Traffic_Cycle_Pedestrian_Counters/FeatureServer/4/query"
r=requests.get(A,params=dict(where="1=1",outFields="SITE_NAME,LOCATION,TYPE,ANNUAL_TOTAL_2022,ANNUAL_TOTAL_2023,ANNUAL_TOTAL_2024",outSR=27700,f="json"),timeout=60).json()
def num(v):
    try: return float(str(v).replace(',',''))
    except: return np.nan
cs=[]
for f in r['features']:
    a=f['attributes']; g=f.get('geometry') or {}
    vals=[num(a[k]) for k in ('ANNUAL_TOTAL_2022','ANNUAL_TOTAL_2023','ANNUAL_TOTAL_2024')]
    vals=[v for v in vals if np.isfinite(v) and v>0]
    if not vals or 'x' not in g: continue
    k=piece_near(g['x'],g['y'])
    if k is None or npt[k]<=0: continue
    cs.append(dict(site=a['SITE_NAME'],daily=np.mean(vals)/365,npt=npt[k],k=int(k),x=g['x'],y=g['y']))
cs=pd.DataFrame(cs)
ratio=cs.daily/cs.npt; scale=float(np.median(ratio)); rho=spearmanr(cs.daily,cs.npt).correlation
print('council counters used',len(cs),'| median counted/modelled',round(scale,2),'| Spearman',round(rho,2))
# DfT counted pedal cycles on major roads, latest year in the council layer
D="https://services2.arcgis.com/Ne8d9gKn5SJ3eAaw/arcgis/rest/services/DFT_Traffic_Counts_AADF_NoDirections/FeatureServer/0/query"
r=requests.get(D,params=dict(where="year=2018 AND estimation_method='Counted'",outFields="road_name,pedal_cycles,easting,northing",f="json",resultRecordCount=2000),timeout=60).json()
dd=[]
for f in r['features']:
    a=f['attributes']; k=piece_near(a['easting'],a['northing'],40)
    if k is not None and npt[k]>0 and a['pedal_cycles']: dd.append((a['pedal_cycles'],npt[k]))
dd=np.array(dd)
if len(dd): print('DfT counted sites',len(dd),'| median counted/modelled',round(float(np.median(dd[:,0]/dd[:,1])),2),'| Spearman',round(spearmanr(dd[:,0],dd[:,1]).correlation,2))
# exposure and smoothed relative risk per street piece
E=npt*scale; pos=E[E>0]; floor=max(1.0,float(np.percentile(pos,5)))
E=np.where(E>0,E,floor)
w=np.zeros(P)
crp=N['crp']
for i in range(0,len(crp),4): w[crp[i]]=crp[i+1]+3*crp[i+2]+6*crp[i+3]
rbar=w.sum()/E.sum()
RR=(w+1)/(rbar*E+1)
risk=[x for k in np.where(w>0)[0] for x in (int(k),round(float(RR[k]),2))]
N['bpd']=[int(round(v)) for v in E]          # modelled bikes a day on each piece
N['rr']=risk                                  # relative risk where collisions are recorded
# hotspots: collisions against the cycling through the junction
cx=np.array([m.x for m in mids]); cy=np.array([m.y for m in mids])
for h in N['hot']:
    x,y=T2.transform(h['lng'],h['lat']); near=np.where(np.hypot(cx-x,cy-y)<50)[0]
    exp_bikes=E[near].sum()/2 if len(near) else floor
    hw=h['n']-h['ksi']+3*(h['ksi']-h['f'])+6*h['f']
    h['bpd']=int(round(exp_bikes)); h['rr']=round(float((hw+1)/(rbar*exp_bikes+1)),1)
print('hotspots by relative risk:')
for h in sorted(N['hot'],key=lambda h:-h['rr'])[:10]: print('  ',h['nm'],'| collisions',h['n'],'| bikes a day',h['bpd'],'| times average',h['rr'])
print('pieces with collisions',int((w>0).sum()),'| relative risk above 2:',int((RR[w>0]>2).sum()))
N['calib']=dict(counters=int(len(cs)),scale=round(scale,2),rho=round(float(rho),2),dft=int(len(dd)))
json.dump(N,open('data/network7.json','w'),separators=(',',':'),allow_nan=False)
