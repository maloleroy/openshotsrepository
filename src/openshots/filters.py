"""Filter fields for query expressions.

This module provides filter fields that can be used with comparison
operators to create filter conditions.

Example:
    >>> from openshots.filters import backend, n_qubits
    >>> osr.results().filter((backend == "ibm_aachen") & (n_qubits == 50))
"""

from openshots.query import FilterField
from openshots.models import circuit_to_hash
from openshots.query import FilterCondition
from typing import Any


# Pre-defined filter fields
backend = FilterField("backend")
"""Filter by backend name."""

n_qubits = FilterField("n_qubits")
"""Filter by number of qubits."""

circuit_hash = FilterField("circuit_hash")
"""Filter by circuit hash."""


class CircuitFilter:
    """Special filter for circuits that computes the hash."""

    name = "circuit_hash"

    def __eq__(self, value: Any) -> FilterCondition:  # type: ignore[override]
        """Create an equality condition using the circuit's hash."""
        return FilterCondition(_conditions={self.name: circuit_to_hash(value)})


circuit = CircuitFilter()
"""Filter by circuit (automatically hashed)."""
