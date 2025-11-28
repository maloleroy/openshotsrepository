"""Field definitions for result projections.

This module provides field descriptors for specifying what data
to extract from shot results.

Example:
    >>> from openshots import fields as f
    >>> for solution, avg in osr.results([f.solution(int, f.higher_better), f.estimate]):
    ...     print(solution, avg)
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable


class Optimization(Enum):
    """Optimization direction for a field."""

    HIGHER_BETTER = "higher_better"
    LOWER_BETTER = "lower_better"


# Convenience aliases
higher_better = Optimization.HIGHER_BETTER
lower_better = Optimization.LOWER_BETTER


@dataclass
class FieldDescriptor:
    """Describes a field to extract from results."""

    name: str
    dtype: type | None = None
    optimization: Optimization | None = None
    transform: Callable[[Any], Any] | None = None


def solution(
    dtype: type = str,
    optimization: Optimization | None = None,
) -> FieldDescriptor:
    """Extract the solution (most frequent outcome) from shots.

    Args:
        dtype: Type to convert the solution to (str or int).
        optimization: Whether higher or lower values are better.

    Returns:
        A FieldDescriptor for the solution field.
    """
    return FieldDescriptor(
        name="solution",
        dtype=dtype,
        optimization=optimization,
    )


# Pre-defined field descriptors
estimate = FieldDescriptor(name="estimate")
"""Extract the estimated value from shots."""

counts = FieldDescriptor(name="counts")
"""Extract the raw counts dict from shots."""

probability = FieldDescriptor(name="probability")
"""Extract outcome probabilities from shots."""
