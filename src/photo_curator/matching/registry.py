"""Strategy registry: lookup matching strategies by name."""

from __future__ import annotations

from photo_curator.matching.base import MatchStrategy
from photo_curator.matching.content_hash import ContentHashStrategy
from photo_curator.matching.filename_size import FilenameSizeStrategy

_STRATEGIES: dict[str, MatchStrategy] = {}


def _register(strategy: MatchStrategy) -> None:
    _STRATEGIES[strategy.name] = strategy


# Register built-in strategies
_register(FilenameSizeStrategy())
_register(ContentHashStrategy())


def get_strategy(name: str) -> MatchStrategy:
    """Look up a strategy by its CLI name."""
    if name not in _STRATEGIES:
        available = ", ".join(sorted(_STRATEGIES.keys()))
        raise ValueError(
            f"Unknown match strategy '{name}'. Available: {available}"
        )
    return _STRATEGIES[name]


def available_strategies() -> list[str]:
    """Return names of all registered strategies."""
    return sorted(_STRATEGIES.keys())
