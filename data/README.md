# Transit Station Dataset

`berlin_transit_stations.csv` is generated from the official VBB GTFS feed.

The app uses this file to estimate walking time from synthetic listing
coordinates to the nearest S-Bahn and U-Bahn station without calling Google
Maps, Photon, or any paid API.

The historical generator kept only S-Bahn GTFS routes with `route_type=109` and
U-Bahn GTFS routes with `route_type=400`, then grouped stop points by station
name and transport type. The compact CSV is now bundled as a static demo asset.

## Source and attribution

Source: **VBB Verkehrsverbund Berlin-Brandenburg GmbH**.
The [official VBB dataset page](https://unternehmen.vbb.de/digitale-services/datensaetze/)
provides the current static GTFS feed. The
[Berlin Open Data entry](https://daten.berlin.de/datensaetze/vbb-fahrplandaten-via-gtfs)
identifies VBB as the publisher and required attribution.

As checked on 2026-09-22, VBB publishes these datasets under
[Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/).
This repository's CSV is a transformed station subset, not the full feed:
only S-Bahn and U-Bahn station names, types, coordinates, and a source label
are retained. Keep this attribution and describe the transformation when
redistributing the CSV; the repository's code license does not replace the
upstream data terms.

## Bundled snapshot and provenance limits

- File: `berlin_transit_stations.csv`, 338 station rows plus a header.
- First recorded in this repository on 2026-06-25, commit
  [`669a5caa`](https://github.com/mich-mayer/flatfeed/commit/669a5caa0d0053ea605d88466a18ca8b16ffa4f5).
  This is the repository commit date, not a verified feed download date.
- SHA-256: `4b3f78ac2afb1f526b73d5b67d1c44dbe099761785b9aabc3266599fe76abd5c`.
- The original GTFS archive, feed version, acquisition timestamp, download
  checksum, and generator are not preserved. The original snapshot's license
  notice was not archived either; the current upstream terms above do not
  establish which notice accompanied that exact download.

The CSV is sufficient for the prototype's local geometric walking-time
estimate. It is not a current station-service or route-planning dataset.
No automatic data refresh runs. A future refresh should record the exact
source URL, acquisition date, feed metadata, archive checksum, applicable
license notice, transformation script, and resulting CSV checksum together.
