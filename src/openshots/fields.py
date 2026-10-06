"""Field definitions for result projections.

This module provides field descriptors for specifying what data
to extract from shot results.

Example:
    >>> from openshots import fields as f
    >>> for solution, avg in osr.results([f.solution(int, f.higher_better), f.estimate]):
    ...     print(solution, avg)
"""

from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from typing import Any


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


def project(descriptor: FieldDescriptor, shot):
    """Project counts/metadata; solution means most frequent outcome, not problem optimality.

    Optimization chooses the numeric tie-break direction for equally frequent
    outcomes. An absent estimate remains None; no objective is invented.
    """
    if descriptor.name == "counts":
        value = shot.counts
    elif descriptor.name == "solution":
        direction = -1 if descriptor.optimization == lower_better else 1
        state = max(
            shot.counts,
            key=lambda state: (shot.counts[state], direction * int(state, 2)),
        )
        value = int(state, 2) if descriptor.dtype is int else state
    elif descriptor.name == "estimate":
        value = shot.metadata.tags.get("estimate")
    elif descriptor.name == "probability":
        total = sum(shot.counts.values())
        value = {state: count / total for state, count in shot.counts.items()}
    else:
        raise ValueError(f"unknown projection {descriptor.name}")
    if descriptor.dtype is not None and value is not None:
        value = descriptor.dtype(value)
    return descriptor.transform(value) if descriptor.transform is not None else value
