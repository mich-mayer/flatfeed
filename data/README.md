# Transit Station Dataset

`berlin_transit_stations.csv` is generated from the official VBB GTFS feed.

The app uses this file to estimate walking time from synthetic listing
coordinates to the nearest S-Bahn and U-Bahn station without calling Google
Maps, Photon, or any paid API.

The historical generator kept only S-Bahn GTFS routes with `route_type=109` and
U-Bahn GTFS routes with `route_type=400`, then grouped stop points by station
name and transport type. The compact CSV is now bundled as a static demo asset.
