"""Add the streets around Glasgow, out to 8 km beyond the city boundary, so routes can start, end or pass outside it.

Glasgow stays the focus: its own streets, protected network, analysis and figures are untouched. The new streets are
appended to the network with an 'out' flag; the page routes over them but leaves them out of every Glasgow figure.

Sources (the same as for Glasgow):
  - Network Planning Tool for Scotland, May 2025 street layer (cbd_layer_2025-05-01.gpkg, Scotland-wide, derived from
    OpenStreetMap): infrastructure type, level of service, traffic volume, speed limit.
    https://github.com/nptscot/npt/releases/download/v2025-05-01/cbd_layer_2025-05-01.gpkg
  - OpenStreetMap via Esri's OpenStreetMap highways service: names, one-way rules, contraflow, bridges and tunnels.
Not yet available outside Glasgow: collisions, cycle flows, the council's signal data, the City Network plan and the
community map (crossing evidence follows from the weekly OpenStreetMap refresh once its area is widened).

    python3 scripts/build_region.py path/to/cbd_layer_2025-05-01.gpkg
"""
import json, re, sys, time, math, concurrent.futures as cf
from collections import defaultdict
from pathlib import Path
import numpy as np, pandas as pd, geopandas as gpd, pyogrio, requests, pyproj
from shapely.geometry import Polygon, LineString, MultiLineString
from shapely import ops
from scipy.spatial import cKDTree

ROOT = Path(__file__).resolve().parent.parent
RING_M = 8000
OSM = 'https://services-eu1.arcgis.com/zci5bUiJ8olAal7N/arcgis/rest/services/OpenStreetMap_Highways_for_Europe/FeatureServer/0/query'
FIELDS = 'osm_id,name,ref,highway,service,oneway,oneway_bicycle,cycleway,bicycle,access,bridge,tunnel,layer,covered,lanes,maxspeed'
LOS = {'High': 0, 'Medium': 1, 'Low': 2, 'Should not be used (mixed traffic)': 3}
INF = {'Mixed Traffic Street': 0, 'Painted Cycle Lane': 1, 'Segregated Track (narrow)': 2, 'Segregated Track (wide)': 3, 'Off Road Cycleway': 4, 'Shared Footway': 5}
VOL = {'0 to 999': 0, '1000 to 1999': 1, '2000 to 3999': 2, '4000+': 3}
MAJOR = {'primary', 'primary_link', 'secondary', 'secondary_link', 'tertiary', 'tertiary_link', 'trunk', 'trunk_link'}
NO_BIKES = {'motorway', 'motorway_link', 'proposed', 'construction', 'platform', 'bus_stop', 'raceway', 'corridor', 'elevator'}
T = pyproj.Transformer.from_crs(4326, 27700, always_xy=True).transform
TI = pyproj.Transformer.from_crs(27700, 4326, always_xy=True).transform

def blob(text, tag):
    return json.loads(re.search(r'<script id="%s" type="application/json">(.*?)</script>' % tag, text, flags=re.S).group(1))

def dec(a):
    out = []; x = y = 0
    for i in range(0, len(a), 2):
        x += a[i]; y += a[i + 1]; out.append((x / 1e5, y / 1e5))
    return out

def enc(coords):
    out = []; px = py = 0
    for x, y in coords:
        X = int(round(x * 1e5)); Y = int(round(y * 1e5)); out += [X - px, Y - py]; px, py = X, Y
    return out

def num(v):
    m = re.match(r'(\d+)', str(v)); return float(m.group(1)) if m else None

def osm_attrs(bbox):
    G = json.dumps({'xmin': bbox[0], 'ymin': bbox[1], 'xmax': bbox[2], 'ymax': bbox[3], 'spatialReference': {'wkid': 4326}})
    def page(off):
        p = dict(where='highway IS NOT NULL', geometry=G, geometryType='esriGeometryEnvelope', inSR=4326, spatialRel='esriSpatialRelIntersects',
                 outFields=FIELDS, returnGeometry='false', resultOffset=off, resultRecordCount=2000, orderByFields='OBJECTID', f='json')
        for _ in range(4):
            try: return [f['attributes'] for f in requests.get(OSM, params=p, timeout=90).json()['features']]
            except Exception as e: err = e; time.sleep(2)
        raise err
    out = []; off = 0
    with cf.ThreadPoolExecutor(6) as ex:
        while True:
            batch = list(ex.map(page, range(off, off + 12000, 2000))); n = 0
            for b in batch: out += b; n += len(b)
            if n < 12000: break
            off += 12000
    return {str(int(a['osm_id'])): a for a in out if a.get('osm_id') is not None}

def main(cbd_path):
    t0 = time.time(); text = (ROOT / 'index.html').read_text(); N = blob(text, 'net-data')
    if 'out' in N and any(N['out']): sys.exit('The network already includes the surrounding area; rebuild from a Glasgow-only page first.')
    P0 = len(N['pu'])
    gcc = Polygon(dec(N['boundary'][0])); g27 = ops.transform(T, gcc)
    region27 = g27.buffer(RING_M, 16); ring27 = region27.difference(g27); bbox = ops.transform(TI, region27).bounds
    print('region bbox', [round(v, 4) for v in bbox])
    df = pyogrio.read_dataframe(cbd_path, bbox=bbox).to_crs(27700)
    df = df[df.intersects(ring27)].copy(); print('NPT ways touching the ring', len(df), f'{time.time() - t0:.0f} s')
    A = osm_attrs(bbox); print('OpenStreetMap ways with attributes', len(A), f'{time.time() - t0:.0f} s')
    df['oid'] = df.osm_id.astype(str).str.replace(r'\.0$', '', regex=True)
    get = lambda o, k: (A.get(o) or {}).get(k)
    df['name'] = [get(o, 'name') or get(o, 'ref') or '' for o in df.oid]
    df = df[~df.highway.isin(NO_BIKES)]
    df = df[~df.oid.map(lambda o: str(get(o, 'bicycle')).lower() in ('no', 'dismount') or str(get(o, 'access')).lower() in ('no', 'private'))]
    # unnamed service roads: most are driveways and car-park aisles that lead nowhere, but some carry the only link
    # between paths (a canal towpath to the road over its bridge, say). Keep one when it joins the rest of the network
    # at two or more places, or meets a path, cycleway or track; drop it when it only hangs off a single point.
    cand = (df.highway == 'service') & (df.name == '') & (df['Infrastructure type'] == 'Mixed Traffic Street')
    vkey = lambda c: (round(c[0], 2), round(c[1], 2))
    def verts(geom): return set(vkey(c) for g in getattr(geom, 'geoms', [geom]) for c in g.coords)
    kept_v, path_v = set(), set()
    for hw, geom in zip(df.highway[~cand], df.geometry[~cand]):
        v = verts(geom); kept_v |= v
        if hw in ('cycleway', 'footway', 'path', 'track', 'bridleway', 'pedestrian', 'steps'): path_v |= v
    keep = [len(verts(geom) & kept_v) >= 2 or bool(verts(geom) & path_v) for geom in df.geometry[cand]]
    drop = df[cand].index[[not k for k in keep]]
    print('unnamed service roads: kept as links', sum(keep), '| dropped', len(drop))
    df = df.drop(index=drop)
    # only the part outside the city: Glasgow keeps its own streets
    df['geometry'] = df.geometry.intersection(ring27)
    df = df[~df.geometry.is_empty].explode(index_parts=False).reset_index(drop=True)
    df = df[df.geometry.geom_type == 'LineString']; df = df[df.length >= 2].reset_index(drop=True)
    print('ways kept outside the city', len(df))
    # nodes at shared vertices (rounded to 1 cm in metres)
    key = lambda c: (round(c[0], 2), round(c[1], 2)); cnt = defaultdict(int)
    for geom in df.geometry:
        for k in set(key(c) for c in geom.coords): cnt[k] += 1
    pieces = []
    for i, geom in enumerate(df.geometry):
        cs = list(geom.coords); s = 0
        for j in range(1, len(cs)):
            if j == len(cs) - 1 or cnt[key(cs[j])] > 1:
                seg = cs[s:j + 1]
                if len(seg) >= 2 and LineString(seg).length >= 0.5: pieces.append((i, seg))
                s = j
    print('pieces', len(pieces))
    # Glasgow's nodes: join the new streets to the city's where they meet at the boundary (dead ends near the line)
    gn = np.array([T(x, y) for x, y in dec(N['nodes'])]); deg = np.zeros(len(gn), int)
    for u, v in zip(N['pu'], N['pv']): deg[u] += 1; deg[v] += 1
    from shapely.geometry import Point
    bline = g27.exterior
    near_b = np.array([deg[n] <= 1 and bline.distance(Point(*gn[n])) <= 40 for n in range(len(gn))])
    ends_idx = np.where(near_b)[0]; ends_tree = cKDTree(gn[ends_idx]); print('Glasgow street ends at the boundary', len(ends_idx))
    newnodes = {}; nodes_xy = list(gn); joined = 0
    def node_for(c, at_end):
        nonlocal joined
        k = key(c)
        if k in newnodes: return newnodes[k]
        if bline.distance(Point(c)) <= 25:
            d, j = ends_tree.query(c, distance_upper_bound=25)
            if np.isfinite(d): newnodes[k] = int(ends_idx[j]); joined += 1; return newnodes[k]
        newnodes[k] = len(nodes_xy); nodes_xy.append(np.array(c)); return newnodes[k]
    rows = []
    for i, seg in pieces:
        u = node_for(seg[0], False); v = node_for(seg[-1], True)
        if u == v: continue
        # pull the ends onto the joined Glasgow nodes so the lines meet
        seg = [tuple(nodes_xy[u])] + seg[1:-1] + [tuple(nodes_xy[v])]
        rows.append((i, u, v, seg))
    print('joined to Glasgow at', joined, 'points | new nodes', len(nodes_xy) - len(gn))
    # attributes
    names = list(N['names']); nidx = {n: i for i, n in enumerate(names)}
    def name_i(n):
        if n not in nidx: nidx[n] = len(names); names.append(n)
        return nidx[n]
    OW = {'yes': 1, 'true': 1, '1': 1, '-1': -1}
    recs = []
    for i, u, v, seg in rows:
        r = df.iloc[i]; o = r.oid; los = LOS.get(r['Level of Service'], -1); rated = los >= 0
        spd = num(get(o, 'maxspeed')) or (None if pd.isna(r['Speed limit']) else float(r['Speed limit']))
        if los < 0: los = 1 if (r.highway not in MAJOR and (spd is None or spd <= 30)) else 2
        lanes = num(get(o, 'lanes')) or 0; ow = OW.get(str(get(o, 'oneway')).strip().lower(), 0)
        if ow and (str(get(o, 'oneway_bicycle')).lower() == 'no' or str(get(o, 'cycleway')).lower().startswith('opposite')): ow = 0
        if ow == -1: u, v, seg, ow = v, u, seg[::-1], 1  # store every one-way piece in its direction of travel
        hard = los == 3 or r.highway in ('trunk', 'trunk_link') or (r.highway in ('primary', 'secondary') and ow and lanes >= 2)
        b, tn, cv = str(get(o, 'bridge')).lower(), str(get(o, 'tunnel')).lower(), str(get(o, 'covered')).lower()
        try: ly = int(float(get(o, 'layer')))
        except Exception: ly = 0
        lay = (ly if ly > 0 else 1) if b not in ('none', 'no', 'nan', '') else ((ly if ly < 0 else -1) if (tn not in ('none', 'no', 'nan', '') or cv == 'yes') else ly)
        inf = INF.get(r['Infrastructure type'], 0)
        recs.append(dict(u=u, v=v, seg=list(seg), a=(int(los), int(rated), inf, 0 if spd is None else int(spd), VOL.get(r['Traffic volume category'], -1), name_i(r['name']), int(ow), int(hard), max(-3, min(3, int(lay))))))
    # join pieces that meet end to end with nothing else at the joint and the same attributes: only junctions matter
    # for routing, and it halves the size
    inc = defaultdict(list)
    for j, r in enumerate(recs): inc[r['u']].append(j); inc[r['v']].append(j)
    alive = [True] * len(recs); merged = 0
    for n in list(inc.keys()):
        if n < len(gn): continue
        js = [j for j in inc[n] if alive[j]]
        if len(js) != 2 or js[0] == js[1]: continue
        A1, B1 = recs[js[0]], recs[js[1]]
        if A1['a'] != B1['a']: continue
        # orient: A ends at n, B starts at n
        if A1['v'] != n: A1['u'], A1['v'], A1['seg'] = A1['v'], A1['u'], A1['seg'][::-1]
        if B1['u'] != n: B1['u'], B1['v'], B1['seg'] = B1['v'], B1['u'], B1['seg'][::-1]
        if A1['a'][6] and (A1['v'] != n or B1['u'] != n): continue
        if A1['u'] == B1['v']: continue
        if A1['a'][6]:  # one-way: both must still run the same way after orienting
            pass
        A1['seg'] = A1['seg'] + B1['seg'][1:]; A1['v'] = B1['v']; alive[js[1]] = False; merged += 1
        inc[B1['v']] = [js[0] if j == js[1] else j for j in inc[B1['v']]]
    recs = [r for j, r in enumerate(recs) if alive[j]]
    print('joined end to end', merged, '| pieces now', len(recs))
    out = dict(pu=[], pv=[], los=[], rated=[], inf=[], spd=[], vol=[], nm=[], cn=[], way=[], geom=[], lens=[], phard=[], pdz=[], ow=[], qow=[], bpd=[], lay=[], hard=[])
    for r in recs:
        los, rated, inf, spd, vol, nmi, ow, hard, lay = r['a']; seg = r['seg']
        ll = [TI(x, y) for x, y in seg]; ls = LineString(ll); s = ls.simplify(0.00003) if len(ll) > 2 else ls  # about 3 m outside the city
        out['pu'].append(r['u']); out['pv'].append(r['v']); out['los'].append(los); out['rated'].append(rated); out['inf'].append(inf)
        out['spd'].append(spd); out['vol'].append(vol); out['nm'].append(nmi); out['cn'].append(-1); out['way'].append(-1)
        out['geom'].append(enc(s.coords)); out['lens'].append(int(round(LineString(seg).length)))
        out['phard'].append(hard); out['pdz'].append(-1); out['ow'].append(ow); out['qow'].append(int(bool(ow) and inf == 0 and los <= 1))
        out['bpd'].append(0); out['lay'].append(lay); out['hard'].append(hard)
    P1 = len(out['pu']); NN = len(nodes_xy); NN0 = len(gn)
    # node flags for the new nodes (and Glasgow nodes the new streets join)
    hardn = list(N['hard']) + [0] * (NN - NN0); gstn = list(N['gst']) + [0] * (NN - NN0); inc = defaultdict(int); incg = defaultdict(int)
    for k in range(P1):
        for n in (out['pu'][k], out['pv'][k]):
            if out['hard'][k]: hardn[n] = 1
            inc[n] += 1; incg[n] += 1 if out['lay'][k] else 0
    gsn = list(N['gs']) + [0] * (NN - NN0)
    for n in range(NN0, NN): gsn[n] = int(inc[n] > 0 and incg[n] == inc[n]); gstn[n] = int(incg[n] > 0)
    # append to the network
    for f in ('pu', 'pv', 'los', 'rated', 'inf', 'spd', 'vol', 'nm', 'cn', 'way', 'geom', 'lens', 'phard', 'pdz', 'ow', 'qow', 'bpd', 'lay'):
        N[f] = list(N[f]) + out[f]
    N['out'] = [0] * P0 + [1] * P1
    N['names'] = names; N['hard'] = hardn; N['gs'] = gsn; N['gst'] = gstn; N['signal'] = list(N['signal']) + [0] * (NN - NN0)
    N['nodes'] = enc(dec(N['nodes']) + [TI(*c) for c in nodes_xy[NN0:]])
    reg = ops.transform(TI, region27.simplify(30))
    N['region'] = [enc(reg.exterior.coords)]
    N['regionInfo'] = dict(cityNodes=NN0, ring_km=RING_M / 1000, pieces=P1, km=round(sum(out['lens']) / 1000), source='Network Planning Tool for Scotland May 2025 street layer and OpenStreetMap')
    s = json.dumps(N, separators=(',', ':'), ensure_ascii=False).replace('<', '\\u003c')
    text = re.sub(r'(<script id="net-data" type="application/json">).*?(</script>)', lambda m: m.group(1) + s + m.group(2), text, count=1, flags=re.S)
    (ROOT / 'index.html').write_text(text)
    print(f'added {P1} pieces, {round(sum(out["lens"]) / 1000)} km of streets and paths outside the city | network blob {len(s) / 1e6:.1f} MB | {time.time() - t0:.0f} s')

if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else 'cbd_layer_2025-05-01.gpkg')
