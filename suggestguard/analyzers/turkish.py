"""Turkish language-specific text processing and query expansion."""

from __future__ import annotations

import re
import string

# Turkish special characters and their ASCII equivalents
_TR_TO_ASCII: dict[str, str] = {
    "ş": "s",
    "Ş": "S",
    "ç": "c",
    "Ç": "C",
    "ö": "o",
    "Ö": "O",
    "ü": "u",
    "Ü": "U",
    "ğ": "g",
    "Ğ": "G",
    "ı": "i",
    "I": "I",
}

_TR_LOWER: dict[str, str] = {
    "İ": "i",
    "I": "ı",
}

_TR_SPECIAL_CHARS = set("şçöüğıŞÇÖÜĞİ")

_WS_RE = re.compile(r"\s+")


class TurkishTextProcessor:
    """Utilities for Turkish-aware text normalisation and query expansion."""

    # ── normalisation ────────────────────────────────────────────────

    @staticmethod
    def normalize(text: str) -> str:
        """Turkish-aware lowercase + whitespace collapse/strip.

        Standard ``str.lower()`` maps ``I`` → ``i`` and ``İ`` → ``i̇``,
        which is wrong for Turkish.  This method handles the special
        cases (``İ`` → ``i``, ``I`` → ``ı``) before lowering the rest.
        """
        for src, dst in _TR_LOWER.items():
            text = text.replace(src, dst)
        text = text.lower()
        text = _WS_RE.sub(" ", text).strip()
        return text

    # ── ASCII transliteration ────────────────────────────────────────

    @staticmethod
    def ascii_variants(text: str) -> str:
        """Replace Turkish special characters with ASCII equivalents.

        ``ş`` → ``s``, ``ç`` → ``c``, ``ö`` → ``o``,
        ``ü`` → ``u``, ``ğ`` → ``g``, ``ı`` → ``i``.
        """
        for src, dst in _TR_TO_ASCII.items():
            text = text.replace(src, dst)
        return text

    # ── query expansion ──────────────────────────────────────────────

    def generate_query_variants(
        self,
        keyword: str,
        expand_az: bool = True,
        expand_turkish: bool = True,
    ) -> list[str]:
        """Generate autocomplete query variants for *keyword*.

        Returns a deduplicated, order-preserved list built from:

        1. The normalised keyword itself.
        2. Its ASCII transliteration (if different).
        3. ``keyword + " " + letter`` for every ``a-z`` letter
           (when *expand_az* is True).
        4. ``keyword + " " + ch`` for every Turkish-specific letter
           ``ş ç ö ü ğ ı`` (when *expand_turkish* is True).
        """
        base = self.normalize(keyword)
        ascii_form = self.ascii_variants(base)

        variants: list[str] = [base]
        if ascii_form != base:
            variants.append(ascii_form)

        if expand_az:
            for ch in string.ascii_lowercase:
                variants.append(f"{base} {ch}")

        if expand_turkish:
            for ch in "şçöüğı":
                variants.append(f"{base} {ch}")

        # deduplicate while preserving order
        seen: set[str] = set()
        unique: list[str] = []
        for v in variants:
            if v not in seen:
                seen.add(v)
                unique.append(v)
        return unique

    # ── language detection (lightweight) ─────────────────────────────

    @staticmethod
    def detect_language(text: str) -> str:
        """Return ``'tr'`` if *text* contains Turkish-specific characters,
        otherwise ``'unknown'``."""
        for ch in text:
            if ch in _TR_SPECIAL_CHARS:
                return "tr"
        return "unknown"
