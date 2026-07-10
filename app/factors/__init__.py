"""
Factor framework package.

Usage::

    from app.factors.registry import factor_registry
    from app.factors import base_factors, financial_factors
    from app.factors.ic_analysis import ICAnalyzer
"""
from .registry import FactorRegistry, factor_registry, FactorMeta

__all__ = ["FactorRegistry", "factor_registry", "FactorMeta"]
