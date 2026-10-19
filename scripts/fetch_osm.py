import requests, json, concurrent.futures as cf
U="https://services-eu1.arcgis.com/zci5bUiJ8olAal7N/arcgis/rest/services/OpenStreetMap_Highways_for_Europe/FeatureServer/0/query"
G='{"xmin":-4.42,"ymin":55.78,"xmax":-4.07,"ymax":55.93,"spatialReference":{"wkid":4326}}'
F="osm_id,name,highway,maxspeed,ref,cycleway,bicycle,parking_lane_both,parking_lane_left,parking_lane_right,lanes,oneway,lit,osm_timestamp"
def page(off):
    p=dict(where="1=1",geometry=G,geometryType="esriGeometryEnvelope",inSR=4326,spatialRel="esriSpatialRelIntersects",
           outFields=F,returnGeometry="false",resultOffset=off,resultRecordCount=2000,orderByFields="OBJECTID",f="json")
    for _ in range(3):
        try:
            r=requests.get(U,params=p,timeout=60).json(); return [f['attributes'] for f in r['features']]
        except Exception as e: err=e
    raise err
out=[]
with cf.ThreadPoolExecutor(6) as ex:
    for res in ex.map(page, range(0,62000,2000)): out+=res
print(len(out))
json.dump(out, open('data/osm_attrs.json','w'))
