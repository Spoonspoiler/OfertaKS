"""GTIN-first lookup and manual product contribution screen."""

from __future__ import annotations

from ofertaks.barcode.scanner import BarcodeScannerUnavailable, ManualBarcodeScanner, UnsupportedBarcodeScanner
from ofertaks.localization import t
from ofertaks.models.knowledge import CanonicalProduct
from ofertaks.ui.theme import MUTED, bind_scroll_content_width, make_label, make_screen_layout

try:
    from kivy.uix.screenmanager import Screen
except Exception:  # pragma: no cover
    class Screen:  # type: ignore[no-redef]
        pass


class BarcodeScanScreen(Screen):
    def __init__(self, app, **kwargs):
        from kivy.metrics import dp
        from kivy.uix.boxlayout import BoxLayout
        from kivy.uix.button import Button
        from kivy.uix.scrollview import ScrollView
        from kivy.uix.textinput import TextInput

        super().__init__(**kwargs)
        self.app = app
        self.return_screen = "search"
        self.merchant: dict | None = None
        self.product: dict | None = None
        self._camera = UnsupportedBarcodeScanner()
        frame, layout = make_screen_layout()
        self.back_button = Button(text=t("back"), size_hint_y=None, height=dp(40))
        self.back_button.bind(on_release=lambda *_: self.app.show_screen(self.return_screen))
        layout.add_widget(self.back_button)
        self.title_label = make_label(text=t("scan_product"), size_hint_y=None, height=dp(36), bold=True, font_size="22sp")
        layout.add_widget(self.title_label)
        scroll = ScrollView()
        content = BoxLayout(orientation="vertical", spacing=dp(7), size_hint_y=None, padding=(0, 0, 0, dp(8)))
        content.bind(minimum_height=content.setter("height"))
        bind_scroll_content_width(scroll, content)
        scroll.add_widget(content)
        layout.add_widget(scroll)
        self.barcode_label = make_label(text=t("barcode"), size_hint_y=None, height=dp(22), bold=True)
        self.barcode_input = TextInput(multiline=False, size_hint_y=None, height=dp(42), input_filter="int")
        buttons = BoxLayout(size_hint_y=None, height=dp(42), spacing=dp(7))
        self.resolve_button = Button(text=t("resolve_barcode"))
        self.resolve_button.bind(on_release=lambda *_: self._resolve())
        self.camera_button = Button(text=t("scan_with_camera"))
        self.camera_button.bind(on_release=lambda *_: self._scan_camera())
        buttons.add_widget(self.resolve_button)
        buttons.add_widget(self.camera_button)
        self.status_label = make_label(text="", size_hint_y=None, height=dp(38), color=MUTED)
        self.product_label = make_label(text="", size_hint_y=None, height=dp(52), bold=True)
        self.prices_label = make_label(text="", size_hint_y=None, height=dp(76), color=MUTED)
        self.name_label = make_label(text=t("product"), size_hint_y=None, height=dp(22), bold=True)
        self.name_input = TextInput(multiline=False, size_hint_y=None, height=dp(42))
        self.brand_label = make_label(text=t("brand"), size_hint_y=None, height=dp(22), bold=True)
        self.brand_input = TextInput(multiline=False, size_hint_y=None, height=dp(42))
        self.quantity_label = make_label(text=t("quantity"), size_hint_y=None, height=dp(22), bold=True)
        self.quantity_input = TextInput(multiline=False, size_hint_y=None, height=dp(42), input_filter="float")
        self.unit_label = make_label(text=t("unit"), size_hint_y=None, height=dp(22), bold=True)
        self.unit_input = TextInput(multiline=False, size_hint_y=None, height=dp(42))
        self.save_product_button = Button(text=t("save_product"), size_hint_y=None, height=dp(44))
        self.save_product_button.bind(on_release=lambda *_: self._create_product())
        self.update_button = Button(text=t("update_price"), size_hint_y=None, height=dp(44), disabled=True)
        self.update_button.bind(on_release=lambda *_: self._open_update())
        for widget in (
            self.barcode_label,
            self.barcode_input,
            buttons,
            self.status_label,
            self.product_label,
            self.prices_label,
            self.name_label,
            self.name_input,
            self.brand_label,
            self.brand_input,
            self.quantity_label,
            self.quantity_input,
            self.unit_label,
            self.unit_input,
            self.save_product_button,
            self.update_button,
        ):
            content.add_widget(widget)
        self.add_widget(frame)
        self._contribution_heights = {
            widget: widget.height
            for widget in (
                self.name_label,
                self.name_input,
                self.brand_label,
                self.brand_input,
                self.quantity_label,
                self.quantity_input,
                self.unit_label,
                self.unit_input,
                self.save_product_button,
            )
        }
        self._set_contribution_visible(False)

    def translate(self) -> None:
        self.back_button.text = t("back")
        self.title_label.text = t("scan_product")
        self.barcode_label.text = t("barcode")
        self.resolve_button.text = t("resolve_barcode")
        self.camera_button.text = t("scan_with_camera")
        self.name_label.text = t("product")
        self.brand_label.text = t("brand")
        self.quantity_label.text = t("quantity")
        self.unit_label.text = t("unit")
        self.save_product_button.text = t("save_product")
        self.update_button.text = t("update_price")

    def set_context(self, *, merchant: dict | None = None, return_screen: str = "search", barcode: str = "") -> None:
        self.return_screen = return_screen
        self.merchant = merchant
        self.product = None
        self.barcode_input.text = barcode
        self.status_label.text = ""
        self.product_label.text = ""
        self.prices_label.text = ""
        self.name_input.text = ""
        self.brand_input.text = ""
        self.quantity_input.text = ""
        self.unit_input.text = ""
        self.update_button.disabled = True
        self._set_contribution_visible(False)

    def _scan_camera(self) -> None:
        try:
            result = self._camera.scan()
        except BarcodeScannerUnavailable:
            self.status_label.text = t("camera_scan_unavailable")
            return
        self.barcode_input.text = result.barcode_gtin
        self._resolve()

    def _resolve(self) -> None:
        try:
            result = ManualBarcodeScanner.from_text(self.barcode_input.text)
        except ValueError:
            self.status_label.text = t("barcode_invalid")
            self.product = None
            self.update_button.disabled = True
            self._set_contribution_visible(False)
            return
        product = self.app.repository.find_verified_product_by_gtin(result.barcode_gtin)
        if product:
            self._show_product(product)
            return
        self.product = None
        self.status_label.text = t("barcode_not_found")
        self.product_label.text = ""
        self.prices_label.text = ""
        self.update_button.disabled = True
        self._set_contribution_visible(True)

    def _show_product(self, product: dict) -> None:
        self.product = product
        self.status_label.text = t("barcode_known")
        identity = [product["canonical_name"], product.get("brand"), product.get("barcode_gtin")]
        self.product_label.text = " | ".join(part for part in identity if part)
        offers = self.app.repository.offers_for_product(int(product["id"]))
        lines = [f"{offer.store_name}: {offer.offer_price:.2f} EUR" for offer in offers[:3]]
        self.prices_label.text = "\n".join(lines) or t("no_current_prices")
        self.update_button.disabled = False
        self._set_contribution_visible(False)

    def _create_product(self) -> None:
        try:
            barcode = ManualBarcodeScanner.from_text(self.barcode_input.text).barcode_gtin
        except ValueError:
            self.status_label.text = t("barcode_invalid")
            return
        name = self.name_input.text.strip()
        if not name:
            self.status_label.text = t("product_required")
            return
        try:
            quantity = float(self.quantity_input.text) if self.quantity_input.text.strip() else None
        except ValueError:
            quantity = None
        product_id = self.app.repository.create_canonical_product(
            CanonicalProduct(
                id=None,
                canonical_name=name,
                brand=self.brand_input.text.strip() or None,
                quantity=quantity,
                unit=self.unit_input.text.strip() or None,
                category=None,
                barcode_gtin=barcode,
                gtin_source="USER_MANUAL",
            )
        )
        product = self.app.repository.get_canonical_product(product_id)
        if product:
            self._show_product(product)

    def _open_update(self) -> None:
        if not self.product:
            return
        update = self.app.screens["price_update"]
        update.set_context(
            merchant=self.merchant,
            product_id=int(self.product["id"]),
            product_name=self.product["canonical_name"],
            mode="update_price",
            return_screen=self.return_screen,
        )
        self.app.show_screen("price_update")

    def _set_contribution_visible(self, visible: bool) -> None:
        for widget in (
            self.name_label,
            self.name_input,
            self.brand_label,
            self.brand_input,
            self.quantity_label,
            self.quantity_input,
            self.unit_label,
            self.unit_input,
            self.save_product_button,
        ):
            widget.disabled = not visible
            widget.opacity = 1 if visible else 0
            widget.height = self._contribution_heights[widget] if visible else 0
