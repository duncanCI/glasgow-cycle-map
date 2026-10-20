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

## Using the map

The page opens on an example route, from the University of Glasgow to Queen's Park, which runs 84% on protected track. The side panel keeps search, sharing and a menu (help and theme) in a fixed header, with tabs for the overview, your route, the selected place, options and the method, and can be dragged wider or narrower by its edge, or folded away with the chevron on that edge (or by dragging it off) to give the map the whole window. Detail sits behind headings that open on demand: the figures behind the headline, the option groups, and each topic in the method. A "Layers" menu on the map switches the main layers on and off, and every layer in the key has its own "Hide" link. The network switch sits on the map itself, and the route's exports sit on the height profile, so nothing important needs a scroll. The map key folds away and remembers your choice, and a short tip greets first-time visitors.

The background map can be light grey, streets, cycling (CyclOSM), satellite or none, from the switch on the map or the Options tab, and the colour theme can follow the device or be set to light or dark. "Share" copies a link to exactly what is on screen: the view, network, options, layers, route, stops and selected street are all stored in the link, so anyone opening it sees the same thing. The address bar itself is left alone, so opening or reloading the page normally always starts from the example route, and "Reset to the starting view" in the More menu clears any saved layout.

## Bike collisions

The map includes the 828 personal-injury collisions involving a cyclist or a pedal cycle in Glasgow in the Department for Transport's STATS19 data, as published by Glasgow City Council for 2016 to 2023 (569 slight, 250 serious, 9 fatal). The council's file holds very few collisions for 2019, and only collisions reported to the police are recorded, so the counts understate the risk.

- **Hotspots** (on by default) ring the 20 places with at least 4 bike collisions within 50 m. The worst is Pollokshaws Toll, where Barrhead Road meets Pollokshaws Road: 13 collisions, 4 of them serious.
- **Every collision** can be shown by severity from the Options tab.
- **Clicking a street** shows its collisions, and those along the whole named street, plus any nearby hotspot.
- **Risk for the cycling a street carries.** Collision counts also follow how many people cycle somewhere, so each street and hotspot is set against its cycling: the Network Planning Tool's modelled daily flows, scaled to Glasgow City Council's automatic cycle counters (84 counters, counted flows a median 1.34 times the model, rank correlation 0.69). Pollokshaws Toll carries about 206 bikes a day and has about 17 times the city's average collision rate for that much cycling. Hotspot markers show this risk as a multiple of the city average (for example 17×), with the collision counts on hover.
- **Routes** count the recorded collisions on the streets they use. Protected track stays the main routing preference: with "Also steer away from unprotected streets with high collision risk" on (the default), only unprotected streets are penalised, by extra riding per unit of risk above the city average, from 300 m when riding with children down to none for very confident riders. A route never leaves protected track to avoid collisions.

## Route planner

Right-click the map, or press and hold on a phone, and choose "Route from here" and "Route to here". The route follows the network for the selected scenario, so the same trip can be compared today and under the plans. Drag the A and B pins to move them, and right-click again to add stops, which can also be dragged or removed.

Each route shows its length and riding time on the profile strip, with the network and rider confidence switchable right there. Hovering over the profile shows a colour-coded tooltip with the surface type, street, distance, height and gradient at that point. "Compare" opens a chart of the same trip across all four networks, or across all five confidence levels, with distance, time, share protected and recorded collisions side by side. "Share or export" groups the link, GPX and Google Maps options. Google Maps re-plans its own route between the points it is given and takes 10 points in all on the web (3 stops on mobile), so the link uses up to 7 stops, leaving one free so the route can still be edited in Google Maps, and places them where Google is most likely to stray: it compares this route with the shortest legal route between each pair of points and pins the middle of the longest stretch that differs, repeating until the waypoints run out. Opening it says roughly how much of the route Google should follow; for the exact route, use the GPX file in Strava, Komoot or a bike computer. The route card in the panel also shows the share on protected track, the climb and the steepest 100 m, the junctions passed and the busy-road crossings or turns, and a breakdown of what you ride on. A height profile follows the route on the map as you move along it. "Download GPX for Strava" saves a file that Strava's route builder imports (Create route, then the upload button), and "Open in Google Maps" passes the start, end, stops and a few points along the route to Google's cycling directions.

Routes follow a cyclist confidence slider with five levels, from "Riding with children" to "Very confident". The lowest level treats a quiet street as three times its length and a busy road as up to 25 times, adds 400 m for every busy road it joins or crosses from a calm street, and may run up to 2.5 times the shortest legal route to stay protected. "Cautious" is the default; "Very confident" takes the shortest legal route. A leg that would stretch beyond its level's limit steps up a level, and the profile says so. Riding speed rises from 11 km/h with children to 20 km/h. Stops stay where you put them, including side roads you want to call in on.

## Music for the virtual cycle

"Music for the ride", a button of its own at the top left of the map during a virtual cycle, opens one short list: lo-fi beats, reggae, country, Celtic, classical, synthwave, 8-bit and rage metal, plus a volume slider. Each plays inside the page from a library of Creative Commons tracks by Kevin MacLeod (incompetech.com, licensed under Creative Commons: By Attribution 4.0), shuffled, with a skip button. Until the library is in place, classical and synthwave fall back to live, ad-free radio (Radio Swiss Classic and Nightride FM).

The library lives in `music/` with its list in `data/music.json`, built by `scripts/fetch_music.py` from the public incompetech catalogue (about four tracks per style; re-encoded to 96 kbps when ffmpeg is available). Build or top it up from the Actions tab with "Fetch the music library", or run the script locally. Every track is credited, as the licence requires.

## Road crossings

Wherever the route leaves a path or shared pavement and crosses a road, the app records a road crossing: at a junction where a path meets the road on both sides, or where a community-mapped line is drawn straight across a carriageway between junctions. Each crossing is checked against `data/crossings.json`, which holds OpenStreetMap's crossing points (signals, toucans, zebras, marked and uncontrolled crossings, and places mapped as no crossing) and the council's city-centre signal sites. The weekly Action refreshes it with `scripts/fetch_crossings.py`.

Busy roads are marked on the map, on the height profile and in the street-by-street list: green at a mapped signal or zebra crossing, red for a busy road with no mapped crossing, and grey where a path meets a road of 40 mph or more, or one carriageway of a busy dual road, with nothing mapped to say a crossing exists. Those grey ones are often not crossable at all (barriers, central reservations), so routing treats them as an 800 m detour, and as 2.5 km where OpenStreetMap says there is no crossing. Community-map lines are also never joined to the street network across a carriageway. Levels matter too: every network piece carries its OpenStreetMap level (bridge, tunnel, underpass or layer), so a path passing over or under a road is not a crossing, and a community line that cuts across a road beside a bridge or underpass is treated as using it. Each crossing adds waiting time to the estimate (20 seconds for a busy road without a crossing, 15 at a crossing, 4 for a side road), and the virtual rider slows as it approaches one without a crossing.

NaPTAN is not used: it lists public transport stops and stations, not pedestrian or cycle crossings.

## Virtual cycle and Street View

"Virtual cycle" on the profile strip rides the route with a real-time 3D cyclist (three.js, lit and shadowed) who matches the confidence level: a parent with a waving child and a flag, an upright town bike with a basket and a scarf, a hybrid rider with a backpack, a road rider, or a racer in an aero tuck with speed streaks. Legs pedal with proper knee bends, wheels spin, and the rider turns with the route; changing confidence mid-ride swaps the rider. Browsers without WebGL get a drawn rider instead. at 1, 2, 4 or 8 times speed (1x is 25 m a second, 2x is the default), with the profile cursor moving in step. While it plays you can drag to look around, scroll or pinch to zoom, and tilt or turn the camera; it keeps your view and carries on following the rider, and "Recentre" puts it back behind them. Click the profile to jump, press Space to pause and Escape to stop. The virtual cycle plays in 3D by default, over Esri satellite imagery with buildings extruded from their OpenStreetMap heights (via OpenFreeMap's free vector tiles) and gently exaggerated terrain, drawn with MapLibre GL. "View" switches to OpenFreeMap's map style instead. With "Photo-textured buildings" (on by default over satellite), a three.js layer redraws the buildings around the rider: roofs are textured with a mosaic of satellite tiles, and walls take the imagery's colour at each building, warmed towards sandstone and lit by a low sun. It rebuilds as the rider moves on, switches terrain off so roofs line up with the imagery, and falls back to plain extrusions if the imagery can't be used. It starts at 2x speed. The camera looks about 90 m ahead, eases its heading and position over about a second so corners feel like a turn rather than a snap, and slows through sharp bends. Untick "3D with buildings" to fly over the 2D map instead; browsers without WebGL fall back to 2D automatically. "Open Street View here" opens Google Street View at the arrow's position, facing the direction of travel. That link needs no key.

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
| Cycling levels | NPT modelled daily cycle flows (May 2025), scaled to Glasgow City Council automatic cycle counters (2022 to 2024) and checked against DfT counted pedal cycles (2018) | ODbL (NPT), Open Government Licence v3.0 (council and DfT) |
| Bike collisions | DfT STATS19 road safety data for Glasgow, 2016 to 2023, published by Glasgow City Council | Open Government Licence v3.0 |
| Crossings | OpenStreetMap crossing points via Overpass, Glasgow City Council city-centre signal sites (CCTP tactile facilities) | © OpenStreetMap contributors (ODbL); Glasgow City Council open data |
| Music | Kevin MacLeod (incompetech.com) library tracks; Radio Swiss Classic and Nightride FM streams as a fallback | CC BY 4.0 for the library; each station's own terms |
| 3D rider | three.js 0.149, loaded only for the virtual cycle | MIT |
| 3D virtual cycle | OpenFreeMap vector tiles (OpenMapTiles schema) drawn with MapLibre GL, terrain from Mapzen Terrain Tiles | © OpenMapTiles, data © OpenStreetMap contributors |
| Background maps | OpenStreetMap standard tiles (light grey and streets), CyclOSM, Esri World Imagery (satellite) | © OpenStreetMap contributors under the tile usage policy; CyclOSM; imagery © Esri, Maxar, Earthstar Geographics and the GIS User Community |

The network data embedded in `index.html` is a derived database of OpenStreetMap and is published under the [Open Database Licence 1.0](https://opendatacommons.org/licenses/odbl/1-0/). The code is MIT licensed (see `LICENSE`).

## Rebuilding the data

The scripts in `scripts/` rebuild the embedded data. They are prototype quality. See `scripts/README.md` for the order and inputs.
