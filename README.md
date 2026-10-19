# How far is protected cycling from your door?

An interactive map of Glasgow's protected cycle network. It shows how far every street is from segregated or off-road cycle track, how much of that track joins up, and what the council's 2032 programme and full City Network plan would change.

With the default settings, 14% of Glasgow's 621,020 residents live in neighbourhoods mostly within 800 m riding of the main protected network. 79% are within 800 m of some protected track, but the city's 148 km of track sits in 183 separate pieces, and 149 of them are under 1 km long.

## Publish on GitHub Pages

The site is one static file, `index.html`, so no build step is needed.

**In the browser.** Create a new public repository called `glasgow-cycle-map`, upload every file in this folder, then open Settings, Pages, and set the source to "Deploy from a branch" with `main` and `/ (root)`.

**From the command line**, with the [GitHub CLI](https://cli.github.com/) signed in:

```sh
cd glasgow-cycle-map
git init -b main
git add .
git commit -m "First version of the Glasgow protected cycle network map"
gh repo create glasgow-cycle-map --public --source . --remote origin --push
gh api -X POST "repos/{owner}/{repo}/pages" -f "source[branch]=main" -f "source[path]=/"
```

The site appears at `https://<your-username>.github.io/glasgow-cycle-map/` once the first Pages build finishes, usually in about 2 minutes.

## Reports

The "Report a problem here" button opens a pre-filled GitHub issue in this repository, with the street, coordinates and a satellite link. The page works out the repository from its GitHub Pages address. On a custom domain, set it in the `<meta name="github-repo">` tag in `index.html`, for example `content="your-username/glasgow-cycle-map"`.

Reports show on the map once they are added to `reports.geojson`:

```json
{
  "type": "Feature",
  "geometry": { "type": "Point", "coordinates": [-4.3385, 55.8845] },
  "properties": { "kind": "parked", "note": "Cars along the kerb most evenings", "date": "2026-10-15" }
}
```

`kind` is one of `parked`, `crossing`, `traffic`, `gap` or `good`. The FixMyStreet button sends a report to Glasgow City Council and needs no GitHub account.

## Method

Protected infrastructure is every way that the Network Planning Tool for Scotland classes as segregated cycle track (wide or narrow) or off-road cycleway. Shared pavements can be added with a checkbox. Painted lanes are left out because nothing stops cars parking in them.

Protected sections join where they share a junction in OpenStreetMap. Gaps count as joined when the unprotected riding across them is within the chosen limit: none, 100 m (default) or 250 m. The main network is the largest joined-up set. Distances to it follow the street network.

A neighbourhood is one of Glasgow's 746 data zones. It counts as within 800 m when at least half of its street length is within 800 m riding of the main network. The 800 m figure comes from the council's Active Travel Strategy, which measures it to any segregated infrastructure. This map measures it to the main network, so a cut-off fragment does not count.

The 2032 programme is approximate. In June 2026 the council approved Connecting Glasgow, which prioritises about 54 km of routes for 2032 and keeps the 270 km City Network as a longer-term aim. This map matches the council's published list of sections to its route data by street name, giving 57 km, 49 km of it not yet built. Planned routes count as protected once built and join the junctions they pass within 35 m.

## Limits

The joined-up network depends on how crossings are mapped in OpenStreetMap. A track that stops at a junction and resumes across it looks split unless the link is mapped. Switching the gap limit from none to 250 m moves the headline from 9% to 21%. Fixing the mapping in OpenStreetMap and rebuilding the data is the way to correct it.

Traffic figures in the traffic stress view are model estimates from the Network Planning Tool, not counts.

## Data sources and licences

| Data | Source | Licence |
| --- | --- | --- |
| Street network, infrastructure type, traffic stress, modelled traffic | Network Planning Tool for Scotland, May 2025 release, derived from OpenStreetMap | ODbL 1.0 |
| Street names and speed limits | OpenStreetMap, via Esri's OpenStreetMap Highways for Europe service, October 2026 | © OpenStreetMap contributors, ODbL 1.0 |
| Signal crossings, rivers and canals | OpenStreetMap via Esri, October 2026 | © OpenStreetMap contributors, ODbL 1.0 |
| City Network routes, stages and constraints | Glasgow City Council Active Travel Strategy routes service, October 2026 | Check with the council before reuse |
| City boundary | Glasgow City Council | Check with the council before reuse |
| Data zones, population, deprivation decile | Network Planning Tool data zones file, from National Records of Scotland and the Scottish Index of Multiple Deprivation 2020 | Open Government Licence v3.0 |
| Background map | OpenStreetMap standard tiles, shown in greyscale | © OpenStreetMap contributors, used under the OpenStreetMap tile usage policy |

The network data embedded in `index.html` is a derived database of OpenStreetMap and is published under the [Open Database Licence 1.0](https://opendatacommons.org/licenses/odbl/1-0/). The code is MIT licensed (see `LICENSE`).

## Rebuilding the data

The scripts in `scripts/` rebuild the embedded data. They are prototype quality. See `scripts/README.md` for the order and inputs.
