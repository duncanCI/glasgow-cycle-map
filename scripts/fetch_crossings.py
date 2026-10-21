"""Gather evidence of road crossings for Glasgow into data/crossings.json.

Two sources:
  * OpenStreetMap, through the Overpass API: crossing nodes (highway=crossing, crossing=*, crossing_ref=*),
    signal nodes that carry a crossing, and crossing ways (footway=crossing, cycleway=crossing).
  * Glasgow City Council's signal sites in the city centre (CCTP tactile facilities layer), which lists
    pelican, toucan and pedex crossings and signalled junctions with pedestrian phases.

Each point is written as [lon, lat, type] with type:
  s  signal-controlled (traffic_signals, pelican, puffin, toucan, pegasus, or a council signal site)
  z  zebra or marked crossing
  u  uncontrolled or unmarked crossing point (dropped kerbs, an island)
  n  explicitly no crossing here (crossing=no)

The weekly GitHub Action runs this; if a source fails, the previous file's points from that source are kept.
"""
import json, sys, time, urllib.parse, urllib.request
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / 'data' / 'crossings.json'
S, W, N, E = 55.78, -4.40, 55.93, -4.07
try:  # with the streets around Glasgow added (build_region.py), cover that area too
    import re as _re, json as _json
    _N = _json.loads(_re.search(r'<script id="net-data" type="application/json">(.*?)</script>', open(Path(__file__).resolve().parent.parent / 'index.html').read(), flags=_re.S).group(1))
    if _N.get('region'):
        _a = _N['region'][0]; _x = _y = 0; _pts = []
        for _i in range(0, len(_a), 2): _x += _a[_i]; _y += _a[_i + 1]; _pts.append((_x / 1e5, _y / 1e5))
        W, E = min(p[0] for p in _pts), max(p[0] for p in _pts); S, N = min(p[1] for p in _pts), max(p[1] for p in _pts)
except Exception as _e:
    print('staying with the city box:', _e)
OVERPASS = ['https://overpass-api.de/api/interpreter', 'https://overpass.kumi.systems/api/interpreter']
COUNCIL = ('https://services2.arcgis.com/Ne8d9gKn5SJ3eAaw/arcgis/rest/services/MyMapService_1/FeatureServer/0/query'
           '?where=1%3D1&outFields=SITETYPE,TYPESUMMAR,SITELOCATI&outSR=4326&f=json')
UA = {'User-Agent': 'glasgow-cycle-map (github.com/duncanCI/glasgow-cycle-map)'}


def get(url, data=None, timeout=180):
    req = urllib.request.Request(url, data=data, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode('utf-8'))


def kind(tags):
    c = (tags.get('crossing') or '').lower()
    ref = (tags.get('crossing_ref') or '').lower()
    if c == 'no':
        return 'n'
    if c in ('traffic_signals', 'pelican', 'puffin', 'toucan', 'pegasus') or ref in ('pelican', 'puffin', 'toucan', 'pegasus', 'tiger') \
            or tags.get('highway') == 'traffic_signals' or tags.get('crossing:signals') == 'yes':
        return 's'
    if c in ('zebra', 'marked') or ref == 'zebra' or tags.get('crossing:markings') not in (None, 'no'):
        return 'z'
    return 'u'


def from_osm():
    bb = f'({S},{W},{N},{E})'
    q = f"""[out:json][timeout:170];
(
  node["highway"="crossing"]{bb};
  node["crossing"]{bb};
  node["highway"="traffic_signals"]["crossing"]{bb};
  way["footway"="crossing"]{bb};
  way["cycleway"="crossing"]{bb};
);
out center tags;"""
    last = None
    for url in OVERPASS:
        try:
            j = get(url, urllib.parse.urlencode({'data': q}).encode())
            pts = []
            for el in j.get('elements', []):
                lat = el.get('lat') or (el.get('center') or {}).get('lat')
                lon = el.get('lon') or (el.get('center') or {}).get('lon')
                if lat is None or lon is None:
                    continue
                pts.append([round(lon, 6), round(lat, 6), kind(el.get('tags') or {})])
            return pts
        except Exception as e:  # try the next mirror
            last = e
            time.sleep(5)
    raise RuntimeError(f'Overpass failed: {last}')


def from_council():
    j = get(COUNCIL, timeout=60)
    pts = []
    for f in j.get('features', []):
        a, g = f.get('attributes') or {}, f.get('geometry') or {}
        if 'x' not in g:
            continue
        if (a.get('TYPESUMMAR') or '').lower().startswith('no ped'):
            continue  # a signalled junction with no pedestrian phase
        pts.append([round(g['x'], 6), round(g['y'], 6), 's'])
    return pts


def main():
    prev = {}
    if OUT.exists():
        try:
            prev = json.loads(OUT.read_text())
        except Exception:
            prev = {}
    out = {'generated': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), 'sources': {}}
    for name, fn in (('osm', from_osm), ('council', from_council)):
        try:
            out[name] = fn()
            out['sources'][name] = 'ok'
        except Exception as e:
            out[name] = prev.get(name, [])
            out['sources'][name] = f'kept previous ({e.__class__.__name__})'
        print(name, len(out[name]), out['sources'][name])
    OUT.write_text(json.dumps(out, separators=(',', ':')))


if __name__ == '__main__':
    sys.exit(main())
