"""First-class Prishtina merchant map screen."""

from __future__ import annotations

from datetime import UTC, datetime

from ofertaks.localization import t
from ofertaks.maps.osm import OverpassMerchantImporter
from ofertaks.maps.providers import OSM_STANDARD_PROVIDER
from ofertaks.maps.region import PRISHTINA_REGION
from ofertaks.maps.service import ALL_FOOD_FILTER, MAP_FILTER_TYPES, MapMerchantResult, MapService
from ofertaks.ui.screens.add_place import MERCHANT_TYPE_KEYS
from ofertaks.ui.theme import MUTED, add_card_background, make_label
from ofertaks.ui.widgets.map_view import MapSurface

try:
    from kivy.uix.screenmanager import Screen
except Exception:  # pragma: no cover
    class Screen:  # type: ignore[no-redef]
        pass


FILTER_LABEL_KEYS = {
    ALL_FOOD_FILTER: "all_food",
    "supermarkets": "supermarkets",
    "local_shops": "local_shops",
    "markets": "markets",
    "fruit_vegetables": "fruit_vegetables",
    "bakeries": "bakeries",
    "butchers_fish": "butchers_fish",
    "best_deals": "best_deals",
    "price_warnings": "price_warnings",
}

ASSESSMENT_LABEL_KEYS = {
    "EXCEPTIONAL_DEAL": "price_integrity_exceptional",
    "GOOD_DEAL": "price_integrity_good",
    "NORMAL_PRICE": "price_integrity_normal",
    "EXPENSIVE": "price_integrity_expensive",
    "VERY_EXPENSIVE": "price_integrity_very_expensive",
    "WEAK_PROMOTION": "price_integrity_weak_promotion",
    "INSUFFICIENT_HISTORY": "price_integrity_insufficient_history",
}


class MapScreen(Screen):
    def __init__(self, app, **kwargs):
        from kivy.metrics import dp
        from kivy.uix.boxlayout import BoxLayout
        from kivy.uix.button import Button
        from kivy.uix.floatlayout import FloatLayout
        from kivy.uix.scrollview import ScrollView
        from kivy.uix.togglebutton import ToggleButton

        super().__init__(**kwargs)
        self.app = app
        self.service = MapService(app.repository)
        self.selected_filter = ALL_FOOD_FILTER
        self.product_id: int | None = None
        self.product_name: str | None = None
        self.selected_merchant_id: str | None = None
        self.current_result: MapMerchantResult | None = None
        self._showing_legend = False
        self._filter_buttons: list[tuple[str, object]] = []
        layout = BoxLayout(orientation="vertical", spacing=dp(4), padding=(dp(6), dp(4), dp(6), dp(2)))
        header = BoxLayout(size_hint_y=None, height=dp(40), spacing=dp(6))
        self.title_label = make_label(text=t("map"), bold=True, font_size="20sp")
        self.refresh_button = Button(text=t("refresh_places"), size_hint_x=None, width=dp(112), font_size="11sp")
        self.refresh_button.bind(on_release=lambda *_: self._refresh_osm())
        self.legend_button = Button(text=t("legend"), size_hint_x=None, width=dp(58), font_size="11sp")
        self.legend_button.bind(on_release=lambda *_: self._toggle_legend())
        self.add_place_button = Button(text=t("add_place"), size_hint_x=None, width=dp(92), font_size="11sp")
        self.add_place_button.bind(on_release=lambda *_: self._open_add_place())
        header.add_widget(self.title_label)
        header.add_widget(self.refresh_button)
        header.add_widget(self.legend_button)
        header.add_widget(self.add_place_button)
        layout.add_widget(header)
        self.context_label = make_label(text="", size_hint_y=None, height=dp(22), color=MUTED, shorten=True)
        layout.add_widget(self.context_label)
        filter_scroll = ScrollView(do_scroll_y=False, do_scroll_x=True, size_hint_y=None, height=dp(38), bar_width=0)
        self.filter_row = BoxLayout(size_hint=(None, 1), spacing=dp(5))
        self.filter_row.bind(minimum_width=self.filter_row.setter("width"))
        filter_scroll.add_widget(self.filter_row)
        layout.add_widget(filter_scroll)
        self._toggle_type = ToggleButton
        self._build_filters()
        self.map_container = FloatLayout()
        self.map_surface = MapSurface(
            provider=OSM_STANDARD_PROVIDER,
            center=(PRISHTINA_REGION.center_latitude, PRISHTINA_REGION.center_longitude),
            zoom=PRISHTINA_REGION.default_zoom,
        )
        self.map_surface.on_viewport_changed = self._viewport_changed
        self.map_surface.on_marker_selected = self._merchant_selected
        self.map_container.add_widget(self.map_surface)
        self.card = BoxLayout(
            orientation="vertical",
            size_hint=(1, None),
            height=0,
            padding=dp(8),
            spacing=dp(3),
            pos_hint={"x": 0, "y": 0},
            opacity=0,
        )
        add_card_background(self.card, radius=6)
        self.card_title = make_label(size_hint_y=None, height=dp(24), bold=True, shorten=True)
        self.card_meta = make_label(size_hint_y=None, height=dp(20), color=MUTED, shorten=True)
        self.card_deals = make_label(size_hint_y=None, height=dp(48), font_size="11sp", color=MUTED)
        self.card_observation = make_label(size_hint_y=None, height=dp(24), color=MUTED, shorten=True)
        actions = BoxLayout(size_hint_y=None, height=dp(34), spacing=dp(5))
        self.update_button = Button(text=t("update_price"), font_size="11sp")
        self.update_button.bind(on_release=lambda *_: self._update_price())
        self.add_product_button = Button(text=t("add_product"), font_size="11sp")
        self.add_product_button.bind(on_release=lambda *_: self._add_product())
        self.directions_button = Button(text=t("directions"), font_size="11sp")
        self.directions_button.bind(on_release=lambda *_: self._directions())
        self.closed_button = Button(text=t("place_closed"), font_size="11sp")
        self.closed_button.bind(on_release=lambda *_: self._report("CLOSED"))
        for button in (self.update_button, self.add_product_button, self.directions_button, self.closed_button):
            actions.add_widget(button)
        self.card.add_widget(self.card_title)
        self.card.add_widget(self.card_meta)
        self.card.add_widget(self.card_deals)
        self.card.add_widget(self.card_observation)
        self.card.add_widget(actions)
        self.map_container.add_widget(self.card)
        layout.add_widget(self.map_container)
        self.attribution = make_label(
            text=OSM_STANDARD_PROVIDER.attribution,
            size_hint_y=None,
            height=dp(16),
            font_size="10sp",
            color=MUTED,
            halign="right",
        )
        layout.add_widget(self.attribution)
        self.add_widget(layout)
        self.translate()

    def translate(self) -> None:
        self.title_label.text = t("map")
        self.refresh_button.text = t("refresh_places")
        self.legend_button.text = t("legend")
        self.add_place_button.text = t("add_place")
        self.update_button.text = t("update_price")
        self.add_product_button.text = t("add_product")
        self.directions_button.text = t("directions")
        self.closed_button.text = t("place_closed")
        self._build_filters()
        self._render_context()
        if self.current_result:
            self._show_card(self.current_result)

    def open_context(
        self,
        *,
        product_id: int | None = None,
        product_name: str | None = None,
        merchant_id: str | None = None,
        filter_id: str | None = None,
    ) -> None:
        self.product_id = product_id
        self.product_name = product_name
        if filter_id in MAP_FILTER_TYPES:
            self.selected_filter = filter_id
        self.selected_merchant_id = merchant_id
        if merchant_id:
            merchant = self.app.repository.get_merchant(merchant_id)
            if merchant:
                self.map_surface.set_view(merchant["latitude"], merchant["longitude"])
        self._render_context()
        self._viewport_changed(self.map_surface.visible_bbox())

    def reload(self) -> None:
        self._viewport_changed(self.map_surface.visible_bbox())

    def _build_filters(self) -> None:
        from kivy.metrics import dp

        self.filter_row.clear_widgets()
        self._filter_buttons = []
        group = f"map-filter-{id(self)}"
        for filter_id in FILTER_LABEL_KEYS:
            label = t(FILTER_LABEL_KEYS[filter_id])
            button = self._toggle_type(
                text=label,
                group=group,
                state="down" if filter_id == self.selected_filter else "normal",
                size_hint=(None, 1),
                width=dp(max(80, len(label) * 7 + 22)),
                font_size="11sp",
            )
            button.bind(state=lambda control, state, value=filter_id: self._filter_changed(value, state))
            self.filter_row.add_widget(button)
            self._filter_buttons.append((filter_id, button))

    def _filter_changed(self, filter_id: str, state: str) -> None:
        if state != "down" or filter_id == self.selected_filter:
            return
        self.selected_filter = filter_id
        self._viewport_changed(self.map_surface.visible_bbox())

    def _viewport_changed(self, bbox: tuple[float, float, float, float]) -> None:
        results = self.service.viewport_merchants(bbox, self.selected_filter, self.product_id)
        self.map_surface.set_markers(results)
        if self.selected_merchant_id:
            selected = next((result for result in results if result.merchant["id"] == self.selected_merchant_id), None)
            self.selected_merchant_id = None
            if selected:
                self._merchant_selected(selected)

    def _merchant_selected(self, result: MapMerchantResult) -> None:
        self.current_result = result
        self._show_card(result)

    def _show_card(self, result: MapMerchantResult) -> None:
        from kivy.metrics import dp

        merchant = result.merchant
        chain = next((row["name"] for row in self.app.repository.chains() if row["id"] == merchant.get("chain_id")), None)
        self.card_title.text = merchant["name"]
        source_key = {
            "OSM": "source_openstreetmap",
            "COMMUNITY": "community",
            "MERCHANT": "origin_source_merchant",
            "CHAIN_OFFICIAL": "origin_source_official_data",
        }.get(merchant.get("source_type"), "origin_source_unknown")
        type_key = MERCHANT_TYPE_KEYS.get(merchant["merchant_type"], "merchant_type")
        verification = merchant.get("verification_status")
        verified = verification in {"MERCHANT_VERIFIED", "ADMIN_VERIFIED", "COMMUNITY_CONFIRMED"}
        self.card_meta.text = " | ".join(
            part for part in [t(type_key), chain, t(source_key), t("verified" if verified else "unverified")]
            if part
        )
        observation = result.observation
        summary = result.deal_summary
        if summary and summary.best_deals:
            counts = [
                f"{summary.exceptional_deal_count} {t('exceptional_prices')}"
                if summary.exceptional_deal_count
                else "",
                f"{summary.good_deal_count} {t('good_prices')}" if summary.good_deal_count else "",
                f"{summary.price_integrity_warning_count} {t('price_warnings')}"
                if summary.price_integrity_warning_count
                else "",
            ]
            headline = " | ".join(item for item in counts if item) or t("no_recent_product_information")
            examples = []
            for deal in summary.best_deals[:2]:
                label = t(ASSESSMENT_LABEL_KEYS.get(deal.assessment.primary_status, "price_integrity_normal"))
                nearby = f" | {t('best_nearby_price')}" if deal.best_nearby else ""
                examples.append(f"{deal.raw_name}: {deal.price:.2f} EUR | {label}{nearby}")
            self.card_deals.text = "\n".join([headline, *examples])
        else:
            self.card_deals.text = t("no_current_deals")
        if observation:
            detail = observation["raw_name"]
            if observation.get("price") is not None:
                detail += f" | {float(observation['price']):.2f} EUR"
            origin = observation.get("origin_country")
            if origin:
                detail += f" | {t('origin')}: {origin}"
            detail += f" | {t(f'availability_{result.availability.casefold()}')}"
        else:
            detail = t("no_recent_product_information") if self.product_id else t("no_recent_observations")
        self.card_observation.text = detail
        self.card.height = dp(184)
        self.card.opacity = 1

    def _render_context(self) -> None:
        if self._showing_legend:
            self.context_label.text = " | ".join(
                (
                    f"SM {t('map_type_supermarket')}",
                    f"FV {t('map_type_fruit_vegetable')}",
                    f"MK {t('map_type_market')}",
                    f"BK {t('map_type_bakery')}",
                    f"BT {t('map_type_butcher')}",
                    f"FS {t('map_type_fish')}",
                )
            )
            return
        self.context_label.text = (
            f"{t('showing_on_map')}: {self.product_name}" if self.product_name else PRISHTINA_REGION.city
        )

    def _toggle_legend(self) -> None:
        self._showing_legend = not self._showing_legend
        self._render_context()

    def _open_add_place(self) -> None:
        add_place = self.app.screens["add_place"]
        add_place.set_location(self.map_surface.center_latitude, self.map_surface.center_longitude)
        self.app.show_screen("add_place")

    def _update_price(self) -> None:
        if not self.current_result:
            return
        merchant = self.current_result.merchant
        self.app.screens["price_update"].set_context(
            merchant=merchant,
            product_id=self.product_id,
            product_name=self.product_name,
            mode="update_price",
            return_screen="map",
        )
        self.app.show_screen("price_update")

    def _add_product(self) -> None:
        if not self.current_result:
            return
        merchant = self.current_result.merchant
        self.app.screens["price_update"].set_context(
            merchant=merchant,
            product_id=self.product_id,
            product_name=self.product_name,
            mode="add_product",
            return_screen="map",
        )
        self.app.show_screen("price_update")

    def _directions(self) -> None:
        if self.current_result:
            self.card_observation.text = t("directions_unavailable")

    def _report(self, report_type: str) -> None:
        if not self.current_result:
            return
        self.service.report_merchant(self.current_result.merchant["id"], report_type)
        self.card_observation.text = t("report_saved_locally")

    def _refresh_osm(self) -> None:
        self.refresh_button.disabled = True
        self.context_label.text = t("refreshing_places")
        importer = OverpassMerchantImporter(self.app.repository, PRISHTINA_REGION)
        future = self.app.executor.submit(importer.import_region)

        def complete(_future) -> None:
            from kivy.clock import Clock

            try:
                result = future.result()
                message = f"{t('places_updated')}: {result.imported + result.updated}"
            except Exception:
                message = t("places_refresh_failed")

            def apply(_dt) -> None:
                self.refresh_button.disabled = False
                self.context_label.text = message
                self._viewport_changed(self.map_surface.visible_bbox())

            Clock.schedule_once(apply, 0)

        future.add_done_callback(complete)
