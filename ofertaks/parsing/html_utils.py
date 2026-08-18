"""BeautifulSoup helpers."""

from __future__ import annotations

from urllib.parse import urljoin

from ofertaks.utils.text import clean_text


def make_soup(html: str):
    from bs4 import BeautifulSoup

    return BeautifulSoup(html, "html.parser")


def text_of(node) -> str:
    if node is None:
        return ""
    return clean_text(node.get_text(" ", strip=True))


def absolute_url(base_url: str, maybe_url: str | None) -> str | None:
    if not maybe_url:
        return None
    return urljoin(base_url, maybe_url)


def image_url_near(node, base_url: str) -> str | None:
    if node is None:
        return None
    for container in [node, node.parent, node.find_parent("article"), node.find_parent("div")]:
        if container is None:
            continue
        image = container.find("img") if hasattr(container, "find") else None
        if image:
            return absolute_url(base_url, image.get("src") or image.get("data-src"))
    return None
