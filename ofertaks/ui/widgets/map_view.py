"""Small Kivy map surface with an OSM-compatible basemap and OfertaKS overlay."""

from __future__ import annotations

import math
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Callable

from ofertaks.app.paths import get_map_cache_dir
from ofertaks.maps.providers import MapTileProvider, OSM_STANDARD_PROVIDER
from ofertaks.ui.theme import PRICE_STATUS_COLORS, add_fill_background
from ofertaks.utils.network import HTTPClient

try:
    from kivy.clock import Clock
    from kivy.graphics import Color, Line, Rectangle
    from kivy.metrics import dp
    from kivy.uix.button import Button
    from kivy.uix.floatlayout import FloatLayout
    from kivy.uix.image import Image
except Exception:  # pragma: no cover - Kivy is optional for non-UI tests
    FloatLayout = None


def _clamp_latitude(latitude: float) -> float:
    return max(-85.05112878, min(85.05112878, latitude))


def latlon_to_world(latitude: float, longitude: float, zoom: int) -> tuple[float, float]:
    size = 256 * (2**zoom)
    latitude = _clamp_latitude(latitude)
    x = (longitude + 180.0) / 360.0 * size
    sin_latitude = math.sin(math.radians(latitude))
    y = (0.5 - math.log((1 + sin_latitude) / (1 - sin_latitude)) / (4 * math.pi)) * size
    return x, y


def world_to_latlon(x: float, y: float, zoom: int) -> tuple[float, float]:
    size = 256 * (2**zoom)
    longitude = x / size * 360.0 - 180.0
    n = math.pi - (2 * math.pi * y / size)
    latitude = math.degrees(math.atan(math.sinh(n)))
    return _clamp_latitude(latitude), longitude


def center_after_drag(
    center: tuple[float, float], start: tuple[float, float], position: tuple[float, float], zoom: int
) -> tuple[float, float]:
    """Move the map with the pointer while preserving horizontal map semantics."""

    start_x, start_y = start
    current_x, current_y = position
    world_x, world_y = latlon_to_world(*center, zoom)
    return world_to_latlon(world_x - (current_x - start_x), world_y + (current_y - start_y), zoom)


if FloatLayout is not None:

    class MapSurface(FloatLayout):
        """Pan/zoom tile surface that requests only currently visible tiles."""

        def __init__(
            self,
            provider: MapTileProvider = OSM_STANDARD_PROVIDER,
            center: tuple[float, float] = (42.6597, 21.1566),
            zoom: int = 14,
            tiles_enabled: bool | None = None,
            **kwargs,
        ) -> None:
            super().__init__(**kwargs)
            self.provider = provider
            self.center_latitude, self.center_longitude = center
            self.zoom = max(provider.min_zoom, min(provider.max_zoom, zoom))
            self.tiles_enabled = (
                os.environ.get("OFERTAKS_DISABLE_MAP_TILES", "0") != "1"
                if tiles_enabled is None
                else tiles_enabled
            )
            self.on_viewport_changed: Callable[[tuple[float, float, float, float]], None] | None = None
            self.on_marker_selected: Callable[[object], None] | None = None
            self._tile_layer = FloatLayout()
            self._marker_layer = FloatLayout()
            self.add_widget(self._tile_layer)
            self.add_widget(self._marker_layer)
            self._tiles: dict[tuple[int, int, int], Image] = {}
            self._fetching: set[tuple[int, int, int]] = set()
            self._markers: list[object] = []
            self._marker_buttons: list[tuple[object, Button]] = []
            self._route: tuple[tuple[float, float], ...] = ()
            self._executor = ThreadPoolExecutor(max_workers=2)
            self._client = HTTPClient()
            self._drag_start: tuple[float, float] | None = None
            self._drag_center: tuple[float, float] | None = None
            self._touches: dict[str, tuple[float, float]] = {}
            self._pinch_distance: float | None = None
            self._notify_event = None
            with self.canvas.before:
                Color(0.85, 0.88, 0.87, 1)
                self._background = Rectangle(pos=self.pos, size=self.size)
            self.bind(pos=self._resized, size=self._resized)
            Clock.schedule_once(lambda _dt: self.refresh(), 0)

        def _resized(self, *_args) -> None:
            self._background.pos = self.pos
            self._background.size = self.size
            self.refresh()

        def set_view(self, latitude: float, longitude: float, zoom: int | None = None) -> None:
            self.center_latitude = _clamp_latitude(latitude)
            self.center_longitude = max(-180.0, min(180.0, longitude))
            if zoom is not None:
                self.zoom = max(self.provider.min_zoom, min(self.provider.max_zoom, zoom))
            self.refresh()

        def zoom_by(self, increment: int) -> None:
            self.set_view(self.center_latitude, self.center_longitude, self.zoom + increment)

        def set_markers(self, markers: list[object]) -> None:
            self._markers = list(markers)
            self._marker_layer.clear_widgets()
            self._marker_buttons = []
            for result in self._markers[:80]:
                marker_width = max(dp(42), min(dp(96), dp(20 + len(result.marker_code) * 7)))
                button = Button(
                    text=result.marker_code,
                    size_hint=(None, None),
                    size=(marker_width, dp(32)),
                    font_size="10sp",
                )
                add_fill_background(button, PRICE_STATUS_COLORS[result.price_status_color], radius=5)
                button.bind(on_release=lambda _button, value=result: self._select_marker(value))
                self._marker_buttons.append((result, button))
                self._marker_layer.add_widget(button)
            self._render_markers()

        def set_route_polyline(self, coordinates: tuple[tuple[float, float], ...]) -> None:
            self._route = coordinates
            self._draw_route()

        def visible_bbox(self, padding: float = 0.08) -> tuple[float, float, float, float]:
            center_x, center_y = latlon_to_world(self.center_latitude, self.center_longitude, self.zoom)
            half_width = self.width * (0.5 + padding)
            half_height = self.height * (0.5 + padding)
            north, west = world_to_latlon(center_x - half_width, center_y - half_height, self.zoom)
            south, east = world_to_latlon(center_x + half_width, center_y + half_height, self.zoom)
            return south, west, north, east

        def refresh(self) -> None:
            if self.width <= 1 or self.height <= 1:
                return
            self._render_tiles()
            self._render_markers()
            self._draw_route()
            self._schedule_viewport_notify()

        def _render_tiles(self) -> None:
            center_x, center_y = latlon_to_world(self.center_latitude, self.center_longitude, self.zoom)
            left = center_x - self.width / 2
            bottom = center_y - self.height / 2
            first_x = math.floor(left / 256)
            last_x = math.floor((left + self.width) / 256)
            first_y = math.floor(bottom / 256)
            last_y = math.floor((bottom + self.height) / 256)
            tile_count = 2**self.zoom
            visible: set[tuple[int, int, int]] = set()
            missing_tiles: list[tuple[int, int, int]] = []
            for display_x in range(first_x, last_x + 1):
                for tile_y in range(max(0, first_y), min(tile_count - 1, last_y) + 1):
                    tile_x = display_x % tile_count
                    key = (self.zoom, tile_x, tile_y)
                    visible.add(key)
                    image = self._tiles.get(key)
                    if image is None:
                        image = Image(size_hint=(None, None), size=(256, 256), allow_stretch=True, opacity=0)
                        self._tiles[key] = image
                        self._tile_layer.add_widget(image)
                        cached = self._tile_path(*key)
                        if cached.exists():
                            image.source = str(cached)
                            image.opacity = 1
                        elif self.tiles_enabled:
                            missing_tiles.append(key)
                    image.size = (256, 256)
                    image.pos = (
                        self.x + (display_x * 256 - left),
                        self.top - ((tile_y + 1) * 256 - bottom),
                    )
            for key, image in list(self._tiles.items()):
                if key not in visible:
                    self._tile_layer.remove_widget(image)
                    del self._tiles[key]
            center_tile = (center_x / 256, center_y / 256)
            for key in sorted(
                missing_tiles,
                key=lambda value: (value[1] - center_tile[0]) ** 2 + (value[2] - center_tile[1]) ** 2,
            ):
                self._fetch_tile(key)

        def _tile_path(self, zoom: int, x: int, y: int) -> Path:
            path = get_map_cache_dir() / "tiles" / self.provider.id / str(zoom) / str(x)
            return path / f"{y}.png"

        def _fetch_tile(self, key: tuple[int, int, int]) -> None:
            if key in self._fetching:
                return
            self._fetching.add(key)

            def worker() -> tuple[tuple[int, int, int], Path | None]:
                zoom, x, y = key
                try:
                    response = self._client.get(self.provider.url_for(zoom, x, y), timeout=15)
                    if response.status_code != 200 or not response.content:
                        return key, None
                    path = self._tile_path(zoom, x, y)
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(response.content)
                    return key, path
                except (OSError, RuntimeError):
                    return key, None

            future = self._executor.submit(worker)

            def done(_future) -> None:
                try:
                    loaded_key, path = future.result()
                except Exception:  # pragma: no cover - defensive worker boundary
                    loaded_key, path = key, None

                def apply(_dt) -> None:
                    self._fetching.discard(loaded_key)
                    image = self._tiles.get(loaded_key)
                    if image is not None and path is not None:
                        image.source = str(path)
                        image.reload()
                        image.opacity = 1

                Clock.schedule_once(apply, 0)

            future.add_done_callback(done)

        def _render_markers(self) -> None:
            center_x, center_y = latlon_to_world(self.center_latitude, self.center_longitude, self.zoom)
            for result, button in self._marker_buttons:
                merchant = result.merchant
                world_x, world_y = latlon_to_world(merchant["latitude"], merchant["longitude"], self.zoom)
                x = self.center_x + (world_x - center_x)
                y = self.center_y - (world_y - center_y)
                visible = self.x - dp(24) <= x <= self.right + dp(24) and self.y - dp(24) <= y <= self.top + dp(24)
                if visible:
                    button.pos = (x - button.width / 2, y - dp(16))
                button.opacity = 1 if visible else 0
                button.disabled = not visible

        def _select_marker(self, result: object) -> None:
            if self.on_marker_selected:
                self.on_marker_selected(result)

        def _draw_route(self) -> None:
            self.canvas.after.clear()
            if len(self._route) < 2:
                return
            center_x, center_y = latlon_to_world(self.center_latitude, self.center_longitude, self.zoom)
            points: list[float] = []
            for latitude, longitude in self._route:
                world_x, world_y = latlon_to_world(latitude, longitude, self.zoom)
                points.extend((self.center_x + world_x - center_x, self.center_y - (world_y - center_y)))
            with self.canvas.after:
                Color(0.10, 0.36, 0.72, 0.85)
                Line(points=points, width=dp(3))

        def _schedule_viewport_notify(self) -> None:
            if not self.on_viewport_changed:
                return
            if self._notify_event is not None:
                self._notify_event.cancel()
            self._notify_event = Clock.schedule_once(
                lambda _dt: self.on_viewport_changed and self.on_viewport_changed(self.visible_bbox()), 0.18
            )

        def on_touch_down(self, touch):
            if getattr(touch, "button", None) == "scrollup":
                self.zoom_by(1)
                return True
            if getattr(touch, "button", None) == "scrolldown":
                self.zoom_by(-1)
                return True
            if not self.collide_point(*touch.pos):
                return super().on_touch_down(touch)
            self._touches[touch.uid] = touch.pos
            if len(self._touches) == 1:
                self._drag_start = touch.pos
                self._drag_center = (self.center_latitude, self.center_longitude)
            elif len(self._touches) == 2:
                self._pinch_distance = self._touch_distance()
            return super().on_touch_down(touch)

        def on_touch_move(self, touch):
            if touch.uid not in self._touches:
                return super().on_touch_move(touch)
            self._touches[touch.uid] = touch.pos
            if len(self._touches) == 1 and self._drag_start and self._drag_center:
                latitude, longitude = center_after_drag(
                    self._drag_center, self._drag_start, (touch.x, touch.y), self.zoom
                )
                self.center_latitude, self.center_longitude = latitude, longitude
                self.refresh()
            elif len(self._touches) == 2 and self._pinch_distance:
                distance = self._touch_distance()
                if distance >= self._pinch_distance * 1.25:
                    self.zoom_by(1)
                    self._pinch_distance = distance
                elif distance <= self._pinch_distance * 0.8:
                    self.zoom_by(-1)
                    self._pinch_distance = distance
            return True

        def on_touch_up(self, touch):
            self._touches.pop(touch.uid, None)
            if not self._touches:
                self._drag_start = None
                self._drag_center = None
                self._pinch_distance = None
            return super().on_touch_up(touch)

        def _touch_distance(self) -> float:
            points = list(self._touches.values())
            if len(points) != 2:
                return 0.0
            return math.dist(points[0], points[1])

else:

    class MapSurface:  # pragma: no cover - only used when Kivy is unavailable
        def __init__(self, *_args, **_kwargs) -> None:
            raise RuntimeError("Kivy is required to render the map")
