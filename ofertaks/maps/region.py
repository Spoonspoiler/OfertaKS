"""Centralized initial geographic scope for the first OfertaKS market."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class MarketRegion:
    id: str
    city: str
    center_latitude: float
    center_longitude: float
    default_zoom: int
    min_latitude: float
    min_longitude: float
    max_latitude: float
    max_longitude: float
    discovery_radius_km: float

    @property
    def bbox(self) -> tuple[float, float, float, float]:
        return (
            self.min_latitude,
            self.min_longitude,
            self.max_latitude,
            self.max_longitude,
        )


# OSM's Prishtina project records the city at 42.6597, 21.1566. The bounded
# region intentionally covers only the city and immediate commercial suburbs.
PRISHTINA_REGION = MarketRegion(
    id="prishtina",
    city="Prishtina",
    center_latitude=42.6597,
    center_longitude=21.1566,
    default_zoom=14,
    min_latitude=42.6100,
    min_longitude=21.1000,
    max_latitude=42.7100,
    max_longitude=21.2400,
    discovery_radius_km=10.0,
)

DEFAULT_CITY = PRISHTINA_REGION.city
DEFAULT_CENTER_LAT = PRISHTINA_REGION.center_latitude
DEFAULT_CENTER_LON = PRISHTINA_REGION.center_longitude
DEFAULT_ZOOM = PRISHTINA_REGION.default_zoom
