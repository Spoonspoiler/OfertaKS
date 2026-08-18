from __future__ import annotations

from unittest import TestCase

from ofertaks.utils.network import HTTPClient


class _BinaryResponse:
    headers = {"Content-Type": "image/png"}

    @property
    def text(self) -> str:
        raise AssertionError("Binary responses must not be decoded as text")


class HTTPClientTests(TestCase):
    def test_binary_image_response_skips_charset_detection(self):
        self.assertEqual(HTTPClient._response_text(_BinaryResponse()), "")
