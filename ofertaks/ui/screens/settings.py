"""Settings and diagnostics screen."""

from __future__ import annotations

import json

from ofertaks.app.localization import t


class SettingsScreen:
    def __init__(self, app, **kwargs):
        from kivy.metrics import dp
        from kivy.uix.boxlayout import BoxLayout
        from kivy.uix.button import Button
        from kivy.uix.label import Label
        from kivy.uix.screenmanager import Screen

        Screen.__init__(self, **kwargs)
        self.app = app
        layout = BoxLayout(orientation="vertical", padding=dp(12), spacing=dp(8))
        layout.add_widget(Label(text=t("settings"), size_hint_y=None, height=dp(36), bold=True, font_size="22sp"))
        layout.add_widget(Label(text=t("diagnostics"), size_hint_y=None, height=dp(30), bold=True))
        self.report = Label(halign="left", valign="top", text_size=(0, None))
        copy = Button(text=t("copy_diagnostics"), size_hint_y=None, height=dp(44))
        copy.bind(on_release=lambda *_: self._copy())
        layout.add_widget(copy)
        layout.add_widget(self.report)
        self.add_widget(layout)

    def reload(self) -> None:
        diagnostics = self.app.repository.diagnostics()
        self.report.text = json.dumps(diagnostics, indent=2, ensure_ascii=False, default=str)

    def _copy(self) -> None:
        from kivy.core.clipboard import Clipboard

        Clipboard.copy(self.report.text)
