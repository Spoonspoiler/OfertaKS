"""Basket optimizer screen."""

from __future__ import annotations

from ofertaks.localization import t
from ofertaks.services.basket_service import BasketService
from ofertaks.ui.theme import make_label, make_screen_layout

try:
    from kivy.uix.screenmanager import Screen
except Exception:  # pragma: no cover
    class Screen:  # type: ignore[no-redef]
        pass


class BasketScreen(Screen):
    def __init__(self, app, **kwargs):
        from kivy.metrics import dp
        from kivy.uix.boxlayout import BoxLayout
        from kivy.uix.button import Button
        from kivy.uix.textinput import TextInput

        super().__init__(**kwargs)
        self.app = app
        frame, layout = make_screen_layout()
        self.title_label = make_label(text=t("basket"), size_hint_y=None, height=dp(36), bold=True, font_size="22sp")
        layout.add_widget(self.title_label)
        row = BoxLayout(size_hint_y=None, height=dp(46), spacing=dp(8))
        self.input_box = TextInput(hint_text=t("search"), multiline=False)
        self.add_button = Button(text=t("add"), size_hint_x=None, width=dp(86))
        self.add_button.bind(on_release=lambda *_: self._add())
        row.add_widget(self.input_box)
        row.add_widget(self.add_button)
        layout.add_widget(row)
        actions = BoxLayout(size_hint_y=None, height=dp(42), spacing=dp(6))
        self.action_buttons = []
        for key, method in [
            ("any_store", self._cheapest),
            ("two_stores", self._two),
            ("one_store", self._one),
        ]:
            button = Button(text=t(key))
            button.bind(on_release=lambda _, fn=method: fn())
            actions.add_widget(button)
            self.action_buttons.append((key, button))
        self.clear_button = Button(text=t("clear"), size_hint_x=None, width=dp(78))
        self.clear_button.bind(on_release=lambda *_: self._clear())
        actions.add_widget(self.clear_button)
        layout.add_widget(actions)
        self.output = make_label(halign="left", valign="top", use_height=False)
        layout.add_widget(self.output)
        self.add_widget(frame)

    def translate(self) -> None:
        self.title_label.text = t("basket")
        self.input_box.hint_text = t("search")
        self.add_button.text = t("add")
        for key, button in self.action_buttons:
            button.text = t(key)
        self.clear_button.text = t("clear")

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
            missing = f" {t('missing_items')} {len(plan.missing)}" if plan.missing else ""
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
                lines.append(f"{choice.query}: {t('not_matched')}")
        self.output.text = "\n".join(lines)

    def reload(self) -> None:
        items = self.app.repository.list_basket_items()
        if not items:
            self.output.text = ""
            return
        self._cheapest()
