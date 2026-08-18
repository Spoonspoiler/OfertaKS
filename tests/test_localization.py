import locale
import tempfile
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from ofertaks.database.database import Database
from ofertaks.database.repository import Repository
from ofertaks.localization import LANGUAGE_OPTIONS, Translator, detect_system_language, t
from ofertaks.localization.i18n import normalize_language


class LocalizationTests(TestCase):
    def test_languages_return_expected_strings(self):
        translator = Translator("en")
        self.assertEqual(translator.translate("refresh"), "Refresh")
        self.assertEqual(translator.translate("refresh", "fr"), "Actualiser")
        self.assertEqual(translator.translate("refresh", "sq"), "Rifresko")

    def test_unknown_language_and_missing_key_fallback_safely(self):
        translator = Translator("de")
        self.assertEqual(normalize_language("de"), "en")
        self.assertEqual(translator.translate("refresh"), "Refresh")
        self.assertEqual(translator.translate("definitely_missing_key"), "definitely_missing_key")

    def test_display_labels_are_not_locale_codes(self):
        self.assertEqual(LANGUAGE_OPTIONS["sq"], "Shqip")
        self.assertEqual(LANGUAGE_OPTIONS["en"], "English")
        self.assertEqual(LANGUAGE_OPTIONS["fr"], "Français")

    def test_system_language_detection(self):
        with patch.object(locale, "getlocale", return_value=("fr_FR", "UTF-8")):
            self.assertEqual(detect_system_language(), "fr")
        with patch.object(locale, "getlocale", return_value=("sq_AL", "UTF-8")):
            self.assertEqual(detect_system_language(), "sq")
        with patch.object(locale, "getlocale", return_value=("de_DE", "UTF-8")):
            self.assertEqual(detect_system_language(), "en")

    def test_manual_preference_persists(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Repository(Database(Path(tmp) / "db.sqlite3"))
            repo.initialize()
            repo.set_preference("language", "fr")
            self.assertEqual(Translator.from_repository(repo).language, "fr")
