"""Search screen."""

from __future__ import annotations

from ofertaks.app.localization import t
from ofertaks.ui.widgets.offer_card import OfferCardMixin
from ofertaks.ui.widgets.search_bar import build_search_bar


class SearchScreen(OfferCardMixin):
    def __init__(self, app, **kwargs):
        from kivy.metrics import dp
        from kivy.uix.boxlayout import BoxLayout
        from kivy.uix.label import Label
        from kivy.uix.screenmanager import Screen
        from kivy.uix.scrollview import ScrollView

        Screen.__init__(self, **kwargs)
        self.app = app
        self.query = ""
        layout = BoxLayout(orientation="vertical", padding=dp(12), spacing=dp(8))
        layout.add_widget(Label(text=t("search"), size_hint_y=None, height=dp(36), bold=True, font_size="22sp"))
        row, self.input_box = build_search_bar(self.set_query)
        layout.add_widget(row)
        scroll = ScrollView()
        self.results = BoxLayout(orientation="vertical", spacing=dp(8), size_hint_y=None)
        self.results.bind(minimum_height=self.results.setter("height"))
        scroll.add_widget(self.results)
        layout.add_widget(scroll)
        self.add_widget(layout)

    def set_query(self, query: str) -> None:
        self.query = query.strip()
        self.input_box.text = self.query
        self.reload()

    def reload(self) -> None:
        from kivy.metrics import dp
        from kivy.uix.label import Label

        self.results.clear_widgets()
        if not self.query:
            return
        offers = self.app.repository.search_offers(self.query)
        if not offers:
            self.results.add_widget(Label(text=t("no_offers"), size_hint_y=None, height=dp(44)))
            return
        for offer in offers:
            self.results.add_widget(self.build_offer_card(offer, self.app.show_product))
