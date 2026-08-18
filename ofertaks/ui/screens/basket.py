"""Basket optimizer screen."""

from __future__ import annotations

from ofertaks.app.localization import t
from ofertaks.services.basket_service import BasketService


class BasketScreen:
    def __init__(self, app, **kwargs):
        from kivy.metrics import dp
        from kivy.uix.boxlayout import BoxLayout
        from kivy.uix.button import Button
        from kivy.uix.label import Label
        from kivy.uix.screenmanager import Screen
        from kivy.uix.textinput import TextInput

        Screen.__init__(self, **kwargs)
        self.app = app
        layout = BoxLayout(orientation="vertical", padding=dp(12), spacing=dp(8))
        layout.add_widget(Label(text=t("basket"), size_hint_y=None, height=dp(36), bold=True, font_size="22sp"))
        row = BoxLayout(size_hint_y=None, height=dp(46), spacing=dp(8))
        self.input_box = TextInput(hint_text=t("search"), multiline=False)
        add = Button(text=t("add"), size_hint_x=None, width=dp(86))
        add.bind(on_release=lambda *_: self._add())
        row.add_widget(self.input_box)
        row.add_widget(add)
        layout.add_widget(row)
        actions = BoxLayout(size_hint_y=None, height=dp(42), spacing=dp(6))
        for label, method in [
            (t("any_store"), self._cheapest),
            (t("two_stores"), self._two),
            (t("one_store"), self._one),
        ]:
            button = Button(text=label)
            button.bind(on_release=lambda _, fn=method: fn())
            actions.add_widget(button)
        clear = Button(text=t("clear"), size_hint_x=None, width=dp(78))
        clear.bind(on_release=lambda *_: self._clear())
        actions.add_widget(clear)
        layout.add_widget(actions)
        self.output = Label(halign="left", valign="top", text_size=(0, None))
        layout.add_widget(self.output)
        self.add_widget(layout)

    def _service(self) -> BasketService:
        return BasketService(self.app.repository)

    def _add(self) -> None:
        query = self.input_box.text.strip()
        if query:
            self.app.repository.add_basket_item(query)
            self.input_box.text = ""
            self.reload()

    def _clear(self) -> None:
        self.app.repository.clear_basket()
        self.reload()

    def _cheapest(self) -> None:
        self._show_plan(self._service().cheapest_overall())

    def _two(self) -> None:
        self._show_plan(self._service().maximum_stores(2))

    def _one(self) -> None:
        plans = self._service().one_store_totals()
        text = []
        for plan in plans:
            missing = f" missing {len(plan.missing)}" if plan.missing else ""
            text.append(f"{', '.join(plan.stores):<16} {plan.total:.2f} EUR{missing}")
        self.output.text = "\n".join(text)

    def _show_plan(self, plan) -> None:
        lines = [f"{', '.join(plan.stores) or '-'}  |  {plan.total:.2f} EUR"]
        for choice in plan.choices:
            if choice.offer:
                lines.append(
                    f"{choice.query}: {choice.offer.store_name} {choice.offer.offer_price:.2f} EUR"
                )
            else:
                lines.append(f"{choice.query}: not matched")
        self.output.text = "\n".join(lines)

    def reload(self) -> None:
        items = self.app.repository.list_basket_items()
        if not items:
            self.output.text = ""
            return
        self._cheapest()
