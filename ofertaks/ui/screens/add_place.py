"""Local community form for a missing Prishtina food place."""

from __future__ import annotations

from ofertaks.localization import t
from ofertaks.maps.service import MapService
from ofertaks.models.merchant import (
    BAKERY,
    BUTCHER,
    CONVENIENCE,
    DAIRY,
    FARM,
    FISH,
    FRUIT_VEGETABLE,
    GROCERY,
    MARKET,
    MARKET_STALL,
    SPECIALTY_FOOD,
    STREET_VENDOR,
    SUPERMARKET,
)
from ofertaks.ui.theme import MUTED, bind_scroll_content_width, make_label, make_screen_layout

try:
    from kivy.uix.screenmanager import Screen
except Exception:  # pragma: no cover
    class Screen:  # type: ignore[no-redef]
        pass


MERCHANT_TYPE_KEYS = {
    SUPERMARKET: "map_type_supermarket",
    GROCERY: "map_type_grocery",
    CONVENIENCE: "map_type_convenience",
    FRUIT_VEGETABLE: "map_type_fruit_vegetable",
    MARKET: "map_type_market",
    MARKET_STALL: "map_type_market_stall",
    BAKERY: "map_type_bakery",
    BUTCHER: "map_type_butcher",
    FISH: "map_type_fish",
    DAIRY: "map_type_dairy",
    FARM: "map_type_farm",
    SPECIALTY_FOOD: "map_type_specialty_food",
    STREET_VENDOR: "map_type_street_vendor",
}


class AddPlaceScreen(Screen):
    def __init__(self, app, **kwargs):
        from kivy.metrics import dp
        from kivy.uix.boxlayout import BoxLayout
        from kivy.uix.button import Button
        from kivy.uix.scrollview import ScrollView
        from kivy.uix.spinner import Spinner
        from kivy.uix.textinput import TextInput

        super().__init__(**kwargs)
        self.app = app
        self.location = (42.6597, 21.1566)
        self.type_labels: dict[str, str] = {}
        self._labels: dict[str, object] = {}
        frame, layout = make_screen_layout()
        self.back_button = Button(text=t("back"), size_hint_y=None, height=dp(40))
        self.back_button.bind(on_release=lambda *_: self.app.show_screen("map"))
        layout.add_widget(self.back_button)
        self.title = make_label(text=t("add_place"), size_hint_y=None, height=dp(34), bold=True, font_size="22sp")
        layout.add_widget(self.title)
        scroll = ScrollView()
        form = BoxLayout(orientation="vertical", size_hint_y=None, spacing=dp(7), padding=(0, 0, 0, dp(8)))
        form.bind(minimum_height=form.setter("height"))
        bind_scroll_content_width(scroll, form)
        scroll.add_widget(form)
        layout.add_widget(scroll)
        self.name_input = self._field(form, "place_name", TextInput)
        self._label(form, "merchant_type")
        self.type_spinner = Spinner(size_hint_y=None, height=dp(42))
        form.add_widget(self.type_spinner)
        self.latitude_input = self._field(form, "latitude", TextInput)
        self.longitude_input = self._field(form, "longitude", TextInput)
        self.description_input = self._field(form, "description", TextInput, multiline=True)
        self.hours_input = self._field(form, "opening_hours", TextInput)
        self.photo_input = self._field(form, "photo_path", TextInput)
        self.status = make_label(text="", size_hint_y=None, height=dp(34), color=MUTED)
        form.add_widget(self.status)
        self.save_button = Button(text=t("save_place"), size_hint_y=None, height=dp(46))
        self.save_button.bind(on_release=lambda *_: self._save())
        form.add_widget(self.save_button)
        self.add_widget(frame)
        self.translate()

    def _label(self, form, key: str) -> None:
        from kivy.metrics import dp

        label = make_label(text=t(key), size_hint_y=None, height=dp(22), bold=True)
        self._labels[key] = label
        form.add_widget(label)

    def _field(self, form, key: str, input_type, multiline: bool = False):
        from kivy.metrics import dp

        self._label(form, key)
        field = input_type(multiline=multiline, size_hint_y=None, height=dp(64 if multiline else 42))
        form.add_widget(field)
        return field

    def set_location(self, latitude: float, longitude: float) -> None:
        self.location = (latitude, longitude)
        self.latitude_input.text = f"{latitude:.6f}"
        self.longitude_input.text = f"{longitude:.6f}"
        self.status.text = ""

    def translate(self) -> None:
        self.back_button.text = t("back")
        self.title.text = t("add_place")
        self.save_button.text = t("save_place")
        for key, label in self._labels.items():
            label.text = t(key)
        self.type_labels = {t(key): value for value, key in MERCHANT_TYPE_KEYS.items()}
        self.type_spinner.values = tuple(self.type_labels)
        if self.type_spinner.text not in self.type_labels:
            self.type_spinner.text = t("map_type_fruit_vegetable")

    def _save(self) -> None:
        try:
            latitude = float(self.latitude_input.text.replace(",", "."))
            longitude = float(self.longitude_input.text.replace(",", "."))
        except ValueError:
            self.status.text = t("location_required")
            return
        merchant_type = self.type_labels.get(self.type_spinner.text, FRUIT_VEGETABLE)
        merchant_id = MapService(self.app.repository).add_community_merchant(
            name=self.name_input.text.strip() or t("unnamed_community_place"),
            merchant_type=merchant_type,
            latitude=latitude,
            longitude=longitude,
            description=self.description_input.text.strip() or None,
            opening_hours=self.hours_input.text.strip() or None,
            photo_path=self.photo_input.text.strip() or None,
        )
        self.app.show_map(merchant_id=merchant_id)
