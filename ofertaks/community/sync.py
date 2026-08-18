"""Boundary for a later community API; current submissions remain local."""

from __future__ import annotations

from typing import Protocol

from ofertaks.models.community import MerchantProductObservation, UserPriceObservation
from ofertaks.models.merchant import Merchant


class CommunitySyncGateway(Protocol):
    def sync_merchant(self, merchant: Merchant) -> None: ...

    def sync_price_observation(self, observation: UserPriceObservation) -> None: ...

    def sync_product_observation(self, observation: MerchantProductObservation) -> None: ...
