"""Deterministic product category detection."""

from __future__ import annotations

from ofertaks.utils.text import comparable_text

FOOD = "FOOD"
DRINK = "DRINK"
MEAT = "MEAT"
FRUIT_VEGETABLE = "FRUIT_VEGETABLE"
DAIRY = "DAIRY"
BAKERY = "BAKERY"
HOUSEHOLD = "HOUSEHOLD"
HYGIENE = "HYGIENE"
BABY = "BABY"
OTHER = "OTHER"

KEYWORDS: dict[str, tuple[str, ...]] = {
    DRINK: (
        "cola",
        "coca",
        "fanta",
        "sprite",
        "uje",
        "uj",
        "leng",
        "juice",
        "birre",
        "beer",
        "ver",
        "pije",
    ),
    MEAT: (
        "mish",
        "pule",
        "chicken",
        "qofte",
        "suxhuk",
        "salcice",
        "proshute",
        "viqi",
    ),
    FRUIT_VEGETABLE: (
        "domate",
        "tomato",
        "molle",
        "apple",
        "banane",
        "banana",
        "patate",
        "qep",
        "sallate",
        "fruta",
        "perime",
    ),
    DAIRY: (
        "qumesht",
        "milk",
        "kos",
        "jogurt",
        "djath",
        "cheese",
        "gjalp",
        "ajke",
    ),
    BAKERY: (
        "buke",
        "bread",
        "kifle",
        "croissant",
        "pite",
        "byrek",
        "furre",
    ),
    HOUSEHOLD: (
        "detergjent",
        "pastrim",
        "leter",
        "peceta",
        "sapun enesh",
        "kuzhine",
        "shtepi",
    ),
    HYGIENE: (
        "shampo",
        "sapuni",
        "sapun",
        "higjien",
        "tooth",
        "pasta",
        "deodorant",
        "kozmetike",
    ),
    BABY: ("bebe", "baby", "pelena", "pampers", "femije"),
    FOOD: (
        "kafe",
        "coffee",
        "oriz",
        "miell",
        "vaj",
        "olive",
        "makarona",
        "pasta",
        "sheqer",
        "cokollate",
        "biskota",
        "ushqimore",
    ),
}


def detect_category(text: str) -> str:
    normalized = comparable_text(text)
    for category, words in KEYWORDS.items():
        if any(word in normalized for word in words):
            return category
    return OTHER
