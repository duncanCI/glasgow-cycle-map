"""Heights for the streets around Glasgow (the 8 km ring added by build_region.py), on a 30 m grid.

Glasgow keeps its 10 m LiDAR grid (prep_lidar.py); this coarser grid covers the surrounding area so routes that leave
the city still get climbs and profiles. Source: Scottish Public Sector LiDAR bare-earth models (Phases 5, 6, 3 and 4)
read at their 16 m overview, with the global terrain tiles (Mapzen terrarium, zoom 12) filling anywhere the LiDAR
doesn't reach. Licence: Open Government Licence v3.0 (LiDAR).

Writes data/relief-region.bin and data/relief-region.json, in the same encoding as data/relief.json.

    python3 scripts/prep_lidar_region.py
"""
import os
if os.path.exists('/etc/ssl/certs/ca-certificates.crt'):
    os.environ.setdefault('CURL_CA_BUNDLE', '/etc/ssl/certs/ca-certificates.crt'); os.environ.setdefault('GDAL_CURL_CA_BUNDLE', '/etc/ssl/certs/ca-certificates.crt')
import gzip, io, json, math, re, time
from pathlib import Path
import numpy as np, rasterio, requests
from PIL import Image
from pyproj import Transformer
from scipy.ndimage import map_coordinates, binary_dilation
from matplotlib.path import Path as MPath
import importlib.util
spec = importlib.util.spec_from_file_location('pl', Path(__file__).with_name('prep_lidar.py')); pl = importlib.util.module_from_spec(spec); spec.loader.exec_module(pl)

ROOT = Path(__file__).resolve().parent.parent
DX, DY = 0.0005, 0.00028          # about 31 m by 31 m
OFF, SCALE = 20.0, 10.0

def terrarium(lons, lats, z=12):
    """Global terrain tiles for cells the LiDAR misses."""
    n = 2 ** z; fx = (lons + 180) / 360 * n; fy = (1 - np.log(np.tan(np.radians(lats)) + 1 / np.cos(np.radians(lats))) / math.pi) / 2 * n
    tx0, tx1, ty0, ty1 = int(fx.min()), int(fx.max()), int(fy.min()), int(fy.max())
    M = np.zeros(((ty1 - ty0 + 1) * 256, (tx1 - tx0 + 1) * 256))
    for tx in range(tx0, tx1 + 1):
        for ty in range(ty0, ty1 + 1):
            r = requests.get(f'https://elevation-tiles-prod.s3.us-east-1.amazonaws.com/terrarium/{z}/{tx}/{ty}.png', timeout=60); r.raise_for_status()
            a = np.asarray(Image.open(io.BytesIO(r.content)).convert('RGB')).astype(np.float64)
            M[(ty - ty0) * 256:(ty - ty0 + 1) * 256, (tx - tx0) * 256:(tx - tx0 + 1) * 256] = a[..., 0] * 256 + a[..., 1] + a[..., 2] / 256 - 32768
    return map_coordinates(M, [(fy - ty0) * 256 - 0.5, (fx - tx0) * 256 - 0.5], order=1, mode='nearest')

def main():
    t0 = time.time(); text = (ROOT / 'index.html').read_text(); N = pl.page_blob(text, 'net-data')
    if 'region' not in N: raise SystemExit('Run build_region.py first.')
    ring = pl.dec(N['region'][0]); X0, Y0 = float(ring[:, 0].min()) - DX, float(ring[:, 1].min()) - DY; X1, Y1 = float(ring[:, 0].max()) + DX, float(ring[:, 1].max()) + DY
    lons = np.arange(X0, X1 + 1e-12, DX); lats = np.arange(Y0, Y1 + 1e-12, DY); nx, ny = len(lons), len(lats)
    LO, LA = np.meshgrid(lons, lats); T = Transformer.from_crs(4326, 27700, always_xy=True); E, Nn = T.transform(LO, LA)
    Z = np.full(LO.shape, np.nan); box = (E.min(), Nn.min(), E.max(), Nn.max()); print('grid', nx, 'x', ny)
    with rasterio.Env(**pl.ENV):
        for name, (e0, n0, e1, n1) in pl.quarters(box):
            sel = (E >= e0) & (E < e1) & (Nn >= n0) & (Nn < n1)
            if not sel.any(): continue
            got = []
            for ph in pl.PHASES:
                url = f'{pl.BUCKET}{ph}/dtm/27700/gridded/{name}_50CM_DTM_{ph.upper().replace("-", "")}.tif'
                try:
                    with rasterio.open(url, overview_level=4) as d:   # the 16 m overview
                        a = d.read(1).astype(np.float64); tr = d.transform; a[(a <= -1000) | (a == d.nodata)] = np.nan
                except Exception:
                    continue
                v = map_coordinates(a, [(Nn[sel] - tr.f) / tr.e - 0.5, (E[sel] - tr.c) / tr.a - 0.5], order=1, mode='constant', cval=np.nan)
                cur = Z[sel]; fill = np.isnan(cur) & ~np.isnan(v); cur[fill] = v[fill]; Z[sel] = cur; got.append(ph)
                if not np.isnan(Z[sel]).any(): break
            print(f'  {name}: {",".join(got) or "no LiDAR"} | {time.time() - t0:.0f} s')
    coarse = terrarium(LO, LA)
    bad = np.isnan(Z) | (np.abs(Z - coarse) > 60); print('cells from the global terrain tiles', f'{100 * bad.mean():.1f}%'); Z[bad] = coarse[bad]
    pts = np.c_[LO.ravel(), LA.ravel()]
    inside = binary_dilation(MPath(ring).contains_points(pts).reshape(LO.shape), iterations=3)
    water = np.zeros(LO.shape, bool)
    for w in N['water']: water |= MPath(pl.dec(w)).contains_points(pts).reshape(LO.shape)
    q = np.clip(np.round((Z + OFF) * SCALE), 2, 65535).astype(np.uint16); q[water] = 1; q[~inside] = 0
    d = q.copy(); d[:, 1:] = (q[:, 1:].astype(np.int64) - q[:, :-1].astype(np.int64)) % 65536
    blob = gzip.compress(d.astype('<u2').tobytes(), 9, mtime=0); (ROOT / 'data' / 'relief-region.bin').write_bytes(blob)
    meta = dict(x0=X0, y0=Y0, dx=DX, dy=DY, nx=nx, ny=ny, off=OFF, scale=SCALE, none=0, water=1, coding='gzip, row deltas mod 65536, uint16 little-endian',
                source='Scottish Public Sector LiDAR DTM (Phases 5, 6, 3, 4) at its 16 m overview, gaps from Mapzen terrarium tiles', credit='Crown copyright Scottish Government and Fugro, Open Government Licence v3.0')
    (ROOT / 'data' / 'relief-region.json').write_text(json.dumps(meta, indent=1))
    for nm, lo, la in [('Paisley Abbey', -4.4235, 55.8453), ('Clydebank', -4.405, 55.901), ('Bearsden Cross', -4.333, 55.918), ('East Kilbride centre', -4.177, 55.764), ('Hamilton', -4.04, 55.777)]:
        i = int(round((la - Y0) / DY)); j = int(round((lo - X0) / DX)); print(f'  {nm}: {Z[i, j]:.1f} m')
    print('relief-region.bin', round(len(blob) / 1e6, 2), 'MB', f'| {time.time() - t0:.0f} s')

if __name__ == '__main__':
    main()
