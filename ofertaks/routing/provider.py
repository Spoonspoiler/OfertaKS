"""Small future routing boundary. No route backend is selected in this slice."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class RouteResult:
    coordinates: tuple[tuple[float, float], ...]
    distance_km: float
    duration_minutes: float
    mode: str = "walking"


class RouteProvider(Protocol):
    def route(
        self,
        start: tuple[float, float],
        destination: tuple[float, float],
        mode: str = "walking",
    ) -> RouteResult: ...
