"""Offer card widget."""

from __future__ import annotations

from ofertaks.community.observations import origin_display_for_offer
from ofertaks.localization import t
from ofertaks.parsing.unit_parser import format_quantity, format_unit_price
from ofertaks.services.comparison_service import classify_price_status
from ofertaks.services.history_service import HistoryService
from ofertaks.ui.theme import (
    CATEGORY_ART_COLORS,
    MUTED,
    PRICE_STATUS_COLORS,
    add_card_background,
    add_fill_background,
    make_label,
)
from ofertaks.utils.categories import category_label_key


def _money(value: float | None) -> str:
    return "" if value is None else f"{value:.2f} EUR"


class OfferCardMixin:
    def build_offer_card(self, offer, on_details=None):
        from kivy.metrics import dp
        from kivy.uix.boxlayout import BoxLayout
        from kivy.uix.button import Button

        card = BoxLayout(
            orientation="vertical",
            spacing=dp(4),
            padding=dp(10),
            size_hint_y=None,
            height=dp(178),
        )
        add_card_background(card, radius=6)
        header = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(68), spacing=dp(10))
        header.add_widget(self._build_product_artwork(offer))
        details = BoxLayout(orientation="vertical", spacing=dp(2))
        details.add_widget(
            make_label(
                text=offer.raw_name,
                bold=True,
                size_hint_y=None,
                height=dp(26),
                shorten=True,
                shorten_from="right",
            )
        )
        quantity = format_quantity(offer.quantity, offer.unit)
        category = t(category_label_key(offer.category))
        meta = " | ".join(part for part in [offer.store_name.upper(), category, quantity] if part)
        details.add_widget(
            make_label(text=meta, size_hint_y=None, height=dp(20), color=MUTED, shorten=True)
        )
        details.add_widget(make_label(text="", size_hint_y=None, height=dp(18)))
        header.add_widget(details)
        card.add_widget(header)

        history, origin = self._offer_context(offer)
        status = classify_price_status(offer.offer_price, history)
        card.add_widget(
            make_label(
                text=f"{t('current_price')}: {_money(offer.offer_price)}",
                size_hint_y=None,
                height=dp(22),
                bold=True,
            )
        )
        previous = ""
        if offer.normal_price:
            previous = f"{t('previous_price')}: {_money(offer.normal_price)}"
        if offer.discount_percent:
            previous = " | ".join(
                part
                for part in [previous, f"{t('discount')}: -{offer.discount_percent:.0f}%"]
                if part
            )
        card.add_widget(
            make_label(
                text=previous,
                size_hint_y=None,
                height=dp(18),
                color=MUTED,
            )
        )
        unit_price = format_unit_price(offer.unit_price, offer.unit)
        origin_text = ""
        if origin.country:
            location = ", ".join(part for part in [origin.country, origin.region] if part)
            origin_text = " | ".join(
                [
                    f"{t('origin')}: {location}",
                    t(origin.source_key),
                    t(origin.confidence_key),
                ]
            )
        card.add_widget(
            make_label(
                text=origin_text,
                size_hint_y=None,
                height=dp(18),
                color=MUTED,
                shorten=True,
            )
        )
        row = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(34), spacing=dp(8))
        badge = BoxLayout(size_hint=(None, 1), width=dp(168), padding=dp(4))
        add_fill_background(badge, PRICE_STATUS_COLORS[status.color_key], radius=4)
        badge.add_widget(
            make_label(
                text=t(status.key),
                halign="center",
                valign="middle",
                color=(1, 1, 1, 1),
                bold=True,
                font_size="11sp",
            )
        )
        row.add_widget(badge)
        row.add_widget(
            make_label(
                text=unit_price,
                color=MUTED,
            )
        )
        if on_details:
            button = Button(text=t("details"), size_hint_x=None, width=dp(86))
            button.bind(on_release=lambda *_: on_details(offer))
            row.add_widget(button)
        card.add_widget(row)
        return card

    def _offer_context(self, offer):
        cache = getattr(self, "_offer_context_cache", None)
        if cache is None:
            cache = {}
            self._offer_context_cache = cache
        key = (offer.store_id, offer.raw_name, offer.normalized_name)
        if key in cache:
            return cache[key]
        history = None
        observations = []
        repository = getattr(getattr(self, "app", None), "repository", None)
        if repository is not None:
            product_id = repository.find_product_id_for_offer(offer)
            if product_id is not None:
                history = HistoryService(repository).stats_for_product(product_id)
            observations = repository.origin_observations_for_offer(offer)
        context = (history, origin_display_for_offer(offer, observations))
        cache[key] = context
        return context

    def _build_product_artwork(self, offer):
        from kivy.metrics import dp
        from kivy.uix.boxlayout import BoxLayout

        if offer.image_url:
            from kivy.uix.image import AsyncImage

            return AsyncImage(
                source=offer.image_url,
                size_hint=(None, None),
                size=(dp(68), dp(68)),
                fit_mode="contain",
            )
        artwork = BoxLayout(size_hint=(None, None), size=(dp(68), dp(68)), padding=dp(5))
        add_fill_background(
            artwork,
            CATEGORY_ART_COLORS.get(offer.category, CATEGORY_ART_COLORS["OTHER_FOOD"]),
            radius=5,
        )
        artwork.add_widget(
            make_label(
                text=t(category_label_key(offer.category)),
                halign="center",
                valign="middle",
                color=(1, 1, 1, 1),
                font_size="11sp",
            )
        )
        return artwork
