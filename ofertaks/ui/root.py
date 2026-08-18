"""Kivy app root."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from ofertaks.app.config import get_data_dir
from ofertaks.app.localization import t
from ofertaks.services.sync_service import SyncService


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
                "Kivy is not installed. Install requirements.txt before running the UI."
            ) from KIVY_IMPORT_ERROR
        super().__init__(**kwargs)
        self.repository = repository
        self.executor = ThreadPoolExecutor(max_workers=1)
        self.screen_manager = None
        self.sync_status: dict[str, str] = {}

    def build(self):
        from ofertaks.ui.screens.basket import BasketScreen
        from ofertaks.ui.screens.home import HomeScreen
        from ofertaks.ui.screens.offers import OffersScreen
        from ofertaks.ui.screens.product_detail import ProductDetailScreen
        from ofertaks.ui.screens.search import SearchScreen
        from ofertaks.ui.screens.settings import SettingsScreen
        from ofertaks.ui.screens.stores import StoresScreen

        Window.clearcolor = (0.96, 0.97, 0.96, 1)
        root = BoxLayout(orientation="vertical")
        self.screen_manager = ScreenManager()
        self.screens = {
            "home": HomeScreen(app=self, name="home"),
            "offers": OffersScreen(app=self, name="offers"),
            "search": SearchScreen(app=self, name="search"),
            "basket": BasketScreen(app=self, name="basket"),
            "stores": StoresScreen(app=self, name="stores"),
            "settings": SettingsScreen(app=self, name="settings"),
            "product_detail": ProductDetailScreen(app=self, name="product_detail"),
        }
        for screen in self.screens.values():
            self.screen_manager.add_widget(screen)
        root.add_widget(self.screen_manager)
        root.add_widget(self._nav_bar())
        self.refresh_all_screens()
        return root

    def _nav_bar(self):
        bar = BoxLayout(size_hint_y=None, height=dp(52), spacing=dp(2), padding=dp(4))
        for screen_name, label_key in [
            ("home", "home"),
            ("offers", "offers"),
            ("search", "search"),
            ("basket", "basket"),
            ("stores", "stores"),
            ("settings", "settings"),
        ]:
            button = Button(text=t(label_key))
            button.bind(on_release=lambda _, name=screen_name: self.show_screen(name))
            bar.add_widget(button)
        return bar

    def show_screen(self, name: str) -> None:
        self.screen_manager.current = name
        screen = self.screens.get(name)
        if screen and hasattr(screen, "reload"):
            screen.reload()

    def show_product(self, offer) -> None:
        detail = self.screens["product_detail"]
        detail.set_offer(offer)
        self.show_screen("product_detail")

    def refresh_all_screens(self) -> None:
        for screen in getattr(self, "screens", {}).values():
            if hasattr(screen, "reload"):
                screen.reload()

    def start_sync(self) -> None:
        data_dir = get_data_dir()
        debug_dir = Path(data_dir) / "debug_scrapes"
        service = SyncService(self.repository, debug_dir=debug_dir)
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
