"""Shared HTTP client with retries, rate limiting, and conditional headers."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from email.utils import parsedate_to_datetime
from typing import Any
from urllib.parse import urlparse

from ofertaks.app import config


@dataclass(slots=True)
class HTTPResponse:
    url: str
    status_code: int
    text: str
    content: bytes
    headers: dict[str, str]


class HTTPClient:
    def __init__(self) -> None:
        import requests

        self.session = requests.Session()
        self.session.headers.update({"User-Agent": config.HTTP_USER_AGENT})
        self._semaphore = threading.Semaphore(config.HTTP_MAX_CONCURRENT)
        self._last_request_by_host: dict[str, float] = {}
        self._validators: dict[str, dict[str, str]] = {}

    def get(self, url: str, **kwargs: Any) -> HTTPResponse:
        return self.request("GET", url, **kwargs)

    def post_json(self, url: str, payload: dict[str, Any], **kwargs: Any) -> HTTPResponse:
        """Post a JSON payload through the shared retry and rate-limit path."""

        headers = dict(kwargs.pop("headers", {}) or {})
        headers.setdefault("Content-Type", "application/json")
        return self.request("POST", url, headers=headers, json=payload, **kwargs)

    def request(self, method: str, url: str, **kwargs: Any) -> HTTPResponse:
        headers = dict(kwargs.pop("headers", {}) or {})
        validators = self._validators.get(url, {})
        if method.upper() == "GET" and validators.get("etag"):
            headers["If-None-Match"] = validators["etag"]
        if method.upper() == "GET" and validators.get("last_modified"):
            headers["If-Modified-Since"] = validators["last_modified"]
        timeout = kwargs.pop("timeout", config.HTTP_TIMEOUT_SECONDS)

        with self._semaphore:
            self._respect_host_delay(url)
            last_exc: Exception | None = None
            for attempt in range(config.HTTP_MAX_RETRIES + 1):
                try:
                    response = self.session.request(
                        method,
                        url,
                        timeout=timeout,
                        headers=headers,
                        **kwargs,
                    )
                    if response.status_code in {429, 500, 502, 503, 504}:
                        raise RuntimeError(f"temporary HTTP {response.status_code}")
                    self._save_validators(url, response.headers)
                    return HTTPResponse(
                        url=response.url,
                        status_code=response.status_code,
                        text=self._response_text(response),
                        content=response.content,
                        headers=dict(response.headers),
                    )
                except Exception as exc:
                    last_exc = exc
                    if attempt >= config.HTTP_MAX_RETRIES:
                        break
                    time.sleep(0.8 * (2**attempt))
            raise RuntimeError(f"{method.upper()} failed for {url}: {last_exc}") from last_exc

    @staticmethod
    def _response_text(response: Any) -> str:
        """Decode only text-like responses.

        Accessing ``requests.Response.text`` triggers charset detection when a
        server does not declare an encoding. That is useful for product pages,
        but it produces noisy diagnostics for binary map PNG files.
        """

        content_type = response.headers.get("Content-Type", "").split(";", 1)[0].strip().casefold()
        if content_type.startswith("image/") or content_type in {
            "application/octet-stream",
            "application/pdf",
            "application/zip",
        }:
            return ""
        if content_type == "application/json" or content_type.endswith("+json"):
            # JSON is UTF-8 by definition. Some catalogue proxies omit or
            # misstate their charset, which otherwise corrupts Albanian text.
            return response.content.decode("utf-8")
        return response.text

    def _respect_host_delay(self, url: str) -> None:
        host = urlparse(url).netloc
        now = time.monotonic()
        previous = self._last_request_by_host.get(host)
        if previous is not None:
            wait = config.HOST_REQUEST_DELAY_SECONDS - (now - previous)
            if wait > 0:
                time.sleep(wait)
        self._last_request_by_host[host] = time.monotonic()

    def _save_validators(self, url: str, headers: Any) -> None:
        validators: dict[str, str] = {}
        etag = headers.get("ETag")
        last_modified = headers.get("Last-Modified")
        if etag:
            validators["etag"] = etag
        if last_modified:
            try:
                parsedate_to_datetime(last_modified)
                validators["last_modified"] = last_modified
            except Exception:
                pass
        if validators:
            self._validators[url] = validators
