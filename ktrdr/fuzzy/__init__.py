"""
Fuzzy logic module for KTRDR.

This module provides functionality for converting indicator values into
fuzzy membership degrees using configurable membership functions.

V3-only: V2 config classes have been removed. Use FuzzySetDefinition
from ktrdr.config.models for configuration.
"""

from ktrdr.fuzzy.engine import FuzzyEngine
from ktrdr.fuzzy.membership import (
    MEMBERSHIP_REGISTRY,
    GaussianMF,
    MembershipFunction,
    TrapezoidalMF,
    TriangularMF,
)

__all__ = [
    "FuzzyEngine",
    "MEMBERSHIP_REGISTRY",
    "MembershipFunction",
    "TriangularMF",
    "TrapezoidalMF",
    "GaussianMF",
]
