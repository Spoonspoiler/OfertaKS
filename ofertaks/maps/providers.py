"""Tile provider configuration kept separate from OfertaKS merchant overlays."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class MapTileProvider:
    id: str
    tile_url: str
    attribution: str
    min_zoom: int
    max_zoom: int

    def url_for(self, zoom: int, x: int, y: int) -> str:
        return self.tile_url.format(z=zoom, x=x, y=y)


# Standard OSM tiles are requested only for the active viewport. The URL is a
# configuration value so another OSM-compatible provider can replace it later.
OSM_STANDARD_PROVIDER = MapTileProvider(
    id="osm_standard",
    tile_url="https://tile.openstreetmap.org/{z}/{x}/{y}.png",
    attribution="© OpenStreetMap contributors",
    min_zoom=2,
    max_zoom=19,
)
