"""Bike collisions around Glasgow, from the Department for Transport's national STATS19 road safety data.

Glasgow's own collisions come from the council's extract of the same data (2016 to 2023) and are built into the
network. This adds the collisions in the area around the city that the map now routes over (out to about 8 km, the
faint dotted line), for the same years, so routes that leave the city count them too. Like Glasgow's, they count
along a route and show on the map; unlike Glasgow's, there is no cycle-flow data outside the city yet, so they don't
feed the collision-risk weighting.

Source: https://www.gov.uk/government/statistical-data-sets/road-safety-open-data (Open Government Licence v3.0).
The 1979-to-latest files are streamed and filtered on the fly (they are large: about 1.4 GB of collisions and 1.6 GB
of vehicles), so this runs on GitHub Actions ("Fetch the collisions around Glasgow") rather than in a browser.

    python3 scripts/fetch_collisions_region.py [first_year last_year]
"""
import csv, io, json, re, sys, time, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASE = 'https://data.dft.gov.uk/road-accidents-safety-data/'
FILES = {'collision': 'dft-road-casualty-statistics-collision-1979-latest-published-year.csv',
         'vehicle': 'dft-road-casualty-statistics-vehicle-1979-latest-published-year.csv'}
UA = {'User-Agent': 'glasgow-cycle-map (github.com/duncanCI/glasgow-cycle-map)'}

def page_net():
    t = (ROOT / 'index.html').read_text()
    return json.loads(re.search(r'<script id="net-data" type="application/json">(.*?)</script>', t, flags=re.S).group(1))

def ring(enc):
    out = []; x = y = 0
    for i in range(0, len(enc), 2): x += enc[i]; y += enc[i + 1]; out.append((x / 1e5, y / 1e5))
    return out

def inside(poly, x, y):
    c = False; j = len(poly) - 1
    for i in range(len(poly)):
        xi, yi = poly[i]; xj, yj = poly[j]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi: c = not c
        j = i
    return c

def rows(name):
    req = urllib.request.Request(BASE + FILES[name], headers=UA)
    with urllib.request.urlopen(req, timeout=300) as r:
        yield from csv.DictReader(io.TextIOWrapper(r, encoding='utf-8-sig', newline=''))

def col(row, *names):
    for n in names:
        if n in row: return row[n]
    raise KeyError(names)

def main():
    y0, y1 = (int(sys.argv[1]), int(sys.argv[2])) if len(sys.argv) > 2 else (2016, 2023)  # the same years as Glasgow's
    N = page_net()
    if not N.get('region'): sys.exit('The page has no surrounding area yet (scripts/build_region.py).')
    city, region = ring(N['boundary'][0]), ring(N['region'][0])
    xs = [p[0] for p in region]; ys = [p[1] for p in region]; W, E, S, Nn = min(xs), max(xs), min(ys), max(ys)
    t0 = time.time(); found = {}
    for r in rows('collision'):
        try:
            yr = int(col(r, 'collision_year', 'accident_year')); lon = float(r['longitude']); lat = float(r['latitude'])
        except (ValueError, KeyError):
            continue
        if not (y0 <= yr <= y1 and W <= lon <= E and S <= lat <= Nn): continue
        if not inside(region, lon, lat) or inside(city, lon, lat): continue  # Glasgow's own come from the council's file
        sev = {'1': 3, '2': 2, '3': 1}.get(col(r, 'collision_severity', 'accident_severity'), 1)   # stored as 1 slight, 2 serious, 3 fatal
        found[col(r, 'collision_index', 'accident_index')] = (lon, lat, sev, yr)
    print('collisions around the city', len(found), f'{time.time() - t0:.0f} s')
    bikes = set()
    for r in rows('vehicle'):
        k = r.get('collision_index') or r.get('accident_index')
        if k in found and r.get('vehicle_type') == '1': bikes.add(k)   # 1 = pedal cycle
    print('with a bike involved', len(bikes), f'{time.time() - t0:.0f} s')
    c = []
    for k in sorted(bikes):
        lon, lat, sev, yr = found[k]; c += [round(lon * 1e5), round(lat * 1e5), sev, yr - 2000]
    out = dict(years=[y0, y1], n=len(bikes), c=c, source='DfT STATS19 road safety open data, collisions with a pedal cycle involved',
               credit='Department for Transport, Open Government Licence v3.0')
    (ROOT / 'data' / 'collisions-region.json').write_text(json.dumps(out, separators=(',', ':')))
    print('written data/collisions-region.json')

if __name__ == '__main__':
    main()
