# Rebuilding the data

Run from the repository root with Python 3.11 or later and `geopandas`, `pyogrio`, `scipy`, `pyproj` and `requests` installed. Files are written to `data/`.

1. Download the inputs into `data/`:
   - `cbd_layer_2025-05-01.gpkg` and `data_zones_2025-05-01.gpkg` from the Network Planning Tool release `v2025-05-01` at https://github.com/nptscot/npt/releases
   - `city_network.geojson` from Glasgow City Council's `ATS_ROUTES` feature service (query with `where=1=1&outFields=*&outSR=4326&f=geojson`)
   - `boundary.geojson` from the council's `Pub_City_Boundary` feature service
   - `signal_crossings.geojson` and `water.geojson` from Esri's OpenStreetMap Highways and Water Bodies for Europe services
2. Clip the Cycling by Design layer to the city boundary and join live OpenStreetMap attributes: run `fetch_osm.py` to get `data/osm_attrs.json`, then clip `cbd_layer` to `boundary.geojson`, merge on `osm_id`, and save as `data/net_city.gpkg`.
3. Run `build_network.py` to split ways at junctions and write `data/network.json`.
4. Run `prep2.py` to add the 2032 programme flags and data zones, writing `data/network2.json`.
5. Paste `data/network2.json` into the `net-data` script tag in `index.html`.
