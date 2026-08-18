"""Search bar widget."""

from __future__ import annotations

from ofertaks.localization import t


def build_search_bar(on_submit):
    from kivy.metrics import dp
    from kivy.uix.boxlayout import BoxLayout
    from kivy.uix.button import Button
    from kivy.uix.textinput import TextInput

    row = BoxLayout(orientation="horizontal", spacing=dp(8), size_hint_y=None, height=dp(48))
    input_box = TextInput(hint_text=t("search"), multiline=False, write_tab=False)
    button = Button(text=t("search"), size_hint_x=None, width=dp(96))
    button.bind(on_release=lambda *_: on_submit(input_box.text))
    input_box.bind(on_text_validate=lambda *_: on_submit(input_box.text))
    row.add_widget(input_box)
    row.add_widget(button)
    return row, input_box, button
