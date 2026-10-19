# How far is protected cycling from your door?

An interactive map of Glasgow's protected cycle network. It shows how far every street is from segregated or off-road cycle track, how much of that track joins up, and what the council's 2032 programme and full City Network plan would change.

With the default settings, 43% of Glasgow's 621,020 residents live in neighbourhoods mostly within 800 m riding of the main protected network. That includes 50 km of protected track from a community-maintained map of routes built since the May 2025 data, which on its own gives 14%. 92% of residents are within 800 m of some protected track, but much of it sits in fragments that join nothing bigger.

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

## One-way streets, contraflow and dead ends

Distances to the network follow one-way streets as mapped in OpenStreetMap, in both directions, and the longer of the ride there and the ride back counts. Only 53 streets in Glasgow are mapped with contraflow cycling, which leaves 95 km of quiet one-way streets that bikes can use in one direction only.

Two options test what that costs. "Reach the network without riding on busy roads" limits the ride to the network to protected track and streets rated High or Medium, as a family with young children would ride. "What if cycling were allowed both ways on quiet one-way streets" opens those 95 km to two-way cycling. With both switched on, about 10,000 more residents come within 800 m of the main protected network.

"Possible missing links" marks 165 residential dead ends that come within 25 m of another street or path, at a similar height, with no mapped way between them within 400 m of riding. A dropped kerb or a filtered gap could join many of them, but some are walls, fences, private land or unmapped paths, so they are shown for checking on the ground and not counted in the figures. Both ideas come from the observations of the community map's author, u/Correct-Audience-421.

## Bridges, steps and blocked links

Community-mapped lines join the street network within 20 m of their ends and 15 m along their length, and never to a road on a bridge or in a tunnel unless the two genuinely meet within 6 m, so a riverside path such as the Kelvin Walkway is not joined to the bridge above it. Planned routes are joined only to junctions at street level. Steps are not part of the network.

Some links still won't be rideable: steps the data misses, kissing gates, or barriers that block cargo bikes and trailers. Reports of the kind "Steps or a barrier, not rideable" open as GitHub issues. To act on one, add the spot to `data/blocked.json`:

```json
{ "points": [ { "lat": 55.8752, "lng": -4.2795, "radius": 15, "note": "Steps down to the Kelvin Walkway at Kelvinbridge" } ] }
```

Every street, path or community-map link within the radius (in metres, default 15) is removed from the network and the route planner the next time the page loads.

## Route planner

Right-click the map, or press and hold on a phone, and choose "Route from here" and "Route to here". The route follows the network for the selected scenario, so the same trip can be compared today and under the plans. Drag the A and B pins to move them, and right-click again to add stops, which can also be dragged or removed.

Each route shows its length and riding time, the share on protected track, the climb and the steepest 100 m, the junctions passed and the busy-road crossings or turns, and a breakdown of what you ride on. A height profile follows the route on the map as you move along it. "Download GPX for Strava" saves a file that Strava's route builder imports (Create route, then the upload button), and "Open in Google Maps" passes the start, end, stops and a few points along the route to Google's cycling directions.

"Most protected", the default, weights each street by traffic stress: protected track at its true length, quiet streets at 1.8 times and busy streets at up to 6 times. "Balanced" uses 1.2 and 4 times, and "Most direct" takes the shortest legal route. The height profile is pinned to the bottom of the map whenever a route is shown. Click the route line to add a stop, then drag it. Riding time assumes 16 km/h on the flat (13 km/h on shared pavements), adjusted for gradient, plus 8 seconds per busy-road crossing or turn and 12 seconds per mapped signal. The planner follows one-way streets as mapped in OpenStreetMap, which may miss some contraflow cycling permissions.

## Community map and the weekly refresh

Routes built since May 2025 come from [Glasgow Cycle Map: Now and Future](https://www.google.com/maps/d/viewer?mid=1DSSERLE1fpX9_ze779MfZS4d3KctbV0), a Google My Map maintained by [u/Correct-Audience-421](https://www.reddit.com/user/Correct-Audience-421/) and used with their permission. Thank you.

`.github/workflows/community-refresh.yml` runs `scripts/community.py` every Monday at 06:00 UTC. It downloads the map, writes `data/community.geojson` and `data/community-meta.json`, embeds the lines in `index.html`, commits, and asks GitHub Pages to rebuild. It refuses a download that looks broken, for example one with less than half the previous built length, and the page keeps the last good copy. To run it by hand, open the Actions tab, choose the workflow and select "Run workflow".

The script reads the map's line colours: dark green and dark teal are built, mint is under construction or being upgraded, amber is planned and dark grey is a quiet street. Built lines become protected paths in the network, sampled every 25 m and joined to street junctions within 20 m. Built lines described as shared pavements count only when shared pavements are switched on. Under-construction lines join the 2032 and full-plan scenarios.

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
| Routes built since May 2025 | Glasgow Cycle Map: Now and Future, by u/Correct-Audience-421, refreshed weekly | Used with the author's permission |
| Heights | Mapzen Terrain Tiles on AWS Open Data, from SRTM in Scotland, resampled to about 37 m | Open data, attribution to Mapzen and SRTM (NASA) |
| Background map | OpenStreetMap standard tiles, shown in greyscale | © OpenStreetMap contributors, used under the OpenStreetMap tile usage policy |

The network data embedded in `index.html` is a derived database of OpenStreetMap and is published under the [Open Database Licence 1.0](https://opendatacommons.org/licenses/odbl/1-0/). The code is MIT licensed (see `LICENSE`).

## Rebuilding the data

The scripts in `scripts/` rebuild the embedded data. They are prototype quality. See `scripts/README.md` for the order and inputs.
