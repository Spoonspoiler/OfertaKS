"""Deterministic product category detection."""

from __future__ import annotations

from ofertaks.utils.text import comparable_text

FOOD = "FOOD"
DRINK = "DRINK"
MEAT = "MEAT"
FRUIT_VEGETABLE = "FRUIT_VEGETABLE"
DAIRY = "DAIRY"
BAKERY = "BAKERY"
PANTRY = "PANTRY"
FROZEN = "FROZEN"
SNACKS = "SNACKS"
OTHER_FOOD = "OTHER_FOOD"
HOUSEHOLD = "HOUSEHOLD"
HYGIENE = "HYGIENE"
BABY = "BABY"
OTHER = "OTHER"

# FOOD is retained as a legacy category for already-cached offers. New generic
# shelf-stable products are normalized to PANTRY so the browse filters are clear.
FOOD_CATEGORIES = frozenset(
    {
        FOOD,
        DRINK,
        MEAT,
        FRUIT_VEGETABLE,
        DAIRY,
        BAKERY,
        PANTRY,
        FROZEN,
        SNACKS,
        OTHER_FOOD,
    }
)

FOOD_CATEGORY_FILTERS: dict[str, tuple[str, ...]] = {
    FRUIT_VEGETABLE: (FRUIT_VEGETABLE,),
    DAIRY: (DAIRY,),
    MEAT: (MEAT,),
    PANTRY: (PANTRY, FOOD),
    DRINK: (DRINK,),
    BAKERY: (BAKERY,),
    FROZEN: (FROZEN,),
    SNACKS: (SNACKS,),
    OTHER_FOOD: (OTHER_FOOD,),
}

CATEGORY_LABEL_KEYS = {
    FRUIT_VEGETABLE: "category_fruits_vegetables",
    DAIRY: "category_dairy",
    MEAT: "category_meat_fish",
    PANTRY: "category_pantry",
    FOOD: "category_pantry",
    DRINK: "category_drinks",
    BAKERY: "bakery",
    FROZEN: "category_frozen",
    SNACKS: "category_snacks",
    OTHER_FOOD: "category_other_food",
}

KEYWORDS: dict[str, tuple[str, ...]] = {
    FROZEN: (
        "frozen",
        "ngrir",
        "ngrirje",
        "surgel",
        "congele",
        "akullore",
        "ice cream",
    ),
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
        "water",
        "eau",
        "limo",
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
        "peshk",
        "fish",
        "thon",
        "tuna",
        "salmon",
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
        "portokall",
        "orange",
        "limon",
        "lemon",
        "kastra",
        "cucumber",
        "spec",
        "pepper",
        "laker",
        "cabbage",
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
        "baguette",
        "patisserie",
    ),
    SNACKS: (
        "chips",
        "patatina",
        "snack",
        "kikirik",
        "peanut",
        "arra",
        "nuts",
        "cokollate",
        "chocolate",
        "biskota",
        "biscuit",
    ),
    HOUSEHOLD: (
        "detergjent",
        "detergent",
        "pastrim",
        "cleaner",
        "dish",
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
    PANTRY: (
        "kafe",
        "coffee",
        "oriz",
        "rice",
        "miell",
        "flour",
        "vaj",
        "olive",
        "makarona",
        "pasta",
        "sheqer",
        "sugar",
        "krip",
        "salt",
        "salce",
        "sauce",
        "konserve",
        "canned",
        "fasule",
        "beans",
        "ushqimore",
    ),
    OTHER_FOOD: (
        "ushqim",
        "food",
        "edible",
        "gatim",
        "cooking",
    ),
}


def detect_category(text: str) -> str:
    normalized = comparable_text(text)
    for category, words in KEYWORDS.items():
        if any(word in normalized for word in words):
            return category
    return OTHER


def is_food_category(category: str | None) -> bool:
    """Return whether a stored category belongs in the food-only catalog."""

    return category in FOOD_CATEGORIES


def category_filter_values(category: str | None) -> tuple[str, ...]:
    """Expand a visible filter to compatible stored categories."""

    if category is None:
        return tuple(FOOD_CATEGORIES)
    return FOOD_CATEGORY_FILTERS.get(category, (category,))


def category_label_key(category: str | None) -> str:
    return CATEGORY_LABEL_KEYS.get(category, "category_other_food")
