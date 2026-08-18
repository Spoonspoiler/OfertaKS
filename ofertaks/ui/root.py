"""Kivy app root."""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor

from ofertaks.app.paths import get_app_data_dir, get_debug_scrape_dir
from ofertaks.localization import Translator, set_language, t
from ofertaks.services.sync_service import SyncService

os.environ.setdefault("KIVY_HOME", str(get_app_data_dir() / "kivy"))

try:
    from kivy.app import App
    from kivy.clock import Clock
    from kivy.core.window import Window
    from kivy.metrics import dp
    from kivy.uix.boxlayout import BoxLayout
    from kivy.uix.button import Button
    from kivy.uix.screenmanager import ScreenManager
except Exception as exc:  # pragma: no cover - desktop dependency guard
    App = None
    KIVY_IMPORT_ERROR = exc
else:
    KIVY_IMPORT_ERROR = None


class OfertaKSApp(App if App is not None else object):
    def __init__(self, repository, **kwargs):
        if App is None:
            raise RuntimeError(
                f"Kivy could not start. Install requirements.txt and ensure KIVY_HOME is writable: {KIVY_IMPORT_ERROR}"
            ) from KIVY_IMPORT_ERROR
        super().__init__(**kwargs)
        self.repository = repository
        self.translator = Translator.from_repository(repository)
        set_language(self.translator.language)
        self.executor = ThreadPoolExecutor(max_workers=1)
        self.screen_manager = None
        self.sync_status: dict[str, str] = {}
        self.nav_buttons: dict[str, object] = {}

    def build(self):
        from ofertaks.ui.screens.basket import BasketScreen
        from ofertaks.ui.screens.barcode_scan import BarcodeScanScreen
        from ofertaks.ui.screens.add_place import AddPlaceScreen
        from ofertaks.ui.screens.home import HomeScreen
        from ofertaks.ui.screens.map import MapScreen
        from ofertaks.ui.screens.offers import OffersScreen
        from ofertaks.ui.screens.product_detail import ProductDetailScreen
        from ofertaks.ui.screens.price_update import PriceUpdateScreen
        from ofertaks.ui.screens.search import SearchScreen
        from ofertaks.ui.screens.settings import SettingsScreen
        from ofertaks.ui.screens.stores import StoresScreen

        Window.clearcolor = (0.96, 0.97, 0.96, 1)
        root = BoxLayout(orientation="vertical")
        self.screen_manager = ScreenManager()
        self.screens = {
            "home": HomeScreen(app=self, name="home"),
            "offers": OffersScreen(app=self, name="offers"),
            "map": MapScreen(app=self, name="map"),
            "search": SearchScreen(app=self, name="search"),
            "basket": BasketScreen(app=self, name="basket"),
            "stores": StoresScreen(app=self, name="stores"),
            "settings": SettingsScreen(app=self, name="settings"),
            "product_detail": ProductDetailScreen(app=self, name="product_detail"),
            "price_update": PriceUpdateScreen(app=self, name="price_update"),
            "add_place": AddPlaceScreen(app=self, name="add_place"),
            "barcode_scan": BarcodeScanScreen(app=self, name="barcode_scan"),
        }
        for screen in self.screens.values():
            self.screen_manager.add_widget(screen)
        root.add_widget(self.screen_manager)
        root.add_widget(self._nav_bar())
        self.refresh_all_screens()
        return root

    def _nav_bar(self):
        from kivy.uix.anchorlayout import AnchorLayout

        wrapper = AnchorLayout(anchor_x="center", anchor_y="center", size_hint_y=None, height=dp(52))
        bar = BoxLayout(size_hint=(None, 1), width=dp(760), spacing=dp(2), padding=dp(4))

        def update_width(instance, width):
            available_width = Window.width if width <= dp(120) else width
            bar.width = min(available_width, dp(760))

        wrapper.bind(width=update_width)
        update_width(wrapper, wrapper.width)
        Clock.schedule_once(lambda *_: update_width(wrapper, wrapper.width), 0)
        self.nav_buttons = {}
        for screen_name, label_key in [
            ("home", "home"),
            ("offers", "offers"),
            ("map", "map"),
            ("search", "search"),
            ("basket", "basket_short"),
            ("stores", "stores"),
            ("settings", "settings"),
        ]:
            button = Button(text=t(label_key), font_size="11sp")
            button.bind(on_release=lambda _, name=screen_name: self._show_from_navigation(name))
            bar.add_widget(button)
            self.nav_buttons[label_key] = button
        wrapper.add_widget(bar)
        return wrapper

    def _show_from_navigation(self, name: str) -> None:
        """Open a top-level screen without retaining a map-specific offer scope."""

        if name == "offers":
            self.screens["offers"].clear_merchant_context()
        self.show_screen(name)

    def set_language(self, language: str) -> None:
        self.translator.set_language(language)
        set_language(language)
        self.repository.set_preference("language", self.translator.language)
        for key, button in self.nav_buttons.items():
            button.text = t(key)
        for screen in getattr(self, "screens", {}).values():
            if hasattr(screen, "translate"):
                screen.translate()
            if hasattr(screen, "reload"):
                screen.reload()

    def show_screen(self, name: str) -> None:
        self.screen_manager.current = name
        screen = self.screens.get(name)
        if screen and hasattr(screen, "reload"):
            screen.reload()

    def show_product(self, offer) -> None:
        detail = self.screens["product_detail"]
        detail.set_offer(offer)
        self.show_screen("product_detail")

    def show_merchant_offers(self, merchant: dict) -> None:
        offers = self.screens["offers"]
        offers.show_merchant(merchant)
        self.show_screen("offers")

    def show_barcode_scan(self, *, merchant: dict | None = None, return_screen: str = "search", barcode: str = "") -> None:
        scanner = self.screens["barcode_scan"]
        scanner.set_context(merchant=merchant, return_screen=return_screen, barcode=barcode)
        self.show_screen("barcode_scan")

    def show_map(
        self,
        *,
        product_id: int | None = None,
        product_name: str | None = None,
        merchant_id: str | None = None,
        filter_id: str | None = None,
    ) -> None:
        map_screen = self.screens["map"]
        map_screen.open_context(
            product_id=product_id,
            product_name=product_name,
            merchant_id=merchant_id,
            filter_id=filter_id,
        )
        self.show_screen("map")

    def refresh_all_screens(self) -> None:
        for screen in getattr(self, "screens", {}).values():
            if hasattr(screen, "reload"):
                screen.reload()

    def start_sync(self) -> None:
        service = SyncService(self.repository, debug_dir=get_debug_scrape_dir())
        self.sync_status = {store["id"]: "queued" for store in self.repository.stores(True)}
        self._notify_sync_change()

        def progress(store_id: str, status: str, error: str | None) -> None:
            def apply(_dt):
                self.sync_status[store_id] = status if not error else f"{status}: {error}"
                self._notify_sync_change()

            Clock.schedule_once(apply)

        future = self.executor.submit(service.sync_all, progress)

        def done(_future):
            def apply(_dt):
                self.refresh_all_screens()

            Clock.schedule_once(apply)

        future.add_done_callback(done)

    def _notify_sync_change(self) -> None:
        for screen in getattr(self, "screens", {}).values():
            if hasattr(screen, "sync_status_changed"):
                screen.sync_status_changed(self.sync_status)
