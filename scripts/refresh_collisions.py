"""Rebuild every bike collision on the map from the Department for Transport's national STATS19 road safety data.

Replaces the earlier Glasgow City Council extract (2016 to 2023, with a gap in 2019) with the national files, from
2016 to the latest published year, for Glasgow and the area around it the map routes over. Rebuilds, inside
index.html: the collisions on each street (N.crp), the collision points (N.crash), Glasgow's hotspots (N.hot), each
Glasgow street's collision risk against the cycling it carries (N.rr, using the modelled cycling already on each
street, N.bpd) and a summary the About tab reads (N.crashInfo). Matching is as before: the nearest street within
25 m, preferring the carriageway when a track runs alongside. Hotspots and risk stay Glasgow's own, since there is
no cycle-flow data outside the city.

Source: https://www.gov.uk/government/statistical-data-sets/road-safety-open-data (Open Government Licence v3.0).
The 1979-to-latest files are big (about 1.4 GB of collisions, 1.6 GB of vehicles) and are streamed and filtered on
the fly, so this runs on GitHub Actions ("Refresh collisions from the national data").

    python3 scripts/refresh_collisions.py [first_year [last_year]]
    STATS19_DIR=folder python3 scripts/refresh_collisions.py    # read local copies of the two CSV files instead
"""
import collections, csv, io, json, os, re, sys, time, urllib.request
from pathlib import Path
import numpy as np, pyproj
from scipy.spatial import cKDTree
from shapely.geometry import LineString, Point, Polygon

ROOT = Path(__file__).resolve().parent.parent
BASE = 'https://data.dft.gov.uk/road-accidents-safety-data/'
FILES = {'collision': 'dft-road-casualty-statistics-collision-1979-latest-published-year.csv',
         'vehicle': 'dft-road-casualty-statistics-vehicle-1979-latest-published-year.csv'}
UA = {'User-Agent': 'glasgow-cycle-map (github.com/duncanCI/glasgow-cycle-map)'}
W = {1: 1, 2: 3, 3: 6}   # slight, serious, fatal
T = pyproj.Transformer.from_crs(4326, 27700, always_xy=True).transform

def dec(a):
    out = []; x = y = 0
    for i in range(0, len(a), 2): x += a[i]; y += a[i + 1]; out.append((x / 1e5, y / 1e5))
    return out

def rows(kind):
    local = os.environ.get('STATS19_DIR')
    if local:
        with open(Path(local) / FILES[kind], encoding='utf-8-sig', newline='') as f: yield from csv.DictReader(f)
        return
    with urllib.request.urlopen(urllib.request.Request(BASE + FILES[kind], headers=UA), timeout=300) as r:
        yield from csv.DictReader(io.TextIOWrapper(r, encoding='utf-8-sig', newline=''))

def col(r, *names):
    for n in names:
        if n in r: return r[n]
    raise KeyError(names)

def main():
    t0 = time.time(); page = (ROOT / 'index.html').read_text()
    m = re.search(r'(<script id="net-data" type="application/json">)(.*?)(</script>)', page, flags=re.S); N = json.loads(m.group(2))
    P = len(N['pu']); OUT = N.get('out') or [0] * P
    city = Polygon(dec(N['boundary'][0])); area = Polygon(dec(N['region'][0])) if N.get('region') else city
    W0, S0, E0, N0 = area.bounds
    y0 = int(sys.argv[1]) if len(sys.argv) > 1 else 2016; y1 = int(sys.argv[2]) if len(sys.argv) > 2 else 9999
    found = {}
    for r in rows('collision'):
        try: yr = int(col(r, 'collision_year', 'accident_year')); lon = float(r['longitude']); lat = float(r['latitude'])
        except (ValueError, KeyError): continue
        if not (y0 <= yr <= y1 and W0 <= lon <= E0 and S0 <= lat <= N0): continue
        pt = Point(lon, lat)
        if not area.contains(pt): continue
        sev = {'1': 3, '2': 2, '3': 1}.get(col(r, 'collision_severity', 'accident_severity'), 1)
        found[col(r, 'collision_index', 'accident_index')] = (lon, lat, sev, yr, city.contains(pt))
    print('collisions in the area', len(found), f'{time.time() - t0:.0f} s')
    bikes = set()
    for r in rows('vehicle'):
        k = r.get('collision_index') or r.get('accident_index')
        if k in found and r.get('vehicle_type') == '1': bikes.add(k)
    C = [found[k] for k in sorted(bikes)]
    years = sorted({c[3] for c in C}); print('bike collisions', len(C), '| years', years[:1], 'to', years[-1:], f'{time.time() - t0:.0f} s')
    # match to the nearest street within 25 m, preferring the carriageway; the city's to city streets, the rest to the rest
    lines = [LineString([T(x, y) for x, y in dec(g)]) for g in N['geom']]
    mids = np.array([l.interpolate(0.5, normalized=True).coords[0] for l in lines]); tree = cKDTree(mids)
    road = [N['inf'][k] in (0, 1) for k in range(P)]
    def match(lon, lat, in_city):
        e, n = T(lon, lat); pt = Point(e, n); best = None
        for k in tree.query_ball_point((e, n), 400):
            if bool(OUT[k]) == in_city: continue
            d = lines[k].distance(pt)
            if d > 25: continue
            sc = d - (5 if road[k] else 0)
            if best is None or sc < best[0]: best = (sc, k)
        return best[1] if best else -1
    piece = [match(c[0], c[1], c[4]) for c in C]
    agg = collections.defaultdict(lambda: [0, 0, 0])
    for k, c in zip(piece, C):
        if k >= 0: agg[k][c[2] - 1] += 1
    N['crp'] = [x for k, v in sorted(agg.items()) for x in (k, *v)]
    N['crash'] = [x for c in C for x in (round(c[0] * 1e5), round(c[1] * 1e5), c[2], c[3] - 2000)]
    # Glasgow's hotspots: at least 4 bike collisions within 50 m, greedily from the densest
    ci = [i for i, c in enumerate(C) if c[4]]; xy = np.array([T(C[i][0], C[i][1]) for i in ci]); ct = cKDTree(xy)
    nb = [ct.query_ball_point(p, 50) for p in xy]; wv = np.array([W[C[i][2]] for i in ci])
    order = sorted(range(len(ci)), key=lambda j: (-len(nb[j]), -wv[nb[j]].sum())); used = np.zeros(len(ci), bool); hot = []
    for j in order:
        mm = [q for q in nb[j] if not used[q]]
        if len(mm) < 4: continue
        used[mm] = True; sub = [C[ci[q]] for q in mm]; ks = sum(1 for c in sub if c[2] >= 2)
        nm = collections.Counter(N['names'][N['nm'][piece[ci[q]]]] for q in mm if piece[ci[q]] >= 0 and N['names'][N['nm'][piece[ci[q]]]])
        hot.append(dict(lat=round(float(np.mean([c[1] for c in sub])), 5), lng=round(float(np.mean([c[0] for c in sub])), 5), n=len(mm), ksi=ks,
                        f=sum(1 for c in sub if c[2] == 3), nm=' and '.join(x for x, _ in nm.most_common(2))))
    hot.sort(key=lambda h: (-h['n'], -h['ksi']))
    # risk against the cycling each Glasgow street carries (N.bpd: modelled bikes a day, already floored)
    E = np.array([max(1, v) for v in N['bpd']], float); cityk = np.array([not o for o in OUT])
    w = np.zeros(P)
    for k, v in agg.items(): w[k] = v[0] + 3 * v[1] + 6 * v[2]
    rbar = w[cityk].sum() / E[cityk].sum(); RR = (w + 1) / (rbar * E + 1)
    N['rr'] = [x for k in np.where((w > 0) & cityk)[0] for x in (int(k), round(float(RR[k]), 2))]
    cx, cy = mids[:, 0], mids[:, 1]
    for h in hot:
        x, y = T(h['lng'], h['lat']); near = np.where((np.hypot(cx - x, cy - y) < 50) & cityk)[0]
        eb = E[near].sum() / 2 if len(near) else 1; hw = h['n'] - h['ksi'] + 3 * (h['ksi'] - h['f']) + 6 * h['f']
        h['bpd'] = int(round(eb)); h['rr'] = round(float((hw + 1) / (rbar * eb + 1)), 1)
    N['hot'] = hot
    cnt = lambda sel: dict(n=len(sel), slight=sum(1 for c in sel if c[2] == 1), serious=sum(1 for c in sel if c[2] == 2), fatal=sum(1 for c in sel if c[2] == 3))
    N['crashInfo'] = dict(y0=years[0] if years else y0, y1=years[-1] if years else y1, city=cnt([c for c in C if c[4]]), area=cnt([c for c in C if not c[4]]),
                          source='DfT STATS19 road safety open data (national), collisions with a pedal cycle involved', credit='Department for Transport, Open Government Licence v3.0')
    s = json.dumps(N, separators=(',', ':'), ensure_ascii=False).replace('<', '\\u003c')
    page = page[:m.start(2)] + s + page[m.end(2):]
    (ROOT / 'index.html').write_text(page)
    old = ROOT / 'data' / 'collisions-region.json'
    if old.exists(): old.unlink()   # now built into the page
    ci_ = N['crashInfo']; print('Glasgow', ci_['city'], '| around it', ci_['area'], '| hotspots', len(hot), '| worst', hot[0]['nm'] if hot else '-', f'| {time.time() - t0:.0f} s')

if __name__ == '__main__':
    main()
