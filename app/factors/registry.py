"""
Factor registry with direction support.

Based on docs/design/06-factor-framework.md §2:

- Every factor has a *direction* (1 = higher is better, -1 = lower is better).
- ``oriented_factor = raw_factor * direction`` so downstream code always
  treats "larger = better".
- The ``@register`` decorator captures metadata alongside the compute function.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

import pandas as pd

logger = logging.getLogger(__name__)


# ======================================================================
# Factor Metadata
# ======================================================================


@dataclass
class FactorMeta:
    """Metadata for a single registered factor."""
    name: str
    description: str
    category: str           # "market", "financial", "momentum", "composite", …
    direction: int           # 1 = higher is better; -1 = lower is better
    compute_fn: Callable     # (date, pit, **kwargs) → DataFrame(ts_code, trade_date, factor_value)
    dependencies: List[str] = field(default_factory=list)
    params: dict = field(default_factory=dict)


# ======================================================================
# Registry
# ======================================================================


class FactorRegistry:
    """Factor registration table.

    Usage::

        registry = FactorRegistry()

        @registry.register(name="pe_ttm", description="PE TTM", category="market", direction=-1)
        def compute_pe_ttm(date: str, pit, **kwargs) -> pd.DataFrame:
            ...

        oriented = registry.compute("pe_ttm", date="20260630", pit=pit_query)
    """

    def __init__(self) -> None:
        self._factors: Dict[str, FactorMeta] = {}

    # --- Registration ---

    def register(
        self,
        name: str,
        description: str = "",
        category: str = "custom",
        direction: int = 1,
        dependencies: Optional[List[str]] = None,
        params: Optional[dict] = None,
    ) -> Callable:
        """Decorator to register a factor compute function.

        The decorated function must accept ``(date: str, pit, **kwargs)``
        and return a ``pd.DataFrame`` with at least columns
        ``[ts_code, trade_date, factor_value]``.
        """
        def decorator(fn: Callable) -> Callable:
            self._factors[name] = FactorMeta(
                name=name,
                description=description or (fn.__doc__ or "").strip(),
                category=category,
                direction=direction,
                compute_fn=fn,
                dependencies=dependencies or [],
                params=params or {},
            )
            return fn
        return decorator

    # --- Computation ---

    def compute(self, name: str, **kwargs) -> pd.DataFrame:
        """Compute factor *name* and apply direction.

        Returns DataFrame with oriented factor values (higher = better).
        """
        meta = self._factors.get(name)
        if meta is None:
            raise ValueError(f"Factor '{name}' is not registered")

        params = {**meta.params, **kwargs}
        raw_df = meta.compute_fn(**params)

        if raw_df is None or len(raw_df) == 0:
            return pd.DataFrame(columns=["ts_code", "trade_date", "factor_value"])

        return self._apply_direction(raw_df, meta.direction)

    def compute_raw(self, name: str, **kwargs) -> pd.DataFrame:
        """Compute factor *name* without direction adjustment."""
        meta = self._factors.get(name)
        if meta is None:
            raise ValueError(f"Factor '{name}' is not registered")
        params = {**meta.params, **kwargs}
        return meta.compute_fn(**params)

    # --- Listing ---

    def list_factors(self) -> List[FactorMeta]:
        return list(self._factors.values())

    def get_meta(self, name: str) -> Optional[FactorMeta]:
        return self._factors.get(name)

    # --- Internal ---

    @staticmethod
    def _apply_direction(df: pd.DataFrame, direction: int) -> pd.DataFrame:
        """Multiply factor_value by direction so higher = better."""
        result = df.copy()
        if "factor_value" in result.columns:
            result["factor_value"] = result["factor_value"] * direction
        return result


# ======================================================================
# Singleton
# ======================================================================

factor_registry = FactorRegistry()
