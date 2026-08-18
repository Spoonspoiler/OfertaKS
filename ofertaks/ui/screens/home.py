"""Home screen."""

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


class HomeScreen(Screen, OfferCardMixin):
    def __init__(self, app, **kwargs):
        from kivy.metrics import dp
        from kivy.uix.boxlayout import BoxLayout
        from kivy.uix.button import Button
        from kivy.uix.scrollview import ScrollView

        super().__init__(**kwargs)
        self.app = app
        frame, layout = make_screen_layout(spacing=10)
        header = BoxLayout(orientation="vertical", size_hint_y=None, height=dp(76))
        self.title_label = make_label(text=t("app_title"), font_size="26sp", bold=True)
        self.tagline_label = make_label(text=t("tagline"), font_size="15sp", color=MUTED)
        header.add_widget(self.title_label)
        header.add_widget(self.tagline_label)
        layout.add_widget(header)
        search_row, self.search_input, self.search_button = build_search_bar(self._search)
        layout.add_widget(search_row)
        action_row = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(44), spacing=dp(8))
        self.last_sync_label = make_label(text="")
        self.refresh_button = Button(text=t("refresh"), size_hint_x=None, width=dp(112))
        self.refresh_button.bind(on_release=lambda *_: self.app.start_sync())
        action_row.add_widget(self.last_sync_label)
        action_row.add_widget(self.refresh_button)
        layout.add_widget(action_row)
        self.status_label = make_label(text="", size_hint_y=None, height=dp(32), color=MUTED)
        layout.add_widget(self.status_label)
        self.best_deals_label = make_label(text=t("best_deals"), size_hint_y=None, height=dp(30), bold=True)
        layout.add_widget(self.best_deals_label)
        scroll = ScrollView()
        self.offer_list = BoxLayout(orientation="vertical", spacing=dp(8), size_hint_y=None)
        self.offer_list.bind(minimum_height=self.offer_list.setter("height"))
        bind_scroll_content_width(scroll, self.offer_list)
        scroll.add_widget(self.offer_list)
        layout.add_widget(scroll)
        self.add_widget(frame)

    def translate(self) -> None:
        self.title_label.text = t("app_title")
        self.tagline_label.text = t("tagline")
        self.search_input.hint_text = t("search")
        self.search_button.text = t("search")
        self.refresh_button.text = t("refresh")
        self.best_deals_label.text = t("best_deals")

    def _search(self, query: str) -> None:
        query = query.strip()
        if not query:
            return
        self.app.screens["search"].set_query(query)
        self.app.show_screen("search")

    def reload(self) -> None:
        from kivy.metrics import dp

        latest = self.app.repository.latest_sync_label()
        self.last_sync_label.text = f"{t('last_sync')}: {latest or t('offline_data')}"
        self.offer_list.clear_widgets()
        offers = self.app.repository.list_offers(limit=30)
        if not offers:
            self.offer_list.add_widget(make_label(text=t("no_offers"), size_hint_y=None, height=dp(44), color=MUTED))
            return
        for offer in offers:
            self.offer_list.add_widget(self.build_offer_card(offer, self.app.show_product))

    def sync_status_changed(self, statuses: dict[str, str]) -> None:
        if not statuses:
            self.status_label.text = ""
            return
        self.status_label.text = " | ".join(f"{store}: {status}" for store, status in statuses.items())
