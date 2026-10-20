"""Build the map's relief from the Scottish Public Sector LiDAR (bare-earth Digital Terrain Model).

Why: the previous heights came from global terrain tiles (SRTM / EU-DEM, about 30 m, which see some buildings and
trees). Glasgow's short, steep streets vanish at that resolution. The Scottish Government's LiDAR is a 50 cm
bare-earth model of the ground itself, so road gradients come out right and nothing above the ground (bridges,
buildings, trees) is mistaken for a hill.

Source: Scottish Public Sector LiDAR Phase 5 DTM (50 cm), with Phases 6, 3 and 4 filling any gaps, read straight
from the open copy on AWS (s3://srsp-open-data, Cloud Optimised GeoTIFFs) at its 4 m overview.
Licence: Open Government Licence v3.0. Attribution: Crown copyright Scottish Government and Fugro (2021).

Writes:
  data/relief.bin   10 m grid over the city, gzip of row-delta uint16 heights (0 = none, 1 = water)
  data/relief.json  the grid's extent and encoding
and refreshes the small 38 m grid embedded in index.html (elev-data), so profiles improve before the 10 m grid loads.

    python3 scripts/prep_lidar.py
"""
import os
if os.path.exists('/etc/ssl/certs/ca-certificates.crt'):  # GDAL's own downloader needs the system certificates named
    os.environ.setdefault('CURL_CA_BUNDLE', '/etc/ssl/certs/ca-certificates.crt'); os.environ.setdefault('GDAL_CURL_CA_BUNDLE', '/etc/ssl/certs/ca-certificates.crt')
import base64, gzip, json, re, sys, time
from pathlib import Path
import numpy as np
import rasterio
from pyproj import Transformer
from scipy.ndimage import map_coordinates
from matplotlib.path import Path as MPath

ROOT = Path(__file__).resolve().parent.parent
BUCKET = '/vsicurl/https://srsp-open-data.s3.eu-west-2.amazonaws.com/lidar/'
PHASES = ['phase-5', 'phase-6', 'phase-3', 'phase-4']          # newest first; later ones fill gaps
X0, X1, Y0, Y1 = -4.40, -4.06, 55.775, 55.935                 # same box as the page's grid
DX, DY = 0.00016, 0.00009                                       # about 10 m by 10 m at Glasgow
OFF, SCALE = 20.0, 10.0                                         # stored value = (height + 20 m) x 10, so 0.1 m steps
NONE, WATER = 0, 1
ENV = dict(GDAL_DISABLE_READDIR_ON_OPEN='EMPTY_DIR', CPL_VSIL_CURL_ALLOWED_EXTENSIONS='.tif', GDAL_HTTP_MULTIRANGE='YES',
           GDAL_HTTP_MERGE_CONSECUTIVE_RANGES='YES', GDAL_HTTP_MAX_RETRY='4', GDAL_HTTP_RETRY_DELAY='2')

def page_blob(text, tag):
    m = re.search(r'<script id="%s" type="application/json">(.*?)</script>' % tag, text, flags=re.S)
    return json.loads(m.group(1))

def dec(a):
    out = []; x = y = 0
    for i in range(0, len(a), 2):
        x += a[i]; y += a[i + 1]; out.append((x / 1e5, y / 1e5))
    return np.array(out)

def quarters(osgb_box):
    """The 5 km quarter tiles (e.g. NS56NW) covering a British National Grid box."""
    e0, n0, e1, n1 = osgb_box; out = []
    for e in range(int(e0 // 5000) * 5000, int(e1) + 1, 5000):
        for n in range(int(n0 // 5000) * 5000, int(n1) + 1, 5000):
            sq = 'NS' + str((e - 200000) // 10000) + str((n - 600000) // 10000)
            q = ('N' if n % 10000 else 'S') + ('E' if e % 10000 else 'W')
            out.append((sq + q, (e, n, e + 5000, n + 5000)))
    return out

def main():
    t0 = time.time(); text = (ROOT / 'index.html').read_text()
    N = page_blob(text, 'net-data'); OLD = page_blob(text, 'elev-data')
    old = np.frombuffer(base64.b64decode(OLD['b64']), '<u2').astype(np.float64).reshape(OLD['ny'], OLD['nx']) / 10
    lons = np.arange(X0, X1 + 1e-12, DX); lats = np.arange(Y0, Y1 + 1e-12, DY); nx, ny = len(lons), len(lats)
    LO, LA = np.meshgrid(lons, lats); T = Transformer.from_crs(4326, 27700, always_xy=True)
    E, Nn = T.transform(LO, LA); Z = np.full(LO.shape, np.nan)
    box = (E.min(), Nn.min(), E.max(), Nn.max()); print('grid', nx, 'x', ny, '| OSGB box', [round(v) for v in box])
    with rasterio.Env(**ENV):
        for name, (e0, n0, e1, n1) in quarters(box):
            sel = (E >= e0) & (E < e1) & (Nn >= n0) & (Nn < n1)
            if not sel.any(): continue
            got = None
            for ph in PHASES:
                url = f'{BUCKET}{ph}/dtm/27700/gridded/{name}_50CM_DTM_{ph.upper().replace("-", "")}.tif'
                try:
                    with rasterio.open(url, overview_level=2) as d:   # the 4 m overview of the 50 cm model
                        a = d.read(1).astype(np.float64); tr = d.transform
                        a[(a <= -1000) | (a == d.nodata)] = np.nan
                except Exception as ex:
                    if 'not exist' not in str(ex) and '404' not in str(ex): print('   ', ph, name, str(ex)[:90])
                    continue
                cols = (E[sel] - tr.c) / tr.a - 0.5; rows = (Nn[sel] - tr.f) / tr.e - 0.5
                v = map_coordinates(a, [rows, cols], order=1, mode='constant', cval=np.nan)
                cur = Z[sel]; fill = np.isnan(cur) & ~np.isnan(v); cur[fill] = v[fill]; Z[sel] = cur
                got = (got or []) + [ph]
                if not np.isnan(Z[sel]).any(): break
            print(f'  {name}: {",".join(got) if got else "no LiDAR"} | {time.time() - t0:.0f} s')
    # gaps (rare: tile edges, water) and anything implausible fall back to the old terrain tiles
    oi = (LA - OLD['y0']) / OLD['dy']; oj = (LO - OLD['x0']) / OLD['dx']
    coarse = map_coordinates(old, [oi, oj], order=1, mode='nearest')
    bad = np.isnan(Z) | (np.abs(Z - coarse) > 40)
    print('cells filled from the old terrain tiles', int(bad.sum()), f'({100 * bad.mean():.2f}%)')
    Z[bad] = coarse[bad]
    # water: marked so the page bridges straight across it (a deck, not the river surface)
    water = np.zeros(LO.shape, bool); pts = np.c_[LO.ravel(), LA.ravel()]
    for ring in N['water']:
        water |= MPath(dec(ring)).contains_points(pts).reshape(LO.shape)
    # only the city (plus 400 m) is kept; the rest compresses to nothing
    inside = np.zeros(LO.shape, bool); kx, ky = 1 / (DX * 62600), 1 / (DY * 111200)
    for ring in N['boundary']:
        inside |= MPath(dec(ring)).contains_points(pts).reshape(LO.shape)
    from scipy.ndimage import binary_dilation
    inside = binary_dilation(inside, iterations=40)
    q = np.clip(np.round((Z + OFF) * SCALE), 2, 65535).astype(np.uint16)
    q[water] = WATER; q[~inside] = NONE
    d = q.copy(); d[:, 1:] = (q[:, 1:].astype(np.int64) - q[:, :-1].astype(np.int64)) % 65536
    blob = gzip.compress(d.astype('<u2').tobytes(), 9, mtime=0)
    (ROOT / 'data' / 'relief.bin').write_bytes(blob)
    meta = dict(x0=X0, y0=Y0, dx=DX, dy=DY, nx=nx, ny=ny, off=OFF, scale=SCALE, none=NONE, water=WATER, coding='gzip, row deltas mod 65536, uint16 little-endian',
                source='Scottish Public Sector LiDAR Phase 5 DTM (50 cm), gaps from Phases 6, 3 and 4, at its 4 m overview',
                credit='Crown copyright Scottish Government and Fugro (2021), Open Government Licence v3.0')
    (ROOT / 'data' / 'relief.json').write_text(json.dumps(meta, indent=1))
    print('relief.bin', round(len(blob) / 1e6, 2), 'MB')
    # the small embedded grid, now from LiDAR (block means of the 10 m grid)
    oj2 = (LO - X0) / DX; ok = inside & ~water
    sums = np.zeros((OLD['ny'], OLD['nx'])); cnt = np.zeros_like(sums)
    gi = np.clip(np.round((LA - OLD['y0']) / OLD['dy']).astype(int), 0, OLD['ny'] - 1); gj = np.clip(np.round((LO - OLD['x0']) / OLD['dx']).astype(int), 0, OLD['nx'] - 1)
    np.add.at(sums, (gi[ok], gj[ok]), Z[ok]); np.add.at(cnt, (gi[ok], gj[ok]), 1)
    newc = np.where(cnt > 0, sums / np.maximum(cnt, 1), old)
    OLD['b64'] = base64.b64encode(np.clip(np.round(newc * 10), 0, 65535).astype('<u2').tobytes()).decode()
    blob2 = json.dumps(OLD, separators=(',', ':'))
    text = re.sub(r'(<script id="elev-data" type="application/json">).*?(</script>)', lambda m: m.group(1) + blob2 + m.group(2), text, count=1, flags=re.S)
    (ROOT / 'index.html').write_text(text)
    # spot checks against well-known places
    for nm, lo, la in [('George Square', -4.2502, 55.8612), ('Park Circus', -4.2805, 55.8678), ('University tower', -4.2882, 55.8718), ('Gibson Street foot', -4.2830, 55.8735),
                       ('Southbrae Drive', -4.3385, 55.8845), ('Broomielaw', -4.2620, 55.8573), ('Cathkin Braes', -4.215, 55.795)]:
        i = int(round((la - Y0) / DY)); j = int(round((lo - X0) / DX)); print(f'  {nm}: LiDAR {Z[i, j]:.1f} m | old tiles {coarse[i, j]:.1f} m')
    print(f'done in {time.time() - t0:.0f} s')

if __name__ == '__main__':
    main()
