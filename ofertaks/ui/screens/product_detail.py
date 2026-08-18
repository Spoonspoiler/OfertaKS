"""Useful product detail screen with current prices, history, and provenance."""

from __future__ import annotations

from ofertaks.community.observations import origin_display_for_offer
from ofertaks.localization import t
from ofertaks.parsing.unit_parser import format_quantity, format_unit_price
from ofertaks.services.comparison_service import classify_price_status
from ofertaks.services.history_service import HistoryService
from ofertaks.services.price_integrity import PriceIntegrityService
from ofertaks.ui.theme import MUTED, PRICE_STATUS_COLORS, bind_scroll_content_width, make_label, make_screen_layout
from ofertaks.utils.categories import category_label_key

try:
    from kivy.uix.screenmanager import Screen
except Exception:  # pragma: no cover
    class Screen:  # type: ignore[no-redef]
        pass


class PriceHistoryGraph:
    def __init__(self, **kwargs):
        from kivy.graphics import Color, Ellipse, Line
        from kivy.uix.widget import Widget

        class _Graph(Widget):
            def __init__(self, **inner_kwargs):
                super().__init__(**inner_kwargs)
                self.observations = []
                self.bind(pos=self._draw, size=self._draw)

            def set_observations(self, observations):
                self.observations = [row for row in observations if row.get("price") is not None]
                self._draw()

            def _draw(self, *_args):
                self.canvas.clear()
                with self.canvas:
                    Color(0.82, 0.85, 0.84, 1)
                    Line(rectangle=(self.x, self.y, self.width, self.height), width=1)
                    if not self.observations:
                        return
                    prices = [float(row["price"]) for row in self.observations]
                    low = min(prices)
                    high = max(prices)
                    span = high - low or 1
                    coords = []
                    count = len(prices)
                    for idx, price in enumerate(prices):
                        x = self.center_x if count == 1 else self.x + (idx / (count - 1)) * self.width
                        y = self.y + ((price - low) / span) * self.height
                        coords.extend([x, y])
                    Color(0.10, 0.46, 0.34, 1)
                    if len(coords) >= 4:
                        Line(points=coords, width=2)
                    for index, row in enumerate(self.observations):
                        x, y = coords[index * 2 : index * 2 + 2]
                        if row.get("observation_context") in {"PROMOTION", "CLEARANCE"}:
                            Color(0.90, 0.47, 0.12, 1)
                        else:
                            Color(0.10, 0.46, 0.34, 1)
                        Ellipse(pos=(x - 4, y - 4), size=(8, 8))

        self.widget = _Graph(**kwargs)


class ProductDetailScreen(Screen):
    def __init__(self, app, **kwargs):
        from kivy.metrics import dp
        from kivy.uix.boxlayout import BoxLayout
        from kivy.uix.button import Button
        from kivy.uix.scrollview import ScrollView

        super().__init__(**kwargs)
        self.app = app
        self.offer = None
        frame, layout = make_screen_layout()
        self.back_button = Button(text=t("back"), size_hint_y=None, height=dp(40))
        self.back_button.bind(on_release=lambda *_: self.app.show_screen("offers"))
        layout.add_widget(self.back_button)
        scroll = ScrollView()
        content = BoxLayout(orientation="vertical", spacing=dp(7), size_hint_y=None, padding=(0, 0, 0, dp(8)))
        content.bind(minimum_height=content.setter("height"))
        bind_scroll_content_width(scroll, content)
        scroll.add_widget(content)
        layout.add_widget(scroll)

        self.title = make_label(size_hint_y=None, height=dp(36), bold=True, font_size="22sp")
        self.subtitle = make_label(size_hint_y=None, height=dp(24), color=MUTED)
        self.current_prices_label = make_label(
            text=t("current_prices"), size_hint_y=None, height=dp(28), bold=True
        )
        self.price_rows = make_label(halign="left", valign="top", use_height=False, size_hint_y=None, height=dp(40))
        self.status_heading = make_label(
            text=t("price_status"), size_hint_y=None, height=dp(26), bold=True
        )
        self.status_label = make_label(size_hint_y=None, height=dp(24), bold=True)
        self.origin_heading = make_label(text=t("origin"), size_hint_y=None, height=dp(26), bold=True)
        self.origin_label = make_label(size_hint_y=None, height=dp(24))
        self.origin_explanation = make_label(size_hint_y=None, height=dp(24), color=MUTED)
        self.history_label = make_label(
            text=t("price_history"), size_hint_y=None, height=dp(30), bold=True
        )
        self.history_explanation = make_label(size_hint_y=None, height=dp(24), color=MUTED)
        self.graph_legend = make_label(size_hint_y=None, height=dp(20), color=MUTED, font_size="11sp")
        graph_wrapper = PriceHistoryGraph(size_hint_y=None, height=dp(150))
        self.graph = graph_wrapper.widget
        self.update_button = Button(text=t("update_price"), size_hint_y=None, height=dp(46))
        self.update_button.bind(on_release=lambda *_: self._open_price_update())
        self.scan_button = Button(text=t("scan_product"), size_hint_y=None, height=dp(42))
        self.scan_button.bind(on_release=lambda *_: self.app.show_barcode_scan(return_screen="product_detail"))
        self.map_button = Button(text=t("show_on_map"), size_hint_y=None, height=dp(42))
        self.map_button.bind(on_release=lambda *_: self._show_on_map())
        for widget in (
            self.title,
            self.subtitle,
            self.current_prices_label,
            self.price_rows,
            self.status_heading,
            self.status_label,
            self.origin_heading,
            self.origin_label,
            self.origin_explanation,
            self.history_label,
            self.history_explanation,
            self.graph_legend,
            self.graph,
            self.update_button,
            self.scan_button,
            self.map_button,
        ):
            content.add_widget(widget)
        self.add_widget(frame)

    def translate(self) -> None:
        self.back_button.text = t("back")
        self.current_prices_label.text = t("current_prices")
        self.status_heading.text = t("price_status")
        self.origin_heading.text = t("origin")
        self.history_label.text = t("price_history")
        self.graph_legend.text = f"{t('price_graph_regular')} | {t('price_graph_promotion')}"
        self.update_button.text = t("update_price")
        self.scan_button.text = t("scan_product")
        self.map_button.text = t("show_on_map")

    def set_offer(self, offer) -> None:
        self.offer = offer
        self.reload()

    def reload(self) -> None:
        if not self.offer:
            return
        offer = self.offer
        self.title.text = offer.raw_name
        meta = [t(category_label_key(offer.category)), format_quantity(offer.quantity, offer.unit)]
        self.subtitle.text = " | ".join(part for part in meta if part)
        product_id = self.app.repository.find_product_id_for_offer(offer)
        comparable = []
        history = None
        observations = []
        assessment = None
        if product_id is not None:
            comparable = self.app.repository.offers_for_product(product_id)
            history = HistoryService(self.app.repository).stats_for_product(product_id)
            observations = self.app.repository.origin_observations_for_offer(offer)
            promotions = self.app.repository.active_promotion_events(product_id, merchant_id=offer.merchant_id)
            if not promotions and offer.chain_id:
                promotions = self.app.repository.active_promotion_events(product_id, chain_id=offer.chain_id)
            assessment = PriceIntegrityService(self.app.repository).assess(
                product_id,
                offer.offer_price,
                current_unit_price=offer.unit_price,
                quantity=offer.quantity,
                unit=offer.unit,
                promotion=promotions[0] if promotions else None,
                observed_at=offer.scraped_at,
            )
        if not comparable:
            comparable = self.app.repository.search_offers(offer.raw_name, limit=12)
        if comparable:
            lines = []
            for item in comparable[:10]:
                unit = format_unit_price(item.unit_price, item.unit)
                suffix = f" | {unit}" if unit else ""
                lines.append(f"{item.store_name}: {item.offer_price:.2f} EUR{suffix}")
            self.price_rows.text = "\n".join(lines)
            from kivy.metrics import dp

            self.price_rows.height = dp(max(28, 24 * len(lines)))
        else:
            self.price_rows.text = t("no_current_prices")
            from kivy.metrics import dp

            self.price_rows.height = dp(30)
        status = classify_price_status(offer.offer_price, history)
        integrity_key = {
            "EXCEPTIONAL_DEAL": "price_integrity_exceptional",
            "GOOD_DEAL": "price_integrity_good",
            "NORMAL_PRICE": "price_integrity_normal",
            "EXPENSIVE": "price_integrity_expensive",
            "VERY_EXPENSIVE": "price_integrity_very_expensive",
            "WEAK_PROMOTION": "price_integrity_weak_promotion",
            "INSUFFICIENT_HISTORY": "price_integrity_insufficient_history",
        }
        integrity_color = {
            "EXCEPTIONAL_DEAL": "exceptional",
            "GOOD_DEAL": "cheap",
            "NORMAL_PRICE": "neutral",
            "EXPENSIVE": "expensive",
            "VERY_EXPENSIVE": "high",
            "WEAK_PROMOTION": "expensive",
            "INSUFFICIENT_HISTORY": "neutral",
        }
        self.status_label.text = t(integrity_key.get(assessment.primary_status if assessment else "", status.key))
        self.status_label.color = PRICE_STATUS_COLORS[
            integrity_color.get(assessment.primary_status if assessment else "", status.color_key)
        ]
        origin = origin_display_for_offer(offer, observations)
        if origin.country:
            location = ", ".join(part for part in [origin.country, origin.region] if part)
            self.origin_label.text = " | ".join(
                [location, t(origin.source_key), t(origin.confidence_key)]
            )
        else:
            self.origin_label.text = t("origin_unknown")
        self.origin_explanation.text = t(origin.explanation_key)
        if assessment and assessment.reference_price is not None:
            reference = f"{assessment.reference_price:.2f} EUR"
            difference = f"{assessment.difference_percent:+.0f}%" if assessment.difference_percent is not None else ""
            self.history_explanation.text = " | ".join(
                part
                for part in [t("price_reference"), reference, difference, t(assessment.explanation_key)]
                if part
            )
        elif history and history.enough_history:
            self.history_explanation.text = t("price_history_explanation")
        else:
            self.history_explanation.text = t("price_integrity_insufficient_history")
        self.graph.set_observations(
            self.app.repository.historical_prices(product_id) if product_id is not None else []
        )

    def _open_price_update(self) -> None:
        if not self.offer:
            return
        update = self.app.screens["price_update"]
        update.set_offer(self.offer)
        self.app.show_screen("price_update")

    def _show_on_map(self) -> None:
        if not self.offer:
            return
        self.app.show_map(
            product_id=self.app.repository.find_product_id_for_offer(self.offer),
            product_name=self.offer.raw_name,
            merchant_id=self.offer.merchant_id,
        )
