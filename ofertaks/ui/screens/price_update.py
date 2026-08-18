"""Local price-update form with an Android-ready photo-path placeholder."""

from __future__ import annotations

from datetime import UTC, datetime

from ofertaks.localization import t
from ofertaks.models.community import UserPriceObservation
from ofertaks.ui.theme import MUTED, bind_scroll_content_width, make_label, make_screen_layout

try:
    from kivy.uix.screenmanager import Screen
except Exception:  # pragma: no cover
    class Screen:  # type: ignore[no-redef]
        pass


class PriceUpdateScreen(Screen):
    def __init__(self, app, **kwargs):
        from kivy.metrics import dp
        from kivy.uix.boxlayout import BoxLayout
        from kivy.uix.button import Button
        from kivy.uix.scrollview import ScrollView
        from kivy.uix.spinner import Spinner
        from kivy.uix.textinput import TextInput

        super().__init__(**kwargs)
        self.app = app
        self.offer = None
        self.origin_source = "USER_OBSERVATION"
        self.origin_confidence = "unknown"
        self.quality = "needs_check"
        self._field_labels: dict[str, object] = {}

        frame, layout = make_screen_layout()
        back = Button(text=t("back"), size_hint_y=None, height=dp(40))
        back.bind(on_release=lambda *_: self.app.show_screen("product_detail"))
        layout.add_widget(back)
        self.back_button = back
        self.title_label = make_label(
            text=t("update_price"), size_hint_y=None, height=dp(34), bold=True, font_size="22sp"
        )
        layout.add_widget(self.title_label)

        scroll = ScrollView()
        form = BoxLayout(orientation="vertical", size_hint_y=None, spacing=dp(7), padding=(0, 0, 0, dp(8)))
        form.bind(minimum_height=form.setter("height"))
        bind_scroll_content_width(scroll, form)
        scroll.add_widget(form)
        layout.add_widget(scroll)

        self.product_label = make_label(size_hint_y=None, height=dp(42), bold=True)
        form.add_widget(self.product_label)
        self.merchant_input = self._add_text_field(form, "merchant", TextInput)
        self.price_input = self._add_text_field(form, "price", TextInput)
        self.quantity_input = self._add_text_field(form, "quantity", TextInput)
        self.unit_input = self._add_text_field(form, "unit", TextInput)
        self.origin_country_input = self._add_text_field(form, "origin", TextInput)
        self.origin_region_input = self._add_text_field(form, "origin_region", TextInput)

        self._add_label(form, "origin_source")
        self.origin_source_spinner = Spinner(size_hint_y=None, height=dp(42))
        self.origin_source_spinner.bind(text=self._origin_source_changed)
        form.add_widget(self.origin_source_spinner)
        self._add_label(form, "origin_confidence")
        self.origin_confidence_spinner = Spinner(size_hint_y=None, height=dp(42))
        self.origin_confidence_spinner.bind(text=self._origin_confidence_changed)
        form.add_widget(self.origin_confidence_spinner)
        self._add_label(form, "quality")
        self.quality_spinner = Spinner(size_hint_y=None, height=dp(42))
        self.quality_spinner.bind(text=self._quality_changed)
        form.add_widget(self.quality_spinner)
        self.photo_input = self._add_text_field(form, "photo_path", TextInput)
        self.notes_input = self._add_text_field(form, "notes", TextInput, multiline=True)
        self.status_label = make_label(text="", size_hint_y=None, height=dp(34), color=MUTED)
        form.add_widget(self.status_label)
        self.save_button = Button(text=t("save_price_update"), size_hint_y=None, height=dp(46))
        self.save_button.bind(on_release=lambda *_: self._save())
        form.add_widget(self.save_button)
        self.add_widget(frame)
        self.translate()

    def _add_label(self, form, key: str) -> None:
        from kivy.metrics import dp

        label = make_label(text=t(key), size_hint_y=None, height=dp(22), bold=True)
        self._field_labels[key] = label
        form.add_widget(label)

    def _add_text_field(self, form, key: str, text_input, *, multiline: bool = False):
        from kivy.metrics import dp

        self._add_label(form, key)
        field = text_input(multiline=multiline, size_hint_y=None, height=dp(64 if multiline else 42))
        form.add_widget(field)
        return field

    def translate(self) -> None:
        self.back_button.text = t("back")
        self.title_label.text = t("update_price")
        self.save_button.text = t("save_price_update")
        for key, label in self._field_labels.items():
            label.text = t(key)
        self.origin_source_labels = {
            "USER_OBSERVATION": t("origin_source_user_observation"),
            "STORE_LABEL": t("origin_source_store_label"),
            "MERCHANT": t("origin_source_merchant"),
            "PRODUCT_PACKAGING": t("origin_source_product_packaging"),
            "FLYER": t("origin_source_flyer"),
            "UNKNOWN": t("origin_source_unknown"),
        }
        self.origin_confidence_labels = {
            "verified": t("origin_confidence_verified"),
            "probable": t("origin_confidence_probable"),
            "unknown": t("origin_confidence_unknown"),
        }
        self.quality_labels = {
            "good": t("quality_good"),
            "average": t("quality_average"),
            "needs_check": t("quality_needs_check"),
        }
        self.origin_source_spinner.values = tuple(self.origin_source_labels.values())
        self.origin_source_spinner.text = self.origin_source_labels[self.origin_source]
        self.origin_confidence_spinner.values = tuple(self.origin_confidence_labels.values())
        self.origin_confidence_spinner.text = self.origin_confidence_labels[self.origin_confidence]
        self.quality_spinner.values = tuple(self.quality_labels.values())
        self.quality_spinner.text = self.quality_labels[self.quality]

    def set_offer(self, offer) -> None:
        self.offer = offer
        self.product_label.text = offer.raw_name
        self.merchant_input.text = offer.store_name
        self.price_input.text = f"{offer.offer_price:.2f}"
        self.quantity_input.text = "" if offer.quantity is None else f"{offer.quantity:g}"
        self.unit_input.text = offer.unit or ""
        self.origin_country_input.text = offer.origin_country or ""
        self.origin_region_input.text = offer.origin_region or ""
        self.photo_input.text = ""
        self.notes_input.text = ""
        self.status_label.text = ""

    def reload(self) -> None:
        if self.offer:
            self.set_offer(self.offer)

    def _origin_source_changed(self, _spinner, label: str) -> None:
        self.origin_source = next(
            (code for code, value in self.origin_source_labels.items() if value == label),
            self.origin_source,
        )

    def _origin_confidence_changed(self, _spinner, label: str) -> None:
        self.origin_confidence = next(
            (code for code, value in self.origin_confidence_labels.items() if value == label),
            self.origin_confidence,
        )

    def _quality_changed(self, _spinner, label: str) -> None:
        self.quality = next(
            (code for code, value in self.quality_labels.items() if value == label), self.quality
        )

    def _save(self) -> None:
        if not self.offer:
            return
        merchant_name = self.merchant_input.text.strip()
        if not merchant_name:
            self.status_label.text = t("merchant_required")
            return
        try:
            price = float(self.price_input.text.replace(",", "."))
        except ValueError:
            self.status_label.text = t("price_required")
            return
        try:
            quantity = (
                float(self.quantity_input.text.replace(",", "."))
                if self.quantity_input.text.strip()
                else None
            )
        except ValueError:
            quantity = None
        if price <= 0:
            self.status_label.text = t("price_required")
            return
        product_id = self.app.repository.find_product_id_for_offer(self.offer)
        observation = UserPriceObservation(
            merchant_name=merchant_name,
            merchant_id=self.offer.merchant_id,
            product_id=product_id,
            raw_name=self.offer.raw_name,
            normalized_name=self.offer.normalized_name,
            price=price,
            quantity=quantity,
            unit=self.unit_input.text.strip() or None,
            origin_country=self.origin_country_input.text.strip() or None,
            origin_region=self.origin_region_input.text.strip() or None,
            origin_source=self.origin_source,
            origin_confidence=self.origin_confidence,
            photo_path=self.photo_input.text.strip() or None,
            quality=self.quality,
            notes=self.notes_input.text.strip() or None,
            observed_at=datetime.now(UTC),
        )
        self.app.repository.record_user_price_observation(observation)
        self.status_label.text = t("price_update_saved")
