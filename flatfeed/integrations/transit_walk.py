from __future__ import annotations

import csv
import math
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from sqlalchemy import select

from flatfeed.config import PROJECT_ROOT
from flatfeed.db.models import Listing
from flatfeed.db.session import SessionLocal


STATIONS_CSV_PATH = PROJECT_ROOT / "data" / "berlin_transit_stations.csv"
WALKING_DISTANCE_FACTOR = 1.25
WALKING_METERS_PER_MINUTE = 80


@dataclass(frozen=True)
class TransitStation:
    name: str
    station_type: str
    latitude: float
    longitude: float


@dataclass(frozen=True)
class TransitWalkInfo:
    s_bahn_minutes: Optional[int]
    u_bahn_minutes: Optional[int]
    s_bahn_station: Optional[str] = None
    u_bahn_station: Optional[str] = None

    def as_dict(self) -> Dict[str, Optional[object]]:
        return {
            "s_bahn_minutes": self.s_bahn_minutes,
            "u_bahn_minutes": self.u_bahn_minutes,
            "s_bahn_station": self.s_bahn_station,
            "u_bahn_station": self.u_bahn_station,
            "method": "local_vbb_station_distance",
            "walking_distance_factor": WALKING_DISTANCE_FACTOR,
        }


def _haversine_meters(
    *,
    lat1: float,
    lon1: float,
    lat2: float,
    lon2: float,
) -> float:
    radius_meters = 6_371_000
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_phi / 2) ** 2
        + math.cos(phi1)
        * math.cos(phi2)
        * math.sin(delta_lambda / 2) ** 2
    )
    return radius_meters * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _distance_to_walking_minutes(distance_meters: float) -> int:
    adjusted_distance = distance_meters * WALKING_DISTANCE_FACTOR
    return max(1, math.ceil(adjusted_distance / WALKING_METERS_PER_MINUTE))


@lru_cache(maxsize=1)
def load_transit_stations(path: Path = STATIONS_CSV_PATH) -> List[TransitStation]:
    if not path.exists():
        return []

    stations: List[TransitStation] = []
    with path.open(newline="", encoding="utf-8") as csv_file:
        reader = csv.DictReader(csv_file)
        for row in reader:
            try:
                stations.append(
                    TransitStation(
                        name=row["station_name"],
                        station_type=row["station_type"],
                        latitude=float(row["latitude"]),
                        longitude=float(row["longitude"]),
                    )
                )
            except (KeyError, TypeError, ValueError):
                continue
    return stations


def _nearest_station(
    *,
    latitude: float,
    longitude: float,
    station_type: str,
    stations: Iterable[TransitStation],
) -> Optional[tuple[TransitStation, float]]:
    nearest: Optional[tuple[TransitStation, float]] = None
    for station in stations:
        if station.station_type != station_type:
            continue
        distance = _haversine_meters(
            lat1=latitude,
            lon1=longitude,
            lat2=station.latitude,
            lon2=station.longitude,
        )
        if nearest is None or distance < nearest[1]:
            nearest = (station, distance)
    return nearest


def compute_transit_walk_info(
    *,
    latitude: Optional[float],
    longitude: Optional[float],
) -> TransitWalkInfo:
    if latitude is None or longitude is None:
        return TransitWalkInfo(s_bahn_minutes=None, u_bahn_minutes=None)

    stations = load_transit_stations()
    if not stations:
        return TransitWalkInfo(s_bahn_minutes=None, u_bahn_minutes=None)

    nearest_s_bahn = _nearest_station(
        latitude=latitude,
        longitude=longitude,
        station_type="s_bahn",
        stations=stations,
    )
    nearest_u_bahn = _nearest_station(
        latitude=latitude,
        longitude=longitude,
        station_type="u_bahn",
        stations=stations,
    )

    return TransitWalkInfo(
        s_bahn_minutes=(
            _distance_to_walking_minutes(nearest_s_bahn[1])
            if nearest_s_bahn is not None
            else None
        ),
        u_bahn_minutes=(
            _distance_to_walking_minutes(nearest_u_bahn[1])
            if nearest_u_bahn is not None
            else None
        ),
        s_bahn_station=nearest_s_bahn[0].name if nearest_s_bahn is not None else None,
        u_bahn_station=nearest_u_bahn[0].name if nearest_u_bahn is not None else None,
    )


def enrich_missing_transport_walk(
    *,
    limit: Optional[int] = None,
    listing_urls: Optional[Iterable[str]] = None,
) -> int:
    if not load_transit_stations():
        return 0
    listing_url_tuple = tuple(listing_urls or ())

    with SessionLocal() as session:
        statement = (
            select(Listing)
            .where(Listing.transport_walk.is_(None))
            .where(Listing.source_active.is_(True))
            .order_by(Listing.updated_at.desc(), Listing.listing_id.desc())
        )
        if listing_url_tuple:
            statement = statement.where(Listing.url.in_(listing_url_tuple))
        if limit is not None:
            statement = statement.limit(limit)

        listings = list(session.scalars(statement))
        enriched_count = 0
        for listing in listings:
            if listing.latitude is None or listing.longitude is None:
                continue

            info = compute_transit_walk_info(
                latitude=listing.latitude,
                longitude=listing.longitude,
            )
            listing.transport_walk = info.as_dict()
            enriched_count += 1

        session.commit()
        return enriched_count
