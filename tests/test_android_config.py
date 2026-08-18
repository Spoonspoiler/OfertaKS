import configparser
from pathlib import Path
from unittest import TestCase

import ofertaks


class AndroidConfigTests(TestCase):
    def setUp(self):
        parser = configparser.ConfigParser()
        parser.read(Path("buildozer.spec"))
        self.app = parser["app"]

    def test_buildozer_identity_and_version(self):
        self.assertEqual(self.app["title"], "OfertaKS")
        self.assertEqual(self.app["package.name"], "ofertaks")
        self.assertEqual(self.app["package.domain"], "com.ptitspot")
        self.assertEqual(self.app["orientation"], "portrait")
        self.assertEqual(self.app["version"], ofertaks.__version__)

    def test_android_permissions_are_minimal(self):
        permissions = {
            item.strip()
            for item in self.app["android.permissions"].split(",")
        }
        self.assertEqual(permissions, {"INTERNET", "ACCESS_NETWORK_STATE"})

    def test_android_architecture_targets_current_phones(self):
        archs = {item.strip() for item in self.app["android.archs"].split(",")}
        self.assertIn("arm64-v8a", archs)
