"""Home screen."""

from __future__ import annotations

from ofertaks.app.localization import t
from ofertaks.ui.widgets.offer_card import OfferCardMixin
from ofertaks.ui.widgets.search_bar import build_search_bar

try:
    from kivy.uix.screenmanager import Screen
except Exception:  # pragma: no cover
    class Screen:  # type: ignore[no-redef]
        pass


class HomeScreen(Screen, OfferCardMixin):
    def __init__(self, app, **kwargs):
        from kivy.metrics import dp
        from kivy.uix.boxlayout import BoxLayout
        from kivy.uix.button import Button
        from kivy.uix.label import Label
        from kivy.uix.scrollview import ScrollView

        super().__init__(**kwargs)
        self.app = app
        layout = BoxLayout(orientation="vertical", padding=dp(12), spacing=dp(10))
        header = BoxLayout(orientation="vertical", size_hint_y=None, height=dp(76))
        header.add_widget(Label(text=t("app_title"), font_size="26sp", bold=True, halign="left", text_size=(0, None)))
        header.add_widget(Label(text=t("tagline"), font_size="15sp", halign="left", text_size=(0, None)))
        layout.add_widget(header)
        search_row, self.search_input = build_search_bar(self._search)
        layout.add_widget(search_row)
        action_row = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(44), spacing=dp(8))
        self.last_sync_label = Label(text="", halign="left", valign="middle", text_size=(0, None))
        refresh = Button(text=t("refresh"), size_hint_x=None, width=dp(112))
        refresh.bind(on_release=lambda *_: self.app.start_sync())
        action_row.add_widget(self.last_sync_label)
        action_row.add_widget(refresh)
        layout.add_widget(action_row)
        self.status_label = Label(text="", size_hint_y=None, height=dp(32), halign="left", text_size=(0, None))
        layout.add_widget(self.status_label)
        layout.add_widget(Label(text=t("best_deals"), size_hint_y=None, height=dp(30), bold=True, halign="left", text_size=(0, None)))
        scroll = ScrollView()
        self.offer_list = BoxLayout(orientation="vertical", spacing=dp(8), size_hint_y=None)
        self.offer_list.bind(minimum_height=self.offer_list.setter("height"))
        scroll.add_widget(self.offer_list)
        layout.add_widget(scroll)
        self.add_widget(layout)

    def _search(self, query: str) -> None:
        query = query.strip()
        if not query:
            return
        self.app.screens["search"].set_query(query)
        self.app.show_screen("search")

    def reload(self) -> None:
        from kivy.metrics import dp
        from kivy.uix.label import Label

        latest = self.app.repository.latest_sync_label()
        self.last_sync_label.text = f"{t('last_sync')}: {latest or t('offline_data')}"
        self.offer_list.clear_widgets()
        offers = self.app.repository.list_offers(limit=30)
        if not offers:
            self.offer_list.add_widget(Label(text=t("no_offers"), size_hint_y=None, height=dp(44)))
            return
        for offer in offers:
            self.offer_list.add_widget(self.build_offer_card(offer, self.app.show_product))

    def sync_status_changed(self, statuses: dict[str, str]) -> None:
        if not statuses:
            self.status_label.text = ""
            return
        self.status_label.text = " | ".join(f"{store}: {status}" for store, status in statuses.items())
