"""Small UI helpers for readable Kivy layouts."""

from __future__ import annotations

TEXT = (0.08, 0.10, 0.11, 1)
MUTED = (0.28, 0.34, 0.36, 1)
ACCENT = (0.10, 0.46, 0.34, 1)
SURFACE = (1, 1, 1, 1)
BORDER = (0.82, 0.85, 0.84, 1)
PRICE_STATUS_COLORS = {
    "exceptional": (0.22, 0.63, 0.84, 1),
    "cheap": (0.10, 0.55, 0.29, 1),
    "neutral": (0.40, 0.45, 0.46, 1),
    "expensive": (0.86, 0.47, 0.10, 1),
    "high": (0.78, 0.20, 0.18, 1),
}
CATEGORY_ART_COLORS = {
    "FRUIT_VEGETABLE": (0.36, 0.64, 0.29, 1),
    "DAIRY": (0.26, 0.57, 0.75, 1),
    "MEAT": (0.72, 0.31, 0.25, 1),
    "PANTRY": (0.72, 0.53, 0.20, 1),
    "FOOD": (0.72, 0.53, 0.20, 1),
    "DRINK": (0.18, 0.51, 0.68, 1),
    "BAKERY": (0.76, 0.47, 0.22, 1),
    "FROZEN": (0.22, 0.62, 0.73, 1),
    "SNACKS": (0.68, 0.36, 0.48, 1),
    "OTHER_FOOD": (0.42, 0.52, 0.40, 1),
}


def make_screen_layout(*, padding: float = 12, spacing: float = 8, max_width: float = 760):
    from kivy.clock import Clock
    from kivy.core.window import Window
    from kivy.metrics import dp
    from kivy.uix.anchorlayout import AnchorLayout
    from kivy.uix.boxlayout import BoxLayout

    frame = AnchorLayout(anchor_x="center", anchor_y="top")
    layout = BoxLayout(
        orientation="vertical",
        padding=dp(padding),
        spacing=dp(spacing),
        size_hint=(None, 1),
        width=dp(max_width),
    )

    def update_width(instance, width):
        # Kivy starts detached widgets at 100px. Once attached, the parent's
        # width is authoritative so a narrow mobile layout never inherits a
        # desktop Window width.
        available_width = Window.width if width <= dp(120) else width
        layout.width = min(available_width, dp(max_width))

    frame.bind(width=update_width)
    update_width(frame, frame.width)
    Clock.schedule_once(lambda *_: update_width(frame, frame.width), 0)
    frame.add_widget(layout)
    return frame, layout


def bind_scroll_content_width(scroll, content):
    content.size_hint_x = None

    def update_width(instance, width):
        content.width = width

    scroll.bind(width=update_width)
    update_width(scroll, scroll.width)


def bind_label_text_size(label, padding: float = 0, use_height: bool = True):
    """Bind a label's text box to its real rendered width.

    Passing ``text_size=(0, None)`` makes Kivy wrap every character vertically.
    This helper keeps left/center alignment while using the actual widget width.
    """

    def update(instance, *_args):
        width = max(1, instance.width - padding)
        height = instance.height if use_height else None
        instance.text_size = (width, height)

    label.bind(width=update, height=update)
    update(label)
    return label


def make_label(
    text: str = "",
    *,
    halign: str = "left",
    valign: str = "middle",
    color=TEXT,
    bind_text: bool = True,
    use_height: bool = True,
    padding: float = 0,
    **kwargs,
):
    from kivy.uix.label import Label

    label = Label(text=text, halign=halign, valign=valign, color=color, **kwargs)
    if bind_text:
        bind_label_text_size(label, padding=padding, use_height=use_height)
    return label


def add_card_background(widget, radius: float = 6) -> None:
    add_fill_background(widget, SURFACE, BORDER, radius)


def add_fill_background(widget, fill, border=None, radius: float = 6) -> None:
    from kivy.graphics import Color, Line, RoundedRectangle

    with widget.canvas.before:
        Color(*fill)
        background = RoundedRectangle(pos=widget.pos, size=widget.size, radius=[radius])
        if border:
            Color(*border)
            border_line = Line(
                rounded_rectangle=(widget.x, widget.y, widget.width, widget.height, radius), width=1
            )
        else:
            border_line = None

    def update(instance, *_args):
        background.pos = instance.pos
        background.size = instance.size
        if border_line is not None:
            border_line.rounded_rectangle = (
                instance.x,
                instance.y,
                instance.width,
                instance.height,
                radius,
            )

    widget.bind(pos=update, size=update)
