import json, collections, numpy as np, geopandas as gpd, pandas as pd
from shapely.geometry import Point
N=json.load(open('data/network.json'))
names=N['names']
def dec(a):
    out=[];x=y=0
    for i in range(0,len(a),2): x+=a[i];y+=a[i+1]; out.append((x/1e5,y/1e5))
    return out
G=[dec(g) for g in N['geom']]
mid=[g[len(g)//2] for g in G]
# per CN feature: street-length by name and centroid
by=collections.defaultdict(collections.Counter); cxy=collections.defaultdict(list)
for k,c in enumerate(N['cn']):
    if c>=0:
        nm=names[N['nm'][k]]
        if nm: by[c][nm]+=N['lens'][k]
        cxy[c].append(mid[k])
ALL=lambda lo,la: True
RULES={'Alexandra Park Street':ALL,'Broomfield Road':ALL,'Broomloan Road':ALL,'Newhall Street':ALL,'Polmadie Road':ALL,
 'Aikenhead Road':lambda lo,la: la>55.825,'Gallowgate':lambda lo,la: -4.235<lo<-4.20,'Langside Avenue':ALL,'Minard Road':ALL,
 'Millerston Street':ALL,'Queen Margaret Drive':ALL,'Somerville Drive':ALL,'Viewpark Avenue':ALL,'Alexandra Parade':ALL,
 'Bellgrove Street':ALL,'Abercromby Street':ALL,'Carlisle Street':ALL,'Cumbernauld Road':lambda lo,la: lo<-4.19,'Provanmill Road':ALL,
 'Duke Street':lambda lo,la: lo>-4.22,'Shettleston Road':ALL,'Edinburgh Road':lambda lo,la: -4.19<lo<-4.16,'Kelvin Way':ALL,
 'Gibson Street':ALL,'Park Road':ALL,'Govan Road':lambda lo,la: lo<-4.29,'Summertown Road':ALL,
 'Great Western Road':lambda lo,la: -4.296<lo<-4.265,'Highburgh Road':ALL,'Hyndland Road':ALL,"King's Drive":ALL,'Kings Drive':ALL,
 'London Road':lambda lo,la: -4.247<lo<-4.224,'Lorne Street':ALL,'Maryhill Road':lambda lo,la: la<55.885,'Castlebank Street':ALL,
 'South Street':ALL,'Paisley Road West':lambda lo,la: -4.315<lo<-4.27,'Royston Road':ALL,'Sauchiehall Street':lambda lo,la: lo<-4.268,
 'Shields Road':ALL,'Maxwell Road':ALL,'Wishart Street':ALL,'Bilsland Drive':ALL,'Hawthorn Street':ALL,'Byres Road':ALL,
 'Dumbreck Road':ALL,'Titwood Road':ALL,'Battlefield Road':ALL,'Sinclair Drive':ALL}
cg=[]
for i,c in enumerate(N['cnInfo']):
    tot=sum(by[i].values())
    if not tot: cg.append(0); continue
    lo,la=np.mean(cxy[i],axis=0)
    hit=sum(v for s,v in by[i].items() if s in RULES and RULES[s](lo,la))
    cg.append(1 if hit/tot>=0.5 else 0)
km=sum(c['km'] for c,f in zip(N['cnInfo'],cg) if f); kmnew=sum(c['km'] for c,f in zip(N['cnInfo'],cg) if f and c['st']>0)
print('2032 matched sections',sum(cg),'km',round(km,1),'of which not yet built',round(kmnew,1))
N['cg']=cg
# data zones
b=gpd.read_file('data/boundary.geojson').to_crs(27700)
dz=gpd.read_file('dz.gpkg').to_crs(27700)
dz=dz[dz.representative_point().within(b.union_all())].reset_index(drop=True)
print('glasgow DZs',len(dz),'pop',int(dz.Total_population.sum()))
pts=gpd.GeoDataFrame({'k':range(len(mid))},geometry=[Point(x,y) for x,y in mid],crs=4326).to_crs(27700)
j=gpd.sjoin(pts,dz[['geometry']],predicate='within')
pdz=np.full(len(mid),-1); pdz[j.k.values]=j.index_right.values
N['pdz']=[int(x) for x in pdz]
def enc(coords):
    out=[];px=py=0
    for x,y in coords:
        X=int(round(x*1e5));Y=int(round(y*1e5)); out+=[X-px,Y-py]; px,py=X,Y
    return out
dzs=dz.copy(); dzs['geometry']=dzs.simplify(12); dzs=dzs.to_crs(4326)
N['dz']=[]
for i,r in dzs.iterrows():
    rings=[enc(p.exterior.coords) for p in getattr(r.geometry,'geoms',[r.geometry]) if p.geom_type=='Polygon']
    N['dz'].append(dict(id=r.DataZone,pop=int(r.Total_population),simd=int(r.SIMD2020v2_Decile) if pd.notna(r.SIMD2020v2_Decile) else None,pc=round(float(r.pcycle),1) if pd.notna(r.pcycle) else None,g=rings))
json.dump(N,open('data/network2.json','w'),separators=(',',':'),allow_nan=False)
import os; print('MB',os.path.getsize('data/network2.json')/1e6)
print(dz[['Total_population','pcycle','SIMD2020v2_Decile']].describe().round(2))
