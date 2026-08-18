"""Stores settings screen."""

from __future__ import annotations

from ofertaks.app.localization import t

try:
    from kivy.uix.screenmanager import Screen
except Exception:  # pragma: no cover
    class Screen:  # type: ignore[no-redef]
        pass


class StoresScreen(Screen):
    def __init__(self, app, **kwargs):
        from kivy.metrics import dp
        from kivy.uix.boxlayout import BoxLayout
        from kivy.uix.label import Label

        super().__init__(**kwargs)
        self.app = app
        self.layout = BoxLayout(orientation="vertical", padding=dp(12), spacing=dp(8))
        self.layout.add_widget(Label(text=t("stores"), size_hint_y=None, height=dp(36), bold=True, font_size="22sp"))
        self.add_widget(self.layout)

    def reload(self) -> None:
        from kivy.metrics import dp
        from kivy.uix.boxlayout import BoxLayout
        from kivy.uix.label import Label
        from kivy.uix.switch import Switch

        while len(self.layout.children) > 1:
            self.layout.remove_widget(self.layout.children[0])
        for store in self.app.repository.stores():
            row = BoxLayout(size_hint_y=None, height=dp(46), spacing=dp(8))
            row.add_widget(Label(text=store["name"], halign="left", text_size=(0, None)))
            toggle = Switch(active=bool(store["enabled"]), size_hint_x=None, width=dp(70))
            toggle.bind(active=lambda _, active, store_id=store["id"]: self.app.repository.set_store_enabled(store_id, active))
            row.add_widget(toggle)
            self.layout.add_widget(row)
