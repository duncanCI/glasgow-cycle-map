import numpy as np, math, io, json, base64, requests, geopandas as gpd, pandas as pd
from PIL import Image
from concurrent.futures import ThreadPoolExecutor
from scipy.ndimage import map_coordinates
Z=13; X0,X1,Y0,Y1=-4.40,-4.06,55.775,55.935; DX,DY=0.0006,0.00034
n=2**Z
fx=lambda lon:(lon+180)/360*n
fy=lambda lat:(1-np.arcsinh(np.tan(np.radians(lat)))/np.pi)/2*n
tx0,tx1=int(fx(X0)),int(fx(X1)); ty0,ty1=int(fy(Y1)),int(fy(Y0))
S=requests.Session()
def get(xy):
    x,y=xy; r=S.get(f"https://elevation-tiles-prod.s3.us-east-1.amazonaws.com/terrarium/{Z}/{x}/{y}.png",timeout=60); r.raise_for_status()
    a=np.asarray(Image.open(io.BytesIO(r.content)).convert('RGB')).astype(np.float64)
    return xy,a[...,0]*256+a[...,1]+a[...,2]/256-32768
tiles=[(x,y) for x in range(tx0,tx1+1) for y in range(ty0,ty1+1)]
M=np.zeros(((ty1-ty0+1)*256,(tx1-tx0+1)*256))
with ThreadPoolExecutor(8) as ex:
    for (x,y),a in ex.map(get,tiles): M[(y-ty0)*256:(y-ty0+1)*256,(x-tx0)*256:(x-tx0+1)*256]=a
lons=np.arange(X0,X1+1e-9,DX); lats=np.arange(Y0,Y1+1e-9,DY)
LO,LA=np.meshgrid(lons,lats)
px=(fx(LO)-tx0)*256-0.5; py=(fy(LA)-ty0)*256-0.5
E=map_coordinates(M,[py,px],order=1)
print('tiles',len(tiles),'grid',E.shape,'min/max',E.min().round(1),E.max().round(1))
for nm,lo,la in [('George Sq',-4.2502,55.8612),('Southbrae Dr',-4.3385,55.8845),('Cathkin Braes',-4.215,55.795),('Park Circus',-4.2805,55.8678),('Clyde at Broomielaw',-4.262,55.8573)]:
    i=int(round((la-Y0)/DY)); j=int(round((lo-X0)/DX)); print(nm, round(E[i,j],1))
q=np.clip(np.round(E*10),0,65535).astype('<u2')
json.dump(dict(x0=X0,y0=Y0,dx=DX,dy=DY,nx=len(lons),ny=len(lats),b64=base64.b64encode(q.tobytes()).decode()),open('data/elev.json','w'),separators=(',',':'))
import os; print('elev KB',os.path.getsize('data/elev.json')//1024)
# one-way flags per piece, matching build_network.py's way order
g=gpd.read_file('data/net_city.gpkg').explode(index_parts=False).reset_index(drop=True)
g=g[~((g.highway=='service') & g['name'].isna() & (g['Infrastructure type']=='Mixed Traffic Street'))].reset_index(drop=True)
N=json.load(open('data/network2.json'))
OW={'yes':1,'true':1,'1':1,'-1':-1}
wo=[OW.get(str(v).strip().lower(),0) for v in g['oneway']]
N['ow']=[wo[w] for w in N['way']]
print('one-way pieces',sum(1 for v in N['ow'] if v),'of',len(N['ow']), 'check len', len(g), max(N['way'])+1)
json.dump(N,open('data/network3.json','w'),separators=(',',':'),allow_nan=False)
