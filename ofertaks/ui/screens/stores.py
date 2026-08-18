"""Stores settings screen."""

from __future__ import annotations

from ofertaks.localization import t
from ofertaks.ui.theme import make_label, make_screen_layout

try:
    from kivy.uix.screenmanager import Screen
except Exception:  # pragma: no cover
    class Screen:  # type: ignore[no-redef]
        pass


class StoresScreen(Screen):
    def __init__(self, app, **kwargs):
        from kivy.metrics import dp

        super().__init__(**kwargs)
        self.app = app
        frame, self.layout = make_screen_layout()
        self.title_label = make_label(text=t("stores"), size_hint_y=None, height=dp(36), bold=True, font_size="22sp")
        self.layout.add_widget(self.title_label)
        self.add_widget(frame)

    def translate(self) -> None:
        self.title_label.text = t("stores")

    def reload(self) -> None:
        from kivy.metrics import dp
        from kivy.uix.boxlayout import BoxLayout
        from kivy.uix.switch import Switch

        while len(self.layout.children) > 1:
            self.layout.remove_widget(self.layout.children[0])
        for store in self.app.repository.stores():
            row = BoxLayout(size_hint_y=None, height=dp(46), spacing=dp(8))
            row.add_widget(make_label(text=store["name"]))
            toggle = Switch(active=bool(store["enabled"]), size_hint_x=None, width=dp(70))
            toggle.bind(active=lambda _, active, store_id=store["id"]: self.app.repository.set_store_enabled(store_id, active))
            row.add_widget(toggle)
            self.layout.add_widget(row)
