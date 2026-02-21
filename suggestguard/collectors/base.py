"""Base collector interface for autocomplete suggestion sources."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Callable


class BaseCollector(ABC):
    """Abstract base class for suggestion collectors."""

    @abstractmethod
    async def collect(
        self,
        query: str,
        language: str = "tr",
        country: str = "TR",
    ) -> list[str]:
        """Fetch suggestions for a single *query* string.

        Returns a list of suggestion strings.
        """

    @abstractmethod
    async def collect_brand(
        self,
        brand: dict,
        progress_callback: Callable[[int, int, str], None] | None = None,
    ) -> list[dict]:
        """Collect suggestions for all query variants of a brand.

        *brand* is a database row dict with at least ``keywords``,
        ``language``, ``country``, ``expand_az``, ``expand_turkish``.

        *progress_callback(current, total, query)* is called after each
        query completes — suitable for driving a Streamlit progress bar.

        Returns a list of result dicts, each containing:
        ``{"query", "suggestions", "source", "timestamp"}``.
        """
