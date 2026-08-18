"""Offers screen."""

from __future__ import annotations

from ofertaks.localization import t
from ofertaks.ui.theme import MUTED, bind_scroll_content_width, make_label, make_screen_layout
from ofertaks.ui.widgets.offer_card import OfferCardMixin
from ofertaks.utils.categories import (
    BAKERY,
    DAIRY,
    DRINK,
    FROZEN,
    FRUIT_VEGETABLE,
    MEAT,
    OTHER_FOOD,
    PANTRY,
    SNACKS,
    category_label_key,
)

try:
    from kivy.uix.screenmanager import Screen
except Exception:  # pragma: no cover
    class Screen:  # type: ignore[no-redef]
        pass


class OffersScreen(Screen, OfferCardMixin):
    def __init__(self, app, **kwargs):
        from kivy.metrics import dp
        from kivy.uix.boxlayout import BoxLayout
        from kivy.uix.scrollview import ScrollView
        from kivy.uix.spinner import Spinner

        super().__init__(**kwargs)
        self.app = app
        self.selected_store_id: str | None = None
        self.selected_merchant_id: str | None = None
        self.selected_chain_id: str | None = None
        self.selected_merchant_name: str | None = None
        self.selected_category: str | None = None
        self.selected_sort = "best"
        frame, layout = make_screen_layout()
        self.title_label = make_label(text=t("offers"), size_hint_y=None, height=dp(36), bold=True, font_size="22sp")
        layout.add_widget(self.title_label)
        filters = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(8))
        self.store_spinner = Spinner()
        self.sort_spinner = Spinner()
        filters.add_widget(self.store_spinner)
        filters.add_widget(self.sort_spinner)
        layout.add_widget(filters)
        self.category_scroll = ScrollView(
            do_scroll_y=False,
            do_scroll_x=True,
            size_hint_y=None,
            height=dp(42),
            bar_width=0,
        )
        self.category_row = BoxLayout(size_hint=(None, 1), spacing=dp(6))
        self.category_row.bind(minimum_width=self.category_row.setter("width"))
        self.category_scroll.add_widget(self.category_row)
        layout.add_widget(self.category_scroll)
        scroll = ScrollView()
        self.offer_list = BoxLayout(orientation="vertical", spacing=dp(8), size_hint_y=None)
        self.offer_list.bind(minimum_height=self.offer_list.setter("height"))
        bind_scroll_content_width(scroll, self.offer_list)
        scroll.add_widget(self.offer_list)
        layout.add_widget(scroll)
        self.add_widget(frame)
        self.translate()
        self.store_spinner.bind(text=self._store_changed)
        self.sort_spinner.bind(text=self._sort_changed)

    def translate(self) -> None:
        self.title_label.text = t("offers")
        self.store_labels = {
            t("all"): None,
            "Viva Fresh": "viva_fresh",
            "Interex": "interex",
            "ETC": "etc",
        }
        self.sort_labels = {
            t("sort_best_deals"): "best",
            t("sort_lowest_price"): "lowest",
            t("largest_discount"): "discount",
            t("newest"): "newest",
            t("price_per_unit"): "unit",
        }
        self.store_spinner.values = tuple(self.store_labels)
        self.sort_spinner.values = tuple(self.sort_labels)
        self.store_spinner.text = next(
            label for label, store_id in self.store_labels.items() if store_id == self.selected_store_id
        )
        self.sort_spinner.text = next(
            label for label, sort in self.sort_labels.items() if sort == self.selected_sort
        )
        self.category_labels = {
            t("all"): None,
            t(category_label_key(FRUIT_VEGETABLE)): FRUIT_VEGETABLE,
            t(category_label_key(DAIRY)): DAIRY,
            t(category_label_key(MEAT)): MEAT,
            t(category_label_key(PANTRY)): PANTRY,
            t(category_label_key(DRINK)): DRINK,
            t(category_label_key(BAKERY)): BAKERY,
            t(category_label_key(FROZEN)): FROZEN,
            t(category_label_key(SNACKS)): SNACKS,
            t(category_label_key(OTHER_FOOD)): OTHER_FOOD,
        }
        self._build_category_filters()

    def _build_category_filters(self) -> None:
        from kivy.metrics import dp
        from kivy.uix.togglebutton import ToggleButton

        self.category_row.clear_widgets()
        group = f"offer-categories-{id(self)}"
        for label, category in self.category_labels.items():
            button = ToggleButton(
                text=label,
                group=group,
                state="down" if category == self.selected_category else "normal",
                size_hint=(None, 1),
                width=dp(max(82, len(label) * 8 + 24)),
            )
            button.bind(
                state=lambda control, state, value=category: self._category_changed(
                    value, state
                )
            )
            self.category_row.add_widget(button)

    def _store_changed(self, _spinner, text: str) -> None:
        self.selected_store_id = self.store_labels.get(text)
        self.selected_merchant_id = None
        self.selected_chain_id = None
        self.selected_merchant_name = None
        self.reload()

    def show_merchant(self, merchant: dict) -> None:
        """Show only facts attributed to the selected map merchant."""

        self.selected_store_id = None
        self.selected_merchant_id = merchant["id"]
        self.selected_chain_id = None
        has_direct_offers = bool(self.app.repository.list_offers(merchant_id=merchant["id"], limit=1))
        if merchant.get("chain_id") and not has_direct_offers:
            self.selected_merchant_id = None
            self.selected_chain_id = merchant["chain_id"]
            self.selected_merchant_name = f"{merchant['name']} ({t('chain_offers')})"
        else:
            self.selected_merchant_name = merchant["name"]
        self.store_spinner.text = t("all")
        self.reload()

    def clear_merchant_context(self) -> None:
        """Return to the catalog while preserving the user's regular filters."""

        self.selected_merchant_id = None
        self.selected_chain_id = None
        self.selected_merchant_name = None

    def _sort_changed(self, _spinner, text: str) -> None:
        self.selected_sort = self.sort_labels.get(text, "best")
        self.reload()

    def _category_changed(self, category: str | None, state: str) -> None:
        if state != "down" or category == self.selected_category:
            return
        self.selected_category = category
        self.reload()

    def reload(self) -> None:
        from kivy.metrics import dp

        self._offer_context_cache = {}
        offers = self.app.repository.list_offers(
            store_id=self.selected_store_id,
            merchant_id=self.selected_merchant_id,
            chain_id=self.selected_chain_id,
            category=self.selected_category,
            sort=self.selected_sort,
            limit=250,
        )
        self.title_label.text = (
            f"{t('offers')}: {self.selected_merchant_name}"
            if self.selected_merchant_name
            else t("offers")
        )
        self.offer_list.clear_widgets()
        if not offers:
            self.offer_list.add_widget(make_label(text=t("no_offers"), size_hint_y=None, height=dp(44), color=MUTED))
            return
        for offer in offers:
            self.offer_list.add_widget(self.build_offer_card(offer, self.app.show_product))
