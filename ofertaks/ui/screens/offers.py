"""Offers screen."""

from __future__ import annotations

from ofertaks.app.localization import t
from ofertaks.ui.widgets.offer_card import OfferCardMixin

try:
    from kivy.uix.screenmanager import Screen
except Exception:  # pragma: no cover
    class Screen:  # type: ignore[no-redef]
        pass


class OffersScreen(Screen, OfferCardMixin):
    def __init__(self, app, **kwargs):
        from kivy.metrics import dp
        from kivy.uix.boxlayout import BoxLayout
        from kivy.uix.label import Label
        from kivy.uix.scrollview import ScrollView
        from kivy.uix.spinner import Spinner

        super().__init__(**kwargs)
        self.app = app
        layout = BoxLayout(orientation="vertical", padding=dp(12), spacing=dp(8))
        layout.add_widget(Label(text=t("offers"), size_hint_y=None, height=dp(36), bold=True, font_size="22sp"))
        filters = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(8))
        self.store_spinner = Spinner(text="All", values=("All", "Viva Fresh", "Interex", "ETC"))
        self.sort_spinner = Spinner(
            text="Best deals",
            values=("Best deals", "Lowest price", "Largest discount", "Newest", "Price per unit"),
        )
        self.store_spinner.bind(text=lambda *_: self.reload())
        self.sort_spinner.bind(text=lambda *_: self.reload())
        filters.add_widget(self.store_spinner)
        filters.add_widget(self.sort_spinner)
        layout.add_widget(filters)
        scroll = ScrollView()
        self.offer_list = BoxLayout(orientation="vertical", spacing=dp(8), size_hint_y=None)
        self.offer_list.bind(minimum_height=self.offer_list.setter("height"))
        scroll.add_widget(self.offer_list)
        layout.add_widget(scroll)
        self.add_widget(layout)

    def reload(self) -> None:
        from kivy.metrics import dp
        from kivy.uix.label import Label

        store_map = {"Viva Fresh": "viva_fresh", "Interex": "interex", "ETC": "etc"}
        sort_map = {
            "Best deals": "best",
            "Lowest price": "lowest",
            "Largest discount": "discount",
            "Newest": "newest",
            "Price per unit": "unit",
        }
        store_id = store_map.get(self.store_spinner.text)
        sort = sort_map.get(self.sort_spinner.text, "best")
        offers = self.app.repository.list_offers(store_id=store_id, sort=sort, limit=250)
        self.offer_list.clear_widgets()
        if not offers:
            self.offer_list.add_widget(Label(text=t("no_offers"), size_hint_y=None, height=dp(44)))
            return
        for offer in offers:
            self.offer_list.add_widget(self.build_offer_card(offer, self.app.show_product))
