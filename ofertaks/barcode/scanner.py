"""Platform-neutral barcode scanning boundary.

The Android adapter intentionally lives behind this small interface so desktop
manual entry remains useful and the package does not claim camera support until
the real Android build has been validated.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol

from ofertaks.normalization.gtin import validate_gtin


class BarcodeScannerUnavailable(RuntimeError):
    """Raised when the current platform has no installed camera adapter."""


@dataclass(frozen=True, slots=True)
class BarcodeScanResult:
    barcode_gtin: str
    source: str
    scanned_at: datetime


class BarcodeScanner(Protocol):
    def scan(self) -> BarcodeScanResult: ...


class ManualBarcodeScanner:
    """Resolve manually entered values through the same validation boundary."""

    @staticmethod
    def from_text(value: str) -> BarcodeScanResult:
        return BarcodeScanResult(
            barcode_gtin=validate_gtin(value),
            source="MANUAL_ENTRY",
            scanned_at=datetime.now(UTC),
        )


class UnsupportedBarcodeScanner:
    """Explicit placeholder until a platform camera implementation is added."""

    def scan(self) -> BarcodeScanResult:
        raise BarcodeScannerUnavailable("No camera barcode scanner is available on this platform")
