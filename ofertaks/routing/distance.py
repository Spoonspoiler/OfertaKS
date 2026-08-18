"""Small geographic distance helpers."""

from __future__ import annotations

from math import asin, cos, radians, sin, sqrt

EARTH_RADIUS_KM = 6371.0088
DEFAULT_WALKING_SPEED_KMH = 4.8


def haversine_km(
    latitude_a: float,
    longitude_a: float,
    latitude_b: float,
    longitude_b: float,
) -> float:
    """Return distance between two WGS84 points in kilometres."""
    lat_a = radians(latitude_a)
    lat_b = radians(latitude_b)
    delta_lat = radians(latitude_b - latitude_a)
    delta_lon = radians(longitude_b - longitude_a)
    inner = (
        sin(delta_lat / 2) ** 2
        + cos(lat_a) * cos(lat_b) * sin(delta_lon / 2) ** 2
    )
    return round(2 * EARTH_RADIUS_KM * asin(sqrt(inner)), 4)


def walking_minutes(distance_km: float, speed_kmh: float = DEFAULT_WALKING_SPEED_KMH) -> int:
    if distance_km <= 0:
        return 0
    return max(1, round(distance_km / speed_kmh * 60))
