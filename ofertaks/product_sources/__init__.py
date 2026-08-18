"""Official product metadata parsing and conservative enrichment."""

from ofertaks.product_sources.base import OfficialProductMetadata, OfficialProductParser
from ofertaks.product_sources.enrichment import EnrichmentResult, ProductEnrichmentService
from ofertaks.product_sources.official_site import parse_official_product_page
from ofertaks.product_sources.registry import ProductSourceRegistry

__all__ = (
    "EnrichmentResult",
    "OfficialProductMetadata",
    "OfficialProductParser",
    "ProductEnrichmentService",
    "ProductSourceRegistry",
    "parse_official_product_page",
)
