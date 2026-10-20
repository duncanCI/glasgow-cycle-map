"""Build the virtual cycle's music library from Kevin MacLeod's incompetech catalogue (Creative Commons BY 4.0).

Reads the public catalogue (https://incompetech.com/music/royalty-free/pieces.json), picks a handful of tracks for
each style, downloads them into music/<style>/, and writes data/music.json with titles, files and the credit line the
licence asks for. Re-running only downloads what is missing. If ffmpeg is installed, tracks are re-encoded to 96 kbps
so the library stays small.

    python3 scripts/fetch_music.py            # build or top up the library
    python3 scripts/fetch_music.py --list     # just show what would be picked
"""
import json, re, shutil, subprocess, sys, time, urllib.parse, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASE = 'https://incompetech.com/music/royalty-free/'
UA = {'User-Agent': 'glasgow-cycle-map music fetch (github.com/duncanCI/glasgow-cycle-map)'}
PER_STYLE = 4

# for each style: titles that suit it well, then words to look for anywhere in a piece's details as a fallback
STYLES = {
    'lofi': ('Lo-fi and chilled beats', ['Lobby Time', 'Airport Lounge', 'Wallpaper', 'Backbay Lounge', 'Easy Lemon', 'Bossa Antigua', 'Smooth Lovin', 'Local Forecast - Elevator'],
             ['chill', 'lounge', 'mellow', 'laid back', 'relaxed', 'smooth', 'lo-fi', 'lofi', 'hip hop', 'downtempo']),
    'reggae': ('Reggae and ska', ['Island Meet and Greet', 'Jah Rasta', 'Reggae Banana', 'Ska Cuba'], ['reggae', 'ska', 'dub', 'island', 'jamaica', 'calypso', 'caribbean']),
    'country': ('Country and bluegrass', ['Hillbilly Swing', 'Cattails', 'Dances and Dames', 'Hot Pursuit', 'Fiddles McGinty'], ['country', 'bluegrass', 'banjo', 'hillbilly', 'western', 'americana', 'fiddle', 'cowboy']),
    'celtic': ('Celtic', ['Achaidh Cheide', 'Celtic Impulse', 'Thatched Villagers', 'Master of the Feast', 'Pippin the Hunchback', 'Folk Round'], ['celtic', 'irish', 'scottish', 'gaelic', 'jig', 'reel', 'bagpipe', 'highland']),
    'classical': ('Classical', ['Gymnopedie No 1', 'Canon in D Major', 'Danse Macabre', 'Prelude and Action', 'String Impromptu Number 1'], ['classical', 'baroque', 'string quartet', 'piano solo', 'orchestral', 'waltz']),
    'synthwave': ('Synthwave and retro', ['Eighties Action', 'Night Vigil', 'Neon Laser Horizon', 'Disco con Tutti'], ['synthwave', 'synth', 'eighties', '80s', 'retro synth']),
    'chip': ('8-bit', ['8bit Dungeon Boss', '8bit Dungeon Level', 'Pixel Peeker Polka - faster', 'Pixelland'], ['8bit', '8-bit', 'chiptune', 'chip', 'video game', 'pixel', 'retro game']),
    'metal': ('Rage metal', ['Volatile Reaction', 'Movement Proposition', 'Ready Aim Fire', 'Ghost Dance'], ['metal', 'heavy', 'thrash', 'hard rock', 'aggressive', 'distorted', 'shred']),
}


def get(url, binary=False, timeout=60):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = r.read()
    return data if binary else json.loads(data.decode('utf-8', 'replace'))


def as_list(v):
    if v is None:
        return []
    if isinstance(v, (list, tuple)):
        return [str(x) for x in v]
    return [str(v)]


def seconds(v):
    if v is None:
        return 0
    if isinstance(v, (int, float)):
        return float(v)
    parts = [float(p) for p in re.findall(r'\d+(?:\.\d+)?', str(v))]
    total = 0.0
    for p in parts:
        total = total * 60 + p
    return total


def blob(p, genres):
    fields = []
    for k in ('title', 'description', 'feel', 'instruments', 'collection', 'collections', 'genre', 'genres', 'tags', 'mood'):
        for x in as_list(p.get(k)):
            fields.append(genres.get(x, x))
    return ' '.join(fields).lower()


def file_for(p):
    for k in ('filename', 'file', 'mp3', 'url'):
        v = p.get(k)
        if v:
            v = str(v)
            if v.startswith('http'):
                return v
            if not v.lower().endswith('.mp3'):
                v += '.mp3'
            return BASE + 'mp3-royaltyfree/' + urllib.parse.quote(v)
    return BASE + 'mp3-royaltyfree/' + urllib.parse.quote(str(p.get('title', '')) + '.mp3')


def slug(s):
    return re.sub(r'[^a-z0-9]+', '-', s.lower()).strip('-')[:60] or 'track'


def main():
    only_list = '--list' in sys.argv
    pieces = get(BASE + 'pieces.json')
    if isinstance(pieces, dict):
        pieces = pieces.get('pieces') or pieces.get('data') or list(pieces.values())
    genres = {}
    try:
        g = get(BASE + 'genre.json')
        if isinstance(g, dict):
            genres = {str(k): str(v if not isinstance(v, dict) else v.get('name', k)) for k, v in g.items()}
        elif isinstance(g, list):
            for x in g:
                if isinstance(x, dict):
                    genres[str(x.get('id', x.get('key', '')))] = str(x.get('name', x.get('title', '')))
    except Exception:
        pass
    print('catalogue pieces', len(pieces))
    by_title = {str(p.get('title', '')).strip().lower(): p for p in pieces if isinstance(p, dict)}
    used, picks = set(), {}
    # first every style takes its named favourites, then each tops up from the catalogue by keyword
    for style, (label, titles, words) in STYLES.items():
        chosen = []
        for t in titles:
            p = by_title.get(t.lower())
            if p and id(p) not in used and len(chosen) < PER_STYLE:
                chosen.append(p); used.add(id(p))
        picks[style] = (label, chosen)
    for style, (label, titles, words) in STYLES.items():
        chosen = picks[style][1]
        if len(chosen) < PER_STYLE:
            scored = []
            for p in pieces:
                if not isinstance(p, dict) or id(p) in used:
                    continue
                L = seconds(p.get('length') or p.get('duration'))
                if L and not (75 <= L <= 420):
                    continue
                text = blob(p, genres)
                score = sum(text.count(w) for w in words)
                if score:
                    scored.append((score, str(p.get('title', '')), p))
            scored.sort(key=lambda x: (-x[0], x[1]))
            for _, _, p in scored:
                if len(chosen) >= PER_STYLE:
                    break
                chosen.append(p); used.add(id(p))
        print(f'{style:10s}', ' | '.join(str(p.get("title")) for p in chosen) or '(nothing found)')
    if only_list:
        return 0
    have_ffmpeg = shutil.which('ffmpeg') is not None
    out = {'generated': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), 'artist': 'Kevin MacLeod', 'source': 'https://incompetech.com',
           'licence': 'Creative Commons: By Attribution 4.0', 'licence_url': 'https://creativecommons.org/licenses/by/4.0/', 'styles': {}}
    for style, (label, chosen) in picks.items():
        folder = ROOT / 'music' / style
        folder.mkdir(parents=True, exist_ok=True)
        tracks = []
        for p in chosen:
            title = str(p.get('title', 'Untitled'))
            dest = folder / (slug(title) + '.mp3')
            if not dest.exists():
                try:
                    data = get(file_for(p), binary=True, timeout=120)
                    if len(data) < 50000:
                        raise ValueError('file too small')
                    tmp = dest.with_suffix('.src.mp3'); tmp.write_bytes(data)
                    if have_ffmpeg:
                        r = subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', str(tmp), '-codec:a', 'libmp3lame', '-b:a', '96k', str(dest)])
                        if r.returncode != 0:
                            tmp.rename(dest)
                        else:
                            tmp.unlink()
                    else:
                        tmp.rename(dest)
                    print('  downloaded', style, title, round(dest.stat().st_size / 1e6, 1), 'MB')
                    time.sleep(1)
                except Exception as e:
                    print('  could not fetch', title, '-', e.__class__.__name__)
                    continue
            tracks.append({'title': title, 'file': f'music/{style}/{dest.name}', 'length': seconds(p.get('length') or p.get('duration')),
                           'credit': f'"{title}" Kevin MacLeod (incompetech.com), licensed under Creative Commons: By Attribution 4.0'})
        if tracks:
            out['styles'][style] = {'label': label, 'tracks': tracks}
    (ROOT / 'data').mkdir(exist_ok=True)
    (ROOT / 'data' / 'music.json').write_text(json.dumps(out, indent=1))
    total = sum(f.stat().st_size for f in (ROOT / 'music').rglob('*.mp3'))
    print('styles', len(out['styles']), '| tracks', sum(len(s['tracks']) for s in out['styles'].values()), '| library', round(total / 1e6, 1), 'MB')
    return 0


if __name__ == '__main__':
    sys.exit(main())
