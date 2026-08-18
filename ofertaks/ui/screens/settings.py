"""Settings and diagnostics screen."""

from __future__ import annotations

import json

from ofertaks.localization import LANGUAGE_OPTIONS, t
from ofertaks.ui.theme import MUTED, make_label, make_screen_layout

try:
    from kivy.uix.screenmanager import Screen
except Exception:  # pragma: no cover
    class Screen:  # type: ignore[no-redef]
        pass


class SettingsScreen(Screen):
    def __init__(self, app, **kwargs):
        from kivy.metrics import dp
        from kivy.uix.button import Button
        from kivy.uix.spinner import Spinner

        super().__init__(**kwargs)
        self.app = app
        frame, layout = make_screen_layout()
        self.title_label = make_label(text=t("settings"), size_hint_y=None, height=dp(36), bold=True, font_size="22sp")
        self.language_label = make_label(text=t("language"), size_hint_y=None, height=dp(28), bold=True)
        self.language_spinner = Spinner(size_hint_y=None, height=dp(44))
        self.language_spinner.bind(text=self._language_changed)
        self.status_label = make_label(text="", size_hint_y=None, height=dp(26), color=MUTED)
        self.diagnostics_label = make_label(text=t("diagnostics"), size_hint_y=None, height=dp(30), bold=True)
        layout.add_widget(self.title_label)
        layout.add_widget(self.language_label)
        layout.add_widget(self.language_spinner)
        layout.add_widget(self.status_label)
        layout.add_widget(self.diagnostics_label)
        self.report = make_label(halign="left", valign="top", use_height=False)
        self.copy_button = Button(text=t("copy_diagnostics"), size_hint_y=None, height=dp(44))
        self.copy_button.bind(on_release=lambda *_: self._copy())
        layout.add_widget(self.copy_button)
        layout.add_widget(self.report)
        self.add_widget(frame)
        self.translate()

    def translate(self) -> None:
        self.title_label.text = t("settings")
        self.language_label.text = t("language")
        self.diagnostics_label.text = t("diagnostics")
        self.copy_button.text = t("copy_diagnostics")
        self.language_spinner.values = tuple(LANGUAGE_OPTIONS.values())
        self.language_spinner.text = LANGUAGE_OPTIONS[self.app.translator.language]

    def reload(self) -> None:
        diagnostics = self.app.repository.diagnostics()
        self.report.text = json.dumps(diagnostics, indent=2, ensure_ascii=False, default=str)

    def _language_changed(self, _spinner, label: str) -> None:
        for code, display in LANGUAGE_OPTIONS.items():
            if display == label and code != self.app.translator.language:
                self.app.set_language(code)
                self.status_label.text = t("language_saved")
                return

    def _copy(self) -> None:
        from kivy.core.clipboard import Clipboard

        Clipboard.copy(self.report.text)
