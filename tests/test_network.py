from __future__ import annotations

from unittest import TestCase

from ofertaks.utils.network import HTTPClient


class _BinaryResponse:
    headers = {"Content-Type": "image/png"}

    @property
    def text(self) -> str:
        raise AssertionError("Binary responses must not be decoded as text")


class _JSONResponse:
    headers = {"Content-Type": "application/json"}
    content = '{"name":"Qumësht"}'.encode("utf-8")

    @property
    def text(self) -> str:
        raise AssertionError("JSON must use its UTF-8 response bytes")


class HTTPClientTests(TestCase):
    def test_binary_image_response_skips_charset_detection(self):
        self.assertEqual(HTTPClient._response_text(_BinaryResponse()), "")

    def test_json_response_uses_utf8_even_when_charset_is_missing(self):
        self.assertEqual(HTTPClient._response_text(_JSONResponse()), '{"name":"Qumësht"}')
