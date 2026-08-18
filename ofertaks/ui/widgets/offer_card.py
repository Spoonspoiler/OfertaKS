"""Offer card widget."""

from __future__ import annotations

from ofertaks.app.localization import t
from ofertaks.parsing.unit_parser import format_quantity, format_unit_price
from ofertaks.services.comparison_service import score_offer


def _money(value: float | None) -> str:
    return "" if value is None else f"{value:.2f} EUR"


class OfferCardMixin:
    def build_offer_card(self, offer, on_details=None):
        from kivy.metrics import dp
        from kivy.uix.boxlayout import BoxLayout
        from kivy.uix.button import Button
        from kivy.uix.label import Label

        card = BoxLayout(
            orientation="vertical",
            spacing=dp(4),
            padding=dp(10),
            size_hint_y=None,
            height=dp(134),
        )
        card.canvas.before.clear()
        title = offer.raw_name
        quantity = format_quantity(offer.quantity, offer.unit)
        if quantity:
            title = f"{title}  |  {quantity}"
        card.add_widget(
            Label(
                text=title,
                bold=True,
                size_hint_y=None,
                height=dp(28),
                halign="left",
                valign="middle",
                text_size=(0, None),
                shorten=True,
                shorten_from="right",
            )
        )
        card.add_widget(
            Label(
                text=offer.store_name.upper(),
                size_hint_y=None,
                height=dp(20),
                halign="left",
                valign="middle",
                text_size=(0, None),
                color=(0.22, 0.31, 0.36, 1),
            )
        )
        price_line = _money(offer.offer_price)
        if offer.normal_price:
            price_line += f"  was {_money(offer.normal_price)}"
        if offer.discount_percent:
            price_line += f"  -{offer.discount_percent:.0f}%"
        card.add_widget(
            Label(
                text=price_line,
                size_hint_y=None,
                height=dp(24),
                halign="left",
                valign="middle",
                text_size=(0, None),
            )
        )
        unit_price = format_unit_price(offer.unit_price, offer.unit)
        deal = score_offer(offer)
        footer = "  |  ".join(part for part in [unit_price, t(deal.label_key)] if part)
        row = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(34), spacing=dp(8))
        row.add_widget(
            Label(
                text=footer,
                halign="left",
                valign="middle",
                text_size=(0, None),
                color=(0.10, 0.46, 0.34, 1),
            )
        )
        if on_details:
            button = Button(text="Details", size_hint_x=None, width=dp(86))
            button.bind(on_release=lambda *_: on_details(offer))
            row.add_widget(button)
        card.add_widget(row)
        return card
