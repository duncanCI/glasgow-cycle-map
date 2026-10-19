"""Add a level for every network piece: 0 at street level, positive on a bridge or upper layer, negative in a tunnel
or underpass. Used to tell a real road crossing from a path passing over or under the road."""
import json, requests, geopandas as gpd
U="https://services-eu1.arcgis.com/zci5bUiJ8olAal7N/arcgis/rest/services/OpenStreetMap_Highways_for_Europe/FeatureServer/0/query"
G='{"xmin":-4.42,"ymin":55.78,"xmax":-4.07,"ymax":55.93,"spatialReference":{"wkid":4326}}'
rows=[]; off=0
while True:
    r=requests.get(U,params=dict(where="bridge IS NOT NULL OR tunnel IS NOT NULL OR (layer IS NOT NULL AND layer <> '0') OR covered IS NOT NULL",geometry=G,geometryType="esriGeometryEnvelope",inSR=4326,
       outFields="osm_id,bridge,tunnel,layer,covered",returnGeometry="false",f="json",resultOffset=off,resultRecordCount=2000,orderByFields="OBJECTID"),timeout=90).json()
    fs=r.get('features',[]); rows+=[f['attributes'] for f in fs]
    if len(fs)<2000: break
    off+=2000
def level(a):
    b=str(a.get('bridge')).lower(); t=str(a.get('tunnel')).lower(); c=str(a.get('covered')).lower(); l=a.get('layer')
    try: l=int(float(l))
    except Exception: l=None
    if b not in ('none','no','nan',''): return l if (l and l>0) else 1
    if t not in ('none','no','nan','') or c in ('yes',): return l if (l and l<0) else -1
    return l or 0
lev={}
for a in rows:
    if a.get('osm_id') is None: continue
    v=level(a)
    if v: lev[str(int(a['osm_id']))]=max(-3,min(3,v))
print('ways off street level',len(lev))
g=gpd.read_file('data/net_city.gpkg').explode(index_parts=False).reset_index(drop=True)
g=g[~((g.highway=='service') & g['name'].isna() & (g['Infrastructure type']=='Mixed Traffic Street'))].reset_index(drop=True)
wayosm=g.osm_id.astype(str).tolist()
N=json.load(open('data/network7.json'))
lay=[lev.get(wayosm[w],0) if 0<=w<len(wayosm) else 0 for w in N['way']]
import collections; print('pieces by level',collections.Counter(lay))
N['lay']=lay
json.dump(N,open('data/network8.json','w'),separators=(',',':'),allow_nan=False)
# spot checks
names=N['names']; nm=N['nm']
for t in ['George V Bridge','Glasgow Bridge','Kingston Bridge','Clydeside Expressway','Kelvin Walkway']:
    ks=[k for k in range(len(nm)) if nm[k]>=0 and names[nm[k]]==t]
    print(t,len(ks),collections.Counter(lay[k] for k in ks))
