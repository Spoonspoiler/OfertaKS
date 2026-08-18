"""Store filter widgets."""

from __future__ import annotations


def build_store_chip(text: str, active: bool = False):
    from kivy.metrics import dp
    from kivy.uix.togglebutton import ToggleButton

    return ToggleButton(
        text=text,
        state="down" if active else "normal",
        size_hint=(None, None),
        width=dp(max(84, len(text) * 10)),
        height=dp(38),
        group="stores",
    )
