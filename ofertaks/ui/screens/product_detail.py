"""Product detail screen with lightweight canvas history graph."""

from __future__ import annotations

from ofertaks.app.localization import t
from ofertaks.parsing.unit_parser import format_quantity, format_unit_price

try:
    from kivy.uix.screenmanager import Screen
except Exception:  # pragma: no cover
    class Screen:  # type: ignore[no-redef]
        pass


class PriceHistoryGraph:
    def __init__(self, **kwargs):
        from kivy.graphics import Color, Line
        from kivy.uix.widget import Widget

        class _Graph(Widget):
            def __init__(self, **inner_kwargs):
                super().__init__(**inner_kwargs)
                self.points = []
                self.bind(pos=self._draw, size=self._draw)

            def set_prices(self, prices):
                self.points = list(prices)
                self._draw()

            def _draw(self, *_args):
                self.canvas.clear()
                with self.canvas:
                    Color(0.82, 0.85, 0.84, 1)
                    Line(rectangle=(self.x, self.y, self.width, self.height), width=1)
                    if len(self.points) < 2:
                        return
                    low = min(self.points)
                    high = max(self.points)
                    span = high - low or 1
                    coords = []
                    for idx, price in enumerate(self.points):
                        x = self.x + (idx / (len(self.points) - 1)) * self.width
                        y = self.y + ((price - low) / span) * self.height
                        coords.extend([x, y])
                    Color(0.10, 0.46, 0.34, 1)
                    Line(points=coords, width=2)

        self.widget = _Graph(**kwargs)


class ProductDetailScreen(Screen):
    def __init__(self, app, **kwargs):
        from kivy.metrics import dp
        from kivy.uix.boxlayout import BoxLayout
        from kivy.uix.button import Button
        from kivy.uix.label import Label

        super().__init__(**kwargs)
        self.app = app
        self.offer = None
        layout = BoxLayout(orientation="vertical", padding=dp(12), spacing=dp(8))
        back = Button(text="<", size_hint=(None, None), width=dp(48), height=dp(42))
        back.bind(on_release=lambda *_: self.app.show_screen("offers"))
        layout.add_widget(back)
        self.title = Label(size_hint_y=None, height=dp(38), bold=True, font_size="22sp")
        self.subtitle = Label(size_hint_y=None, height=dp(28))
        self.price_rows = Label(halign="left", valign="top", text_size=(0, None))
        graph_wrapper = PriceHistoryGraph(size_hint_y=None, height=dp(150))
        self.graph = graph_wrapper.widget
        layout.add_widget(self.title)
        layout.add_widget(self.subtitle)
        layout.add_widget(self.price_rows)
        layout.add_widget(Label(text=t("price_history"), size_hint_y=None, height=dp(30), bold=True))
        layout.add_widget(self.graph)
        self.add_widget(layout)

    def set_offer(self, offer) -> None:
        self.offer = offer
        self.reload()

    def reload(self) -> None:
        if not self.offer:
            return
        offer = self.offer
        self.title.text = offer.raw_name
        self.subtitle.text = format_quantity(offer.quantity, offer.unit)
        comparable = self.app.repository.search_offers(offer.raw_name, limit=30)
        lines = []
        for item in comparable:
            unit = format_unit_price(item.unit_price, item.unit)
            suffix = f"  ({unit})" if unit else ""
            lines.append(f"{item.store_name:<12} {item.offer_price:.2f} EUR{suffix}")
        self.price_rows.text = "\n".join(lines[:12])
        product_id = self.app.repository.find_product_id_for_offer(offer)
        if product_id is None:
            self.graph.set_prices([])
            return
        history = self.app.repository.price_history(product_id)
        self.graph.set_prices([row["price"] for row in history])
