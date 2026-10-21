"""Add the footbridges, ramps, steps and path links that join the network but are missing from it.

The Network Planning Tool's street layer leaves out most footways, footbridges and steps, so some ways onto paths
don't exist in the map: the footbridge and ramp from Kelvinside Avenue over Maryhill Road to the canal, say. This
takes them from OpenStreetMap, for Glasgow and the area around it, keeping only those that join two parts of the
network, and adds them for routing only: every Glasgow figure stays as it was.

  - Pavements alongside roads (footway=sidewalk or crossing, or a footway running beside a road) stay out: riding
    on them isn't legal. Private paths and paths where cycling is banned stay out.
  - A link that meets a street or path between its junctions gets a junction there: the street or path is copied
    in two routing-only parts, split at that point, alongside the original.
  - Steps are marked (N.stp); the page keeps cautious riders and children off them and tells others to carry.

    python3 scripts/build_links.py            (after build_region.py)
"""
import json, re, sys, time, math, concurrent.futures as cf
from collections import defaultdict
from pathlib import Path
import numpy as np, requests, pyproj
from scipy.spatial import cKDTree
from shapely.geometry import LineString, Point, Polygon

ROOT = Path(__file__).resolve().parent.parent
OSM = 'https://services-eu1.arcgis.com/zci5bUiJ8olAal7N/arcgis/rest/services/OpenStreetMap_Highways_for_Europe/FeatureServer/0/query'
KINDS = ('footway', 'path', 'steps', 'pedestrian', 'bridleway', 'cycleway', 'track', 'service')  # service: car-park and yard lanes the street layer leaves out, kept only where they join two places
T = pyproj.Transformer.from_crs(4326, 27700, always_xy=True).transform
TI = pyproj.Transformer.from_crs(27700, 4326, always_xy=True).transform

def dec(a):
    out = []; x = y = 0
    for i in range(0, len(a), 2): x += a[i]; y += a[i + 1]; out.append((x / 1e5, y / 1e5))
    return out

def enc(coords):
    out = []; px = py = 0
    for x, y in coords:
        X = int(round(x * 1e5)); Y = int(round(y * 1e5)); out += [X - px, Y - py]; px, py = X, Y
    return out

def fetch(bbox):
    """Every matching way in the box: the ids first, then the ways 500 at a time (paging by offset can stop short)."""
    where = 'highway IN (%s)' % ','.join("'%s'" % k for k in KINDS)
    G = json.dumps({'xmin': bbox[0], 'ymin': bbox[1], 'xmax': bbox[2], 'ymax': bbox[3], 'spatialReference': {'wkid': 4326}})
    base = dict(where=where, geometry=G, geometryType='esriGeometryEnvelope', inSR=4326, spatialRel='esriSpatialRelIntersects', f='json')
    for attempt in range(6):
        try: ids = requests.get(OSM, params=dict(base, returnIdsOnly='true'), timeout=120).json()['objectIds']; break
        except Exception: time.sleep(5 * (attempt + 1))
    else: raise RuntimeError('could not list the paths')
    def chunk(c):
        p = dict(objectIds=','.join(map(str, c)), outSR=4326, outFields='osm_id,name,highway,service,footway,bicycle,foot,access,bridge,tunnel,layer', returnGeometry='true', f='json')
        for _ in range(4):
            try:
                r = requests.post(OSM, data=p, timeout=120).json()
                if 'features' in r: return r['features']
            except Exception as e: err = e
            time.sleep(3)
        raise RuntimeError('fetch failed')
    out = []
    with cf.ThreadPoolExecutor(6) as ex:
        for b in ex.map(chunk, [ids[i:i + 500] for i in range(0, len(ids), 500)]): out += b
    print('paths listed', len(ids), '| fetched', len(out))
    return out

def main():
    t0 = time.time(); text = (ROOT / 'index.html').read_text()
    m = re.search(r'(<script id="net-data" type="application/json">)(.*?)(</script>)', text, flags=re.S); N = json.loads(m.group(2))
    if 'lnk' in N: sys.exit('Path links are already in this page; rebuild from a page without them.')
    P0 = len(N['pu']); OUT = N.get('out') or [0] * P0
    nodes = np.array([T(x, y) for x, y in dec(N['nodes'])]); NN0 = len(nodes); ntree = cKDTree(nodes)
    city = Polygon([T(x, y) for x, y in dec(N['boundary'][0])])
    area = Polygon([T(x, y) for x, y in dec(N['region'][0])]) if N.get('region') else city
    lines = [np.array([T(x, y) for x, y in dec(g)]) for g in N['geom']]
    # every network piece sampled every 3 m, to tell what's already there and where a link meets a piece
    sx, sy, sk = [], [], []
    for k, L in enumerate(lines):
        for i in range(len(L) - 1):
            a, b = L[i], L[i + 1]; n = max(1, int(math.hypot(*(b - a)) / 3))
            for j in range(n): f = j / n; sx.append(a[0] + (b[0] - a[0]) * f); sy.append(a[1] + (b[1] - a[1]) * f); sk.append(k)
        sx.append(L[-1][0]); sy.append(L[-1][1]); sk.append(k)
    stree = cKDTree(np.c_[sx, sy]); sk = np.array(sk)
    lay = np.array([N['lay'][k] for k in range(P0)]); flat = lay[sk] == 0
    stree0 = cKDTree(np.c_[sx, sy][flat]); sk0 = sk[flat]          # ground-level pieces only, for joining links
    road = np.array([N['inf'][k] <= 1 for k in range(P0)])
    bb = [TI(*c) for c in (area.bounds[:2], area.bounds[2:])]; bbox = (bb[0][0], bb[0][1], bb[1][0], bb[1][1])
    feats = fetch(bbox); print('OpenStreetMap paths in the area', len(feats), f'{time.time() - t0:.0f} s')
    cand = []
    for f in feats:
        a = f['attributes']; low = lambda k: str(a.get(k) or '').lower()
        if low('footway') in ('sidewalk', 'crossing', 'traffic_island', 'access_aisle'): continue   # pavements and road crossings
        if low('access') in ('private', 'no') or low('bicycle') == 'no': continue
        if a.get('highway') == 'service' and low('service') == 'driveway': continue   # private driveways
        for path in (f.get('geometry') or {}).get('paths', []):
            c = np.array([T(x, y) for x, y in path])
            if len(c) < 2: continue
            ls = LineString(c)
            if ls.length < 3 or not area.intersects(ls): continue
            samp = np.array([ls.interpolate(d).coords[0] for d in np.arange(0, ls.length + 0.1, 4)])
            d, i = stree.query(samp)
            if (d <= 4).mean() >= 0.6: continue                                   # already in the network
            near_road = road[sk[i]] & (d <= 10)
            if a.get('highway') == 'footway' and ls.length > 30 and near_road.mean() >= 0.7 and low('bridge') in ('', 'none', 'no'): continue  # a pavement by another name
            cand.append(dict(c=c, hw=a.get('highway'), nm=a.get('name') or '', br=low('bridge') not in ('', 'none', 'no'), tn=low('tunnel') not in ('', 'none', 'no')))
    print('candidate links', len(cand), f'{time.time() - t0:.0f} s')
    # junctions: vertices shared between candidates, network nodes they touch, and points where they meet a piece
    key = lambda p: (round(p[0], 1), round(p[1], 1)); cnt = defaultdict(int)
    for w in cand:
        for p in set(key(p) for p in w['c']): cnt[p] += 1
    attach = {}        # vertex key -> ('n', node) or ('p', piece, point)
    for w in cand:
        for p in w['c']:
            kp = key(p)
            if kp in attach: continue
            dn, jn = ntree.query(p)
            if dn <= 1.5: attach[kp] = ('n', int(jn)); continue
            ds, js = stree0.query(p)
            if ds <= 1.5: attach[kp] = ('p', int(sk0[js]), (float(p[0]), float(p[1])))
    # a path that stops at the edge of a road, where the pavement (left out) would take you on, joins the road there
    nsnap = 0
    for w in cand:
        for end in (0, -1):
            p = w['c'][end]; kp = key(p)
            if kp in attach or cnt[kp] > 1: continue
            ds, js = stree0.query(p)
            if ds <= 12:
                k = int(sk0[js]); q = LineString(lines[k]).interpolate(LineString(lines[k]).project(Point(p))).coords[0]
                c = w['c']; w['c'] = np.vstack([c, q]) if end == -1 else np.vstack([q, c])
                attach[key(q)] = ('p', k, (float(q[0]), float(q[1]))); nsnap += 1
    print('path ends joined to the road beside them', nsnap)
    # the same for paths already in the network that stop just short of a road (the pavement between is left out)
    degn = defaultdict(int); inc1 = {}
    for k in range(P0):
        for n in (N['pu'][k], N['pv'][k]): degn[n] += 1; inc1[n] = k
    nstub = 0
    for n, d in degn.items():
        k0 = inc1[n]
        if d != 1 or N['inf'][k0] < 2: continue
        p = nodes[n]; dd, jj = stree0.query(p, k=12)
        for ds, js in zip(dd, jj):
            k = int(sk0[js])
            if k == k0 or ds > 15 or ds < 0.5: continue
            q = LineString(lines[k]).interpolate(LineString(lines[k]).project(Point(p))).coords[0]
            cand.append(dict(c=np.array([p, q]), hw='footway', nm='', br=False, tn=False))
            attach[key(p)] = ('n', int(n)); attach[key(q)] = ('p', k, (float(q[0]), float(q[1]))); nstub += 1
            break
    print('paths in the network joined to the road just beyond their end', nstub)
    segs = []
    for w in cand:
        c = w['c']; s = 0
        for j in range(1, len(c)):
            kp = key(c[j])
            if j == len(c) - 1 or cnt[kp] > 1 or kp in attach:
                if j > s: segs.append(dict(w=w, c=c[s:j + 1]))
                s = j
    # prune dead ends until only links that join something remain
    alive = [True] * len(segs)
    while True:
        deg = defaultdict(int)
        for i, sg in enumerate(segs):
            if alive[i]: deg[key(sg['c'][0])] += 1; deg[key(sg['c'][-1])] += 1
        drop = 0
        for i, sg in enumerate(segs):
            if not alive[i]: continue
            a, b = key(sg['c'][0]), key(sg['c'][-1])
            if (deg[a] == 1 and a not in attach) or (deg[b] == 1 and b not in attach) or a == b: alive[i] = False; drop += 1
        if not drop: break
    segs = [s for i, s in enumerate(segs) if alive[i]]
    # a connected group of links must touch the network in at least two places, or it leads nowhere new
    par = {}
    def fnd(a):
        while par.setdefault(a, a) != a: par[a] = par[par[a]]; a = par[a]
        return a
    for sg in segs: par[fnd(key(sg['c'][0]))] = fnd(key(sg['c'][-1]))
    touch = defaultdict(set)
    for sg in segs:
        for e in (key(sg['c'][0]), key(sg['c'][-1])):
            if e in attach: touch[fnd(e)].add(attach[e][:2])
    segs = [sg for sg in segs if len(touch[fnd(key(sg['c'][0]))]) >= 2]
    # car-park and yard lanes only where they lead out of a dead end (the end of Kelvinside Avenue to Maryhill Road,
    # say): a group made only of such lanes, touching no dead end, is a way through a car park and adds little
    deg0 = defaultdict(int)
    for k in range(P0):
        for n in (N['pu'][k], N['pv'][k]): deg0[n] += 1
    allsvc = defaultdict(lambda: True); dead = defaultdict(bool)
    for sg in segs:
        r = fnd(key(sg['c'][0])); allsvc[r] = allsvc[r] and sg['w']['hw'] == 'service'
        for e in (key(sg['c'][0]), key(sg['c'][-1])):
            a = attach.get(e)
            if a and a[0] == 'n' and deg0[a[1]] == 1: dead[r] = True
    segs = [sg for sg in segs if not allsvc[fnd(key(sg['c'][0]))] or dead[fnd(key(sg['c'][0]))]]
    # keep a group of links only where it is a real shortcut: some pair of the places it joins is at least 100 m and
    # half as far again further apart by the network than through the links (a way into a dead end counts: the
    # network can't reach it at all)
    import networkx as nx
    G = nx.Graph()
    for k in range(P0):
        u, v, l = N['pu'][k], N['pv'][k], N['lens'][k]
        if not G.has_edge(u, v) or G[u][v]['w'] > l: G.add_edge(u, v, w=l)
    def anchor(a):   # a junction to measure from: the node, or the nearer end of the piece joined part-way
        if a[0] == 'n': return a[1], 0.0
        L = LineString(lines[a[1]]); d = L.project(Point(a[2]))
        return (N['pu'][a[1]], d) if d <= L.length / 2 else (N['pv'][a[1]], L.length - d)
    groups = defaultdict(list)
    for sg in segs: groups[fnd(key(sg['c'][0]))].append(sg)
    keepE = set(); tested = 0; kept_groups = 0
    for r, gs in groups.items():
        H = nx.Graph(); ats = {}
        for sg in gs:
            a, b = key(sg['c'][0]), key(sg['c'][-1]); l = LineString(sg['c']).length
            if not H.has_edge(a, b) or H[a][b]['w'] > l: H.add_edge(a, b, w=l)
            for e in (a, b):
                if e in attach: ats[e] = anchor(attach[e])
        if len(ats) < 2: continue
        keys = list(ats)[:60]; got = False
        for i, ka in enumerate(keys):
            dl, paths = nx.single_source_dijkstra(H, ka, weight='w')
            na, oa = ats[ka]; far = max((dl.get(kb, 0) for kb in keys[i + 1:]), default=0)
            if not far: continue
            dn = nx.single_source_dijkstra_path_length(G, na, cutoff=1.5 * far + 300 + oa, weight='w') if na in G else {}
            for kb in keys[i + 1:]:
                if kb not in dl: continue
                nb, ob = ats[kb]; net = dn.get(nb, float('inf')) + oa + ob; tested += 1
                if net > 1.5 * dl[kb] + 100 and net - dl[kb] > 100:   # a shortcut: keep just the links along it
                    pth = paths[kb]; got = True
                    for x, y in zip(pth, pth[1:]): keepE.add((x, y)); keepE.add((y, x))
        kept_groups += got
    segs = [sg for sg in segs if (key(sg['c'][0]), key(sg['c'][-1])) in keepE]
    print('shortcut test:', len(groups), 'groups,', kept_groups, 'with a shortcut;', tested, 'pairs measured')
    print('links kept', len(segs), '| km', round(sum(LineString(s['c']).length for s in segs) / 1000, 1), f'{time.time() - t0:.0f} s')
    # nodes for the new junctions; pieces split where links meet them
    new_nodes = []; vnode = {}
    for kp, a in list(attach.items()):
        if a[0] != 'p': continue
        L = LineString(lines[a[1]]); d = L.project(Point(a[2]))
        if d <= 20: attach[kp] = ('n', N['pu'][a[1]])
        elif L.length - d <= 20: attach[kp] = ('n', N['pv'][a[1]])
    def node_at(kp, p):
        if kp in vnode: return vnode[kp]
        a = attach.get(kp)
        if a and a[0] == 'n': vnode[kp] = a[1]; return a[1]
        vnode[kp] = NN0 + len(new_nodes); new_nodes.append((float(p[0]), float(p[1]))); return vnode[kp]
    splits = defaultdict(list)    # piece -> [(distance along, node)]
    rows = []
    for sg in segs:
        c = sg['c']; u = node_at(key(c[0]), c[0]); v = node_at(key(c[-1]), c[-1])
        for kp, p, n in ((key(c[0]), c[0], u), (key(c[-1]), c[-1], v)):
            a = attach.get(kp)
            if a and a[0] == 'p': splits[a[1]].append((LineString(lines[a[1]]).project(Point(p)), n))
        if u != v: rows.append((sg, u, v))
    out = {f: [] for f in ('pu', 'pv', 'los', 'rated', 'inf', 'spd', 'vol', 'nm', 'cn', 'way', 'geom', 'lens', 'phard', 'pdz', 'ow', 'qow', 'bpd', 'lay', 'out', 'stp')}
    names = list(N['names']); nidx = {n: i for i, n in enumerate(names)}
    def name_i(n):
        if n not in nidx: nidx[n] = len(names); names.append(n)
        return nidx[n]
    def add(u, v, coords, **a):
        ll = [TI(x, y) for x, y in coords]; ls = LineString(ll); s = ls.simplify(0.00002) if len(ll) > 2 else ls
        out['pu'].append(u); out['pv'].append(v); out['geom'].append(enc(s.coords)); out['lens'].append(max(1, int(round(LineString(coords).length))))
        for f in ('los', 'rated', 'inf', 'spd', 'vol', 'nm', 'cn', 'way', 'phard', 'pdz', 'ow', 'qow', 'bpd', 'lay', 'out', 'stp'): out[f].append(a[f])
    for i, (sg, u, v) in enumerate(rows):
        c = sg['c']
        if u < NN0 and math.dist(c[0], nodes[u]) > 0.5: c = np.vstack([nodes[u], c])
        if v < NN0 and math.dist(c[-1], nodes[v]) > 0.5: c = np.vstack([c, nodes[v]])
        sg['c'] = c
    for sg, u, v in rows:
        w = sg['w']; mid = LineString(sg['c']).interpolate(0.5, normalized=True)
        add(u, v, sg['c'], los=0 if w['hw'] != 'service' else 1, rated=0, inf=4 if w['hw'] == 'cycleway' else (0 if w['hw'] == 'service' else 5), spd=0, vol=-1, nm=name_i(w['nm']), cn=-1, way=-1, phard=0, pdz=-1,
            ow=0, qow=0, bpd=0, lay=1 if w['br'] else (-1 if w['tn'] else 0), out=0 if city.contains(mid) else 1, stp=1 if w['hw'] == 'steps' else 0)
    nsplit = 0
    for k, pts in splits.items():
        L = LineString(lines[k]); pts = sorted(set((round(d, 2), n) for d, n in pts if 0.5 < d < L.length - 0.5))
        if not pts: continue
        cuts = [(0.0, N['pu'][k])] + list(pts) + [(L.length, N['pv'][k])]
        for (d0, n0), (d1, n1) in zip(cuts, cuts[1:]):
            if n0 == n1 or d1 - d0 < 0.3: continue
            seg = [L.interpolate(d0).coords[0]] + [c for c in L.coords if d0 < L.project(Point(c)) < d1] + [L.interpolate(d1).coords[0]]
            add(n0, n1, seg, los=N['los'][k], rated=N['rated'][k], inf=N['inf'][k], spd=N['spd'][k], vol=N['vol'][k], nm=N['nm'][k], cn=-1, way=-1,
                phard=N['phard'][k], pdz=-1, ow=N['ow'][k], qow=N['qow'][k], bpd=0, lay=N['lay'][k], out=OUT[k], stp=0); nsplit += 1
    P1 = len(out['pu']); NNn = NN0 + len(new_nodes)
    hardn = list(N['hard']) + [0] * len(new_nodes); inc = defaultdict(int); incg = defaultdict(int)
    for i in range(P1):
        for n in (out['pu'][i], out['pv'][i]):
            if out['phard'][i]: hardn[n] = 1
            inc[n] += 1; incg[n] += 1 if out['lay'][i] else 0
    gsn = list(N['gs']) + [int(inc[n] > 0 and incg[n] == inc[n]) for n in range(NN0, NNn)]; gstn = list(N['gst']) + [int(incg[n] > 0) for n in range(NN0, NNn)]
    for f in ('pu', 'pv', 'los', 'rated', 'inf', 'spd', 'vol', 'nm', 'cn', 'way', 'geom', 'lens', 'phard', 'pdz', 'ow', 'qow', 'bpd', 'lay'): N[f] = list(N[f]) + out[f]
    N['out'] = list(OUT) + out['out']; N['lnk'] = [0] * P0 + [1] * len(rows) + [2] * nsplit;  # 1 a path link, 2 a routing-only copy of part of a street or path
    N['stp'] = [0] * P0 + out['stp']
    N['names'] = names; N['hard'] = hardn; N['gs'] = gsn; N['gst'] = gstn; N['signal'] = list(N['signal']) + [0] * len(new_nodes)
    N['nodes'] = enc(dec(N['nodes']) + [TI(*p) for p in new_nodes])
    N['linkInfo'] = dict(baseNodes=NN0, links=len(rows), steps=sum(out['stp']), split_parts=nsplit, source='OpenStreetMap footways, paths, steps and footbridges (ODbL), routing only')
    s = json.dumps(N, separators=(',', ':'), ensure_ascii=False).replace('<', '\\u003c')
    (ROOT / 'index.html').write_text(text[:m.start(2)] + s + text[m.end(2):])
    print(f'added {len(rows)} links ({sum(out["stp"])} of them steps) and {nsplit} split parts; {len(new_nodes)} new junctions | network blob {len(s) / 1e6:.1f} MB | {time.time() - t0:.0f} s')

if __name__ == '__main__':
    main()
