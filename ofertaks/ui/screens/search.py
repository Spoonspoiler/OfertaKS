"""Search screen."""

from __future__ import annotations

from ofertaks.localization import t
from ofertaks.ui.theme import MUTED, bind_scroll_content_width, make_label, make_screen_layout
from ofertaks.ui.widgets.offer_card import OfferCardMixin
from ofertaks.ui.widgets.search_bar import build_search_bar

try:
    from kivy.uix.screenmanager import Screen
except Exception:  # pragma: no cover
    class Screen:  # type: ignore[no-redef]
        pass


class SearchScreen(Screen, OfferCardMixin):
    def __init__(self, app, **kwargs):
        from kivy.metrics import dp
        from kivy.uix.boxlayout import BoxLayout
        from kivy.uix.button import Button
        from kivy.uix.scrollview import ScrollView

        super().__init__(**kwargs)
        self.app = app
        self.query = ""
        frame, layout = make_screen_layout()
        self.title_label = make_label(text=t("search"), size_hint_y=None, height=dp(36), bold=True, font_size="22sp")
        layout.add_widget(self.title_label)
        row, self.input_box, self.search_button = build_search_bar(self.set_query)
        layout.add_widget(row)
        self.scan_button = Button(text=t("scan_product"), size_hint_y=None, height=dp(38))
        self.scan_button.bind(on_release=lambda *_: self.app.show_barcode_scan(return_screen="search"))
        layout.add_widget(self.scan_button)
        self.show_map_button = Button(
            text=t("show_on_map"), size_hint_y=None, height=dp(38), disabled=True
        )
        self.show_map_button.bind(on_release=lambda *_: self._show_on_map())
        layout.add_widget(self.show_map_button)
        scroll = ScrollView()
        self.results = BoxLayout(orientation="vertical", spacing=dp(8), size_hint_y=None)
        self.results.bind(minimum_height=self.results.setter("height"))
        bind_scroll_content_width(scroll, self.results)
        scroll.add_widget(self.results)
        layout.add_widget(scroll)
        self.add_widget(frame)

    def translate(self) -> None:
        self.title_label.text = t("search")
        self.input_box.hint_text = t("search")
        self.search_button.text = t("search")
        self.scan_button.text = t("scan_product")
        self.show_map_button.text = t("show_on_map")

    def set_query(self, query: str) -> None:
        self.query = query.strip()
        self.input_box.text = self.query
        self.reload()

    def reload(self) -> None:
        from kivy.metrics import dp

        self.results.clear_widgets()
        self._offer_context_cache = {}
        self._map_offer = None
        self.show_map_button.disabled = True
        if not self.query:
            return
        offers = self.app.repository.search_offers(self.query)
        if not offers:
            self.results.add_widget(make_label(text=t("no_offers"), size_hint_y=None, height=dp(44), color=MUTED))
            return
        for offer in offers:
            self.results.add_widget(self.build_offer_card(offer, self.app.show_product))
        self._map_offer = offers[0]
        self.show_map_button.disabled = False

    def _show_on_map(self) -> None:
        offer = getattr(self, "_map_offer", None)
        if not offer:
            return
        self.app.show_map(
            product_id=self.app.repository.find_product_id_for_offer(offer),
            product_name=offer.raw_name,
        )
