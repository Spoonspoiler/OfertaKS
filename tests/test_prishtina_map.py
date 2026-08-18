"""Offline coverage for the bounded Prishtina map vertical slice."""

from __future__ import annotations

import os
import sqlite3
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest import TestCase

from ofertaks.database.database import Database
from ofertaks.database.repository import Repository
from ofertaks.maps.osm import OverpassMerchantImporter, merchant_type_from_osm_tags
from ofertaks.maps.region import PRISHTINA_REGION
from ofertaks.maps.service import (
    AVAILABILITY_CURRENT,
    AVAILABILITY_STALE,
    AVAILABILITY_UNKNOWN,
    MapService,
)
from ofertaks.models.community import MerchantProductObservation, UserPriceObservation
from ofertaks.models.merchant import (
    BAKERY,
    BUTCHER,
    COMMUNITY_UNVERIFIED,
    FRUIT_VEGETABLE,
    GROCERY,
    MARKET,
    SOURCE_COMMUNITY,
    Merchant,
)
from ofertaks.models.offer import Offer
from ofertaks.services.merchant_service import MerchantService


def merchant(merchant_id: str, name: str, merchant_type: str, latitude: float, longitude: float, **kwargs) -> Merchant:
    return Merchant(
        id=merchant_id,
        name=name,
        merchant_type=merchant_type,
        chain_id=kwargs.pop("chain_id", None),
        latitude=latitude,
        longitude=longitude,
        **kwargs,
    )


class PrishtinaMapTests(TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Repository(Database(Path(self.tmp.name) / "map.sqlite3"))
        self.repo.initialize()
        self.service = MapService(self.repo)

    def tearDown(self):
        self.tmp.cleanup()

    def test_required_chain_registry_is_seeded_without_fake_scraper_support(self):
        chains = {row["id"]: row["name"] for row in self.repo.chains()}
        self.assertEqual(chains["etc"], "ETC")
        self.assertEqual(chains["viva_fresh"], "Viva Fresh")
        self.assertEqual(chains["interex"], "Interex")
        self.assertEqual(chains["albi_market"], "Albi Market")
        self.assertEqual(chains["maxi"], "Maxi")
        self.assertEqual(chains["meridian"], "Meridian Express")
        self.assertEqual(chains["emona"], "Emona Center")
        self.assertEqual(chains["spar_kosovo"], "SPAR Kosovo")
        statuses = {row["id"]: row["availability"] for row in self.repo.source_statuses()}
        self.assertEqual(statuses["etc"], "live")
        self.assertEqual(statuses["maxi"], "location_only")

    def test_food_osm_tag_mapping(self):
        self.assertEqual(merchant_type_from_osm_tags({"shop": "supermarket"}), "SUPERMARKET")
        self.assertEqual(merchant_type_from_osm_tags({"shop": "greengrocer"}), FRUIT_VEGETABLE)
        self.assertEqual(merchant_type_from_osm_tags({"shop": "bakery"}), BAKERY)
        self.assertEqual(merchant_type_from_osm_tags({"shop": "butcher"}), BUTCHER)
        self.assertEqual(merchant_type_from_osm_tags({"amenity": "marketplace"}), MARKET)
        self.assertIsNone(merchant_type_from_osm_tags({"shop": "electronics"}))

    def test_importer_keeps_osm_provenance_and_detects_chain(self):
        importer = OverpassMerchantImporter(
            self.repo, PRISHTINA_REGION, cache_dir=Path(self.tmp.name) / "cache"
        )
        result = importer.import_payload(
            {
                "elements": [
                    {
                        "type": "node",
                        "id": 45,
                        "lat": 42.6597,
                        "lon": 21.1566,
                        "tags": {"shop": "supermarket", "name": "VIVA FRESH", "brand": "VivaFresh"},
                    }
                ]
            }
        )
        row = self.repo.get_merchant("osm-node-45")
        self.assertEqual(result.imported, 1)
        self.assertEqual(row["source_type"], "OSM")
        self.assertEqual(row["source_id"], "node/45")
        self.assertEqual(row["chain_id"], "viva_fresh")
        self.assertIn("VIVA FRESH", row["osm_tags_json"])

    def test_existing_merchant_database_migrates_before_source_index_creation(self):
        legacy_path = Path(self.tmp.name) / "legacy.sqlite3"
        legacy_db = sqlite3.connect(legacy_path)
        try:
            legacy_db.execute(
                """
                CREATE TABLE merchants (
                    id TEXT PRIMARY KEY, name TEXT NOT NULL, merchant_type TEXT NOT NULL,
                    chain_id TEXT, latitude REAL NOT NULL, longitude REAL NOT NULL,
                    address TEXT, city TEXT, neighborhood TEXT, phone TEXT, website TEXT,
                    opening_hours_json TEXT, payment_cash INTEGER, payment_card INTEGER,
                    community_added INTEGER NOT NULL DEFAULT 0, claimed_by_merchant INTEGER NOT NULL DEFAULT 0,
                    verification_status TEXT NOT NULL DEFAULT 'unverified',
                    created_at TEXT NOT NULL, updated_at TEXT NOT NULL
                )
                """
            )
            legacy_db.commit()
        finally:
            legacy_db.close()
        legacy_repo = Repository(Database(legacy_path))
        legacy_repo.initialize()
        with legacy_repo.database.connect() as db:
            fields = {row["name"] for row in db.execute("PRAGMA table_info(merchants)")}
        self.assertIn("source_type", fields)

    def test_bbox_includes_boundaries_and_excludes_outside_places(self):
        self.repo.add_merchant(merchant("inside", "Inside", GROCERY, 42.65, 21.15))
        self.repo.add_merchant(merchant("edge", "Edge", BAKERY, 42.66, 21.16))
        self.repo.add_merchant(merchant("outside", "Outside", BUTCHER, 42.67, 21.17))
        found = self.repo.find_merchants_in_bbox(42.65, 21.15, 42.66, 21.16)
        self.assertEqual({row["id"] for row in found}, {"inside", "edge"})

    def test_duplicate_confidence_does_not_merge_distant_similar_names(self):
        self.repo.add_merchant(
            merchant("viva-official", "Viva Fresh Ulpiana", GROCERY, 42.6597, 21.1566, chain_id="viva_fresh")
        )
        service = MerchantService(self.repo)
        nearby = merchant(
            "viva-osm", "VIVA FRESH", GROCERY, 42.65978, 21.15665, chain_id="viva_fresh"
        )
        distant = merchant(
            "viva-distant", "Viva Fresh", GROCERY, 42.7000, 21.2200, chain_id="viva_fresh"
        )
        self.assertIn(service.match(nearby).confidence, {"EXACT", "LIKELY"})
        self.assertEqual(service.match(distant).confidence, "NO_MATCH")
        self.assertEqual(len(self.repo.list_merchants()), 1)

    def test_product_map_search_distinguishes_current_unknown_and_stale(self):
        offer = Offer(
            store_id="etc",
            store_name="ETC",
            raw_name="Strawberries",
            normalized_name="strawberries",
            brand=None,
            quantity=1000,
            unit="g",
            normal_price=None,
            offer_price=2.5,
            unit_price=2.5,
            discount_percent=None,
            valid_from=None,
            valid_until=None,
            category=FRUIT_VEGETABLE,
            source_url="https://example.test",
            image_url=None,
            scraped_at=datetime.now(UTC),
        )
        self.repo.insert_offer(offer)
        product_id = self.repo.find_product_id_for_offer(offer)
        for merchant_id, name, latitude in (
            ("current", "Current fruit shop", 42.65),
            ("unknown", "Unknown fruit shop", 42.651),
            ("stale", "Stale fruit shop", 42.652),
        ):
            self.repo.add_merchant(merchant(merchant_id, name, FRUIT_VEGETABLE, latitude, 21.15))
        now = datetime.now(UTC)
        for merchant_id, price, observed_at in (
            ("current", 2.5, now - timedelta(hours=2)),
            ("stale", 2.0, now - timedelta(days=90)),
        ):
            self.repo.record_user_price_observation(
                UserPriceObservation(
                    merchant_name=merchant_id,
                    merchant_id=merchant_id,
                    product_id=product_id,
                    raw_name="Strawberries",
                    normalized_name="strawberries",
                    price=price,
                    observed_at=observed_at,
                )
            )
        rows = self.service.viewport_merchants((42.64, 21.14, 42.66, 21.16), product_id=product_id)
        availability = {row.merchant["id"]: row.availability for row in rows}
        self.assertEqual(availability["current"], AVAILABILITY_CURRENT)
        self.assertEqual(availability["unknown"], AVAILABILITY_UNKNOWN)
        self.assertEqual(availability["stale"], AVAILABILITY_STALE)

    def test_community_place_is_unverified_and_visible_in_bbox(self):
        merchant_id = self.service.add_community_merchant(
            name="Vegetable seller next to pharmacy",
            merchant_type=FRUIT_VEGETABLE,
            latitude=42.655,
            longitude=21.161,
            description="Local seasonal vegetables",
        )
        row = self.repo.get_merchant(merchant_id)
        self.assertEqual(row["source_type"], SOURCE_COMMUNITY)
        self.assertEqual(row["community_status"], COMMUNITY_UNVERIFIED)
        visible = self.repo.find_merchants_in_bbox(42.65, 21.15, 42.66, 21.17)
        self.assertIn(merchant_id, {item["id"] for item in visible})
        candidate = merchant("later-import", "Vegetable seller next to pharmacy", FRUIT_VEGETABLE, 42.65501, 21.16101)
        self.assertIn(MerchantService(self.repo).match(candidate).confidence, {"EXACT", "LIKELY"})

    def test_map_price_update_keeps_context_timestamp_and_optional_photo(self):
        self.repo.add_merchant(merchant("map-merchant", "Map merchant", GROCERY, 42.65, 21.15))
        observed_at = datetime.now(UTC)
        observation_id = self.repo.record_user_price_observation(
            UserPriceObservation(
                merchant_name="Map merchant",
                merchant_id="map-merchant",
                product_id=None,
                raw_name="Tomatoes",
                normalized_name="tomatoes",
                price=1.2,
                observed_at=observed_at,
                photo_path=None,
            )
        )
        saved = self.repo.list_user_price_observations()[0]
        self.assertEqual(saved["id"], observation_id)
        self.assertEqual(saved["merchant_id"], "map-merchant")
        self.assertIsNone(saved["photo_path"])
        self.assertEqual(datetime.fromisoformat(saved["observed_at"]), observed_at.replace(microsecond=0))

    def test_add_product_creates_searchable_local_evidence_without_price(self):
        self.repo.add_merchant(merchant("market-stall", "Market stall", MARKET, 42.65, 21.15))
        product_id = self.repo.ensure_product("Goat cheese")
        observation_id = self.repo.record_merchant_product_observation(
            MerchantProductObservation(
                merchant_id="market-stall",
                product_id=product_id,
                raw_name="Goat cheese",
                normalized_name="goat cheese",
                price=None,
                quality="good",
                photo_path=None,
                observed_at=datetime.now(UTC),
            )
        )
        evidence = self.repo.latest_product_evidence(product_id)
        saved = self.repo.list_merchant_product_observations(product_id, "market-stall")[0]
        self.assertEqual(saved["id"], observation_id)
        self.assertIsNone(evidence["market-stall"]["price"])
        self.assertEqual(evidence["market-stall"]["quality"], "good")


class MapUISmokeTests(TestCase):
    def test_map_screen_constructs_with_tiles_disabled(self):
        os.environ["OFERTAKS_DISABLE_MAP_TILES"] = "1"
        try:
            from ofertaks.ui.widgets.map_view import MapSurface, latlon_to_world, world_to_latlon
            from ofertaks.ui.root import OfertaKSApp

            x, y = latlon_to_world(42.6597, 21.1566, 14)
            latitude, longitude = world_to_latlon(x, y, 14)
            self.assertAlmostEqual(latitude, 42.6597, places=4)
            self.assertAlmostEqual(longitude, 21.1566, places=4)
            surface = MapSurface(tiles_enabled=False)
            self.assertEqual(surface.provider.id, "osm_standard")
            with tempfile.TemporaryDirectory() as tmp:
                repo = Repository(Database(Path(tmp) / "ui.sqlite3"))
                repo.initialize()
                repo.add_merchant(merchant("ui-market", "UI market", MARKET, 42.6597, 21.1566))
                app = OfertaKSApp(repo)
                app.build()
                self.assertIn("map", app.screens)
                self.assertIn("map", {name for name in app.nav_buttons})
                app.show_map()
                map_screen = app.screens["map"]
                map_screen._viewport_changed(map_screen.map_surface.visible_bbox())
                self.assertEqual(app.screen_manager.current, "map")
                self.assertEqual(len(map_screen.filter_row.children), 7)
                self.assertEqual(len(map_screen.map_surface._marker_buttons), 1)
                result = map_screen.service.viewport_merchants(map_screen.map_surface.visible_bbox())[0]
                map_screen._merchant_selected(result)
                self.assertGreater(map_screen.card.opacity, 0)
        finally:
            os.environ.pop("OFERTAKS_DISABLE_MAP_TILES", None)
