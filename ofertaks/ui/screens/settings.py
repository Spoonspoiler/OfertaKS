"""Settings and readable diagnostics screen."""

from __future__ import annotations

import json

from ofertaks.localization import LANGUAGE_OPTIONS, t
from ofertaks.ui.theme import MUTED, bind_scroll_content_width, make_label, make_screen_layout

try:
    from kivy.uix.screenmanager import Screen
except Exception:  # pragma: no cover
    class Screen:  # type: ignore[no-redef]
        pass


class SettingsScreen(Screen):
    def __init__(self, app, **kwargs):
        from kivy.metrics import dp
        from kivy.uix.button import Button
        from kivy.uix.scrollview import ScrollView
        from kivy.uix.spinner import Spinner

        super().__init__(**kwargs)
        self.app = app
        self._showing_raw = False
        self.raw_report = ""
        frame, layout = make_screen_layout()
        self.title_label = make_label(
            text=t("settings"), size_hint_y=None, height=dp(36), bold=True, font_size="22sp"
        )
        self.language_label = make_label(
            text=t("language"), size_hint_y=None, height=dp(28), bold=True
        )
        self.language_spinner = Spinner(size_hint_y=None, height=dp(44))
        self.language_spinner.bind(text=self._language_changed)
        self.status_label = make_label(text="", size_hint_y=None, height=dp(26), color=MUTED)
        self.diagnostics_label = make_label(
            text=t("diagnostics"), size_hint_y=None, height=dp(30), bold=True
        )
        layout.add_widget(self.title_label)
        layout.add_widget(self.language_label)
        layout.add_widget(self.language_spinner)
        layout.add_widget(self.status_label)
        layout.add_widget(self.diagnostics_label)
        self.report = make_label(
            halign="left",
            valign="top",
            use_height=False,
            size_hint_y=None,
            height=dp(260),
            padding=dp(4),
        )
        self.report.bind(texture_size=self._report_texture_changed)
        self.copy_button = Button(text=t("copy_diagnostics"), size_hint_y=None, height=dp(44))
        self.copy_button.bind(on_release=lambda *_: self._copy())
        self.raw_button = Button(size_hint_y=None, height=dp(40))
        self.raw_button.bind(on_release=lambda *_: self._toggle_raw())
        report_scroll = ScrollView()
        bind_scroll_content_width(report_scroll, self.report)
        report_scroll.add_widget(self.report)
        layout.add_widget(self.copy_button)
        layout.add_widget(self.raw_button)
        layout.add_widget(report_scroll)
        self.add_widget(frame)
        self.translate()

    def translate(self) -> None:
        self.title_label.text = t("settings")
        self.language_label.text = t("language")
        self.diagnostics_label.text = t("diagnostics")
        self.copy_button.text = t("copy_diagnostics")
        self.raw_button.text = t("hide_raw_report") if self._showing_raw else t("show_raw_report")
        self.language_spinner.values = tuple(LANGUAGE_OPTIONS.values())
        self.language_spinner.text = LANGUAGE_OPTIONS[self.app.translator.language]

    def reload(self) -> None:
        diagnostics = self.app.repository.diagnostics()
        self.raw_report = json.dumps(diagnostics, indent=2, ensure_ascii=False, default=str)
        self._render_summary(self.app.repository.diagnostics_summary())

    def _render_summary(self, summary) -> None:
        if self._showing_raw:
            self.report.text = self.raw_report
            self.raw_button.text = t("hide_raw_report")
            return
        state = lambda value: t("diagnostic_ok") if value else t("diagnostic_unavailable")
        lines = [
            f"{t('store_count')}: {summary['store_count']}",
            f"{t('live_stores')}: {summary['live_store_count']}",
            f"{t('total_offers')}: {summary['total_offer_count']}",
            f"{t('food_offers')}: {summary['food_offer_count']}",
            f"{t('merchant_count')}: {summary['merchant_count']}",
            f"{t('last_sync')}: {summary['last_sync'] or t('offline_data')}",
            f"{t('cache_writable')}: {state(summary['cache_writable'])}",
            f"{t('database_writable')}: {state(summary['database_writable'])}",
            f"{t('translation_service')}: {state(summary['translation_service'])}",
            "",
            f"{t('scraper_statuses')}:",
        ]
        for source in summary["last_scraper_runs"]:
            last_run = source["last_run"]
            run_status = t("status_never_run")
            if last_run:
                run_status = t(f"status_{last_run['status']}")
            lines.append(
                f"{source['name']}: {t(source['status_key'])} | "
                f"{source['offer_count']} | {run_status}"
            )
        self.report.text = "\n".join(lines)
        self.raw_button.text = t("show_raw_report")

    def _report_texture_changed(self, _label, size) -> None:
        from kivy.metrics import dp

        self.report.height = max(dp(260), size[1] + dp(12))

    def _toggle_raw(self) -> None:
        self._showing_raw = not self._showing_raw
        self._render_summary(self.app.repository.diagnostics_summary())

    def _language_changed(self, _spinner, label: str) -> None:
        for code, display in LANGUAGE_OPTIONS.items():
            if display == label and code != self.app.translator.language:
                self.app.set_language(code)
                self.status_label.text = t("language_saved")
                return

    def _copy(self) -> None:
        from kivy.core.clipboard import Clipboard

        Clipboard.copy(self.raw_report or self.report.text)
