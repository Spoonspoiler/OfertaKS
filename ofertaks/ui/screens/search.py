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
        from kivy.uix.scrollview import ScrollView

        super().__init__(**kwargs)
        self.app = app
        self.query = ""
        frame, layout = make_screen_layout()
        self.title_label = make_label(text=t("search"), size_hint_y=None, height=dp(36), bold=True, font_size="22sp")
        layout.add_widget(self.title_label)
        row, self.input_box, self.search_button = build_search_bar(self.set_query)
        layout.add_widget(row)
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

    def set_query(self, query: str) -> None:
        self.query = query.strip()
        self.input_box.text = self.query
        self.reload()

    def reload(self) -> None:
        from kivy.metrics import dp

        self.results.clear_widgets()
        self._offer_context_cache = {}
        if not self.query:
            return
        offers = self.app.repository.search_offers(self.query)
        if not offers:
            self.results.add_widget(make_label(text=t("no_offers"), size_hint_y=None, height=dp(44), color=MUTED))
            return
        for offer in offers:
            self.results.add_widget(self.build_offer_card(offer, self.app.show_product))
