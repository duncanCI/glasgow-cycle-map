"""Fetch the community "Glasgow Cycle Map - Now & Future" (Google My Maps, by u/Correct-Audience-421,
used with permission) and embed it in index.html.

Standard library only, so it runs on a plain GitHub Actions runner.
Usage: python3 scripts/community.py            (download from Google)
       python3 scripts/community.py --input x.kml   (use a local copy)
"""
import argparse, datetime, hashlib, html, json, math, re, sys, urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

MID = "1DSSERLE1fpX9_ze779MfZS4d3KctbV0"
URL = f"https://www.google.com/maps/d/kml?mid={MID}&forcekml=1"
VIEWER = f"https://www.google.com/maps/d/viewer?mid={MID}"
ROOT = Path(__file__).resolve().parent.parent
NS = {"k": "http://www.opengis.net/kml/2.2"}
# line colours used on the community map, mapped to a status
# dark green = built protected, dark teal = traffic-free links, mint = under construction or being upgraded,
# amber = planned, dark grey = quiet streets; anything else (such as light grey) stays unclassified
STATUS = {"097138": "built", "006064": "built", "87CEAC": "progress", "F9A825": "planned", "757575": "quiet"}

def load(args):
    if args.input:
        return Path(args.input).read_bytes()
    req = urllib.request.Request(URL, headers={"User-Agent": "glasgow-cycle-map weekly refresh (GitHub Actions)"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()

def metres(a, b):
    lat = math.radians((a[1] + b[1]) / 2)
    return math.hypot((b[0] - a[0]) * math.cos(lat) * 111320, (b[1] - a[1]) * 110540)

def simplify(pts, tol=2.5):
    """Douglas-Peucker in metres on a local plane."""
    if len(pts) < 3:
        return pts
    lat0 = math.radians(pts[0][1]); kx = math.cos(lat0) * 111320; ky = 110540
    P = [((x - pts[0][0]) * kx, (y - pts[0][1]) * ky) for x, y in pts]
    keep = [False] * len(P); keep[0] = keep[-1] = True; stack = [(0, len(P) - 1)]
    while stack:
        i, j = stack.pop(); ax, ay = P[i]; bx, by = P[j]; dx, dy = bx - ax, by - ay; L = dx * dx + dy * dy
        best, bi = 0, -1
        for k in range(i + 1, j):
            px, py = P[k]
            t = ((px - ax) * dx + (py - ay) * dy) / L if L else 0; t = max(0, min(1, t))
            d = math.hypot(ax + t * dx - px, ay + t * dy - py)
            if d > best: best, bi = d, k
        if best > tol:
            keep[bi] = True; stack += [(i, bi), (bi, j)]
    return [p for p, k in zip(pts, keep) if k]

def encode(pts):
    out, px, py = [], 0, 0
    for x, y in pts:
        X, Y = round(x * 1e5), round(y * 1e5); out += [X - px, Y - py]; px, py = X, Y
    return out

def clean(text):
    if not text:
        return ""
    text = re.sub(r"<br\s*/?>", " | ", text); text = re.sub(r"<[^>]+>", "", text)
    text = html.unescape(text).replace("\xa0", " ")
    return re.sub(r"\s+", " ", text).strip(" |")[:300]

def parse(raw):
    doc = ET.fromstring(raw).find("k:Document", NS)
    feats, km = [], {}
    for folder in doc.findall("k:Folder", NS):
        fname = folder.findtext("k:name", namespaces=NS) or ""
        for pm in folder.findall(".//k:Placemark", NS):
            ls = pm.find(".//k:LineString", NS)
            if ls is None:
                continue
            m = re.match(r"#line-([0-9A-Fa-f]{6})", pm.findtext("k:styleUrl", namespaces=NS) or "")
            colour = m.group(1).upper() if m else ""
            status = STATUS.get(colour, "other")
            if fname.lower().startswith("scrapped"):
                status = "onhold"
            pts = [tuple(map(float, c.split(",")[:2])) for c in (ls.findtext("k:coordinates", namespaces=NS) or "").split()]
            if len(pts) < 2:
                continue
            desc = clean(pm.findtext("k:description", namespaces=NS))
            length = sum(metres(a, b) for a, b in zip(pts, pts[1:]))
            km[status] = km.get(status, 0) + length / 1000
            feats.append({"n": clean(pm.findtext("k:name", namespaces=NS))[:120], "fo": fname, "s": status, "c": colour,
                          "sh": 1 if (status == "built" and "shared pavement" in desc.lower()) else 0,
                          "d": desc, "g": encode(simplify(pts))})
    return feats, {k: round(v, 1) for k, v in km.items()}

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--input"); args = ap.parse_args()
    feats, km = parse(load(args))
    meta_path = ROOT / "data" / "community-meta.json"
    old = json.loads(meta_path.read_text()) if meta_path.exists() else {}
    # refuse a refresh that looks broken, so the page keeps the last good copy
    if len(feats) < 200 or km.get("built", 0) < 50:
        sys.exit(f"Community map looks wrong ({len(feats)} lines, {km.get('built', 0)} km built); keeping the last good copy.")
    if old.get("km", {}).get("built") and km["built"] < 0.5 * old["km"]["built"]:
        sys.exit(f"Built length fell from {old['km']['built']} km to {km['built']} km; keeping the last good copy.")
    body = json.dumps(feats, separators=(",", ":"), ensure_ascii=False)
    digest = hashlib.sha256(body.encode()).hexdigest()
    today = datetime.date.today().isoformat()
    meta = {"checked": today, "changed": today if digest != old.get("sha256") else old.get("changed", today),
            "sha256": digest, "lines": len(feats), "km": km, "source": VIEWER,
            "credit": "Glasgow Cycle Map - Now & Future, by u/Correct-Audience-421, used with permission"}
    (ROOT / "data").mkdir(exist_ok=True)
    meta_path.write_text(json.dumps(meta, indent=2) + "\n")
    geo = {"type": "FeatureCollection", "features": [
        {"type": "Feature", "properties": {k: f[k] for k in ("n", "fo", "s", "c", "sh", "d")},
         "geometry": {"type": "LineString", "coordinates": decode(f["g"])}} for f in feats]}
    (ROOT / "data" / "community.geojson").write_text(json.dumps(geo, separators=(",", ":"), ensure_ascii=False))
    page = ROOT / "index.html"; text = page.read_text()
    blob = json.dumps({"meta": {k: meta[k] for k in ("checked", "changed", "lines", "km", "source", "credit")}, "f": feats},
                      separators=(",", ":"), ensure_ascii=False).replace("</", "<\\/")
    new, n = re.subn(r'(<script id="comm-data" type="application/json">).*?(</script>)', lambda m: m.group(1) + blob + m.group(2), text, flags=re.S)
    if n != 1:
        sys.exit("Could not find the comm-data block in index.html.")
    page.write_text(new)
    print(f"{len(feats)} lines; km by status {km}; checked {meta['checked']}, changed {meta['changed']}")

def decode(a):
    out, x, y = [], 0, 0
    for i in range(0, len(a), 2):
        x += a[i]; y += a[i + 1]; out.append([round(x / 1e5, 5), round(y / 1e5, 5)])
    return out

if __name__ == "__main__":
    main()
