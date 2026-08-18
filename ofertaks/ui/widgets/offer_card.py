"""Offer card widget."""

from __future__ import annotations

from ofertaks.localization import t
from ofertaks.parsing.unit_parser import format_quantity, format_unit_price
from ofertaks.services.comparison_service import score_offer
from ofertaks.ui.theme import ACCENT, MUTED, add_card_background, make_label


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
            height=dp(142),
        )
        add_card_background(card, radius=6)
        title = offer.raw_name
        quantity = format_quantity(offer.quantity, offer.unit)
        if quantity:
            title = f"{title}  |  {quantity}"
        card.add_widget(
            make_label(
                text=title,
                bold=True,
                size_hint_y=None,
                height=dp(30),
                shorten=True,
                shorten_from="right",
            )
        )
        card.add_widget(
            make_label(
                text=offer.store_name.upper(),
                size_hint_y=None,
                height=dp(20),
                color=MUTED,
            )
        )
        price_line = _money(offer.offer_price)
        if offer.normal_price:
            price_line += f"  was {_money(offer.normal_price)}"
        if offer.discount_percent:
            price_line += f"  -{offer.discount_percent:.0f}%"
        card.add_widget(
            make_label(
                text=price_line,
                size_hint_y=None,
                height=dp(24),
            )
        )
        unit_price = format_unit_price(offer.unit_price, offer.unit)
        deal = score_offer(offer)
        footer = "  |  ".join(part for part in [unit_price, t(deal.label_key)] if part)
        row = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(34), spacing=dp(8))
        row.add_widget(
            make_label(
                text=footer,
                color=ACCENT,
            )
        )
        if on_details:
            button = Button(text=t("details"), size_hint_x=None, width=dp(86))
            button.bind(on_release=lambda *_: on_details(offer))
            row.add_widget(button)
        card.add_widget(row)
        return card
