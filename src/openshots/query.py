"""Query interface for the Open Shots Repository."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Iterator

from openshots.models import Shot, circuit_to_hash

if TYPE_CHECKING:
    from openshots.client import OSRClient


@dataclass
class ResultsQuery:
    """A fluent query builder for shots.

    Supports chained filtering and aggregation operations.
    """

    _client: OSRClient | None = None
    _filters: dict[str, Any] = field(default_factory=dict)
    _as_int: bool = False

    def filter(
        self,
        condition: FilterCondition | None = None,
        *,
        backend: str | None = None,
        circuit: Any | None = None,
        circuit_hash: str | None = None,
        n_qubits: int | None = None,
    ) -> ResultsQuery:
        """Add filter conditions to the query.

        Can be called with keyword arguments or with a FilterCondition
        from the filters module.

        Args:
            condition: A FilterCondition object (e.g., from openshots.filters).
            backend: Filter by backend name.
            circuit: Filter by circuit (will be hashed).
            circuit_hash: Filter by circuit hash.
            n_qubits: Filter by number of qubits.

        Returns:
            A new ResultsQuery with the filters applied.
        """
        new_filters = self._filters.copy()

        # Handle FilterCondition
        if condition is not None:
            new_filters.update(condition.to_dict())

        # Handle keyword arguments
        if backend is not None:
            new_filters["backend"] = backend

        if circuit is not None:
            new_filters["circuit_hash"] = circuit_to_hash(circuit)
        elif circuit_hash is not None:
            new_filters["circuit_hash"] = circuit_hash

        if n_qubits is not None:
            new_filters["n_qubits"] = n_qubits

        return ResultsQuery(
            _client=self._client,
            _filters=new_filters,
            _as_int=self._as_int,
        )

    @property
    def client(self) -> OSRClient:
        """Get the client, using the default if not set."""
        if self._client is None:
            from openshots.client import get_client

            return get_client()
        return self._client

    def _execute(self) -> list[Shot]:
        """Execute the query and return results."""
        return self.client.query_shots(**self._filters)

    def __iter__(self) -> Iterator[dict[str, int] | dict[int, int]]:
        """Iterate over shot counts."""
        for shot in self._execute():
            if self._as_int:
                yield shot.counts_int()
            else:
                yield shot.counts

    def all(self) -> list[Shot]:
        """Return all matching shots as Shot objects."""
        return self._execute()

    def concat(self) -> dict[str, int] | dict[int, int]:
        """Concatenate all matching shot counts into a single dict.

        Returns:
            Combined counts from all matching shots.
        """
        shots = self._execute()

        if self._as_int:
            result: dict[int, int] = {}
            for shot in shots:
                for k, v in shot.counts_int().items():
                    result[k] = result.get(k, 0) + v
            return result
        else:
            result_str: dict[str, int] = {}
            for shot in shots:
                for k, v in shot.counts.items():
                    result_str[k] = result_str.get(k, 0) + v
            return result_str

    def count(self) -> int:
        """Return the number of matching shots."""
        return len(self._execute())

    def first(self) -> Shot | None:
        """Return the first matching shot, or None if no matches."""
        shots = self._execute()
        return shots[0] if shots else None


@dataclass
class FilterCondition:
    """Represents a filter condition for queries."""

    _conditions: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to a dictionary of filter parameters."""
        return self._conditions.copy()

    def __and__(self, other: FilterCondition) -> FilterCondition:
        """Combine two conditions with AND."""
        combined = self._conditions.copy()
        combined.update(other._conditions)
        return FilterCondition(_conditions=combined)


@dataclass
class FilterField:
    """A field that can be used in filter expressions."""

    name: str

    def __eq__(self, value: Any) -> FilterCondition:  # type: ignore[override]
        """Create an equality condition."""
        return FilterCondition(_conditions={self.name: value})


def results(client: OSRClient | None = None) -> ResultsQuery:
    """Create a new query for shot results.

    Args:
        client: Optional OSRClient instance. Uses the default client if not provided.

    Returns:
        A ResultsQuery that returns counts as dict[str, int].

    Example:
        >>> for counts in osr.results().filter(backend="ibm_aachen"):
        ...     print(counts)
    """
    return ResultsQuery(_client=client, _as_int=False)


def results_int(client: OSRClient | None = None) -> ResultsQuery:
    """Create a new query for shot results with integer keys.

    Args:
        client: Optional OSRClient instance. Uses the default client if not provided.

    Returns:
        A ResultsQuery that returns counts as dict[int, int].

    Example:
        >>> combined = osr.results_int().filter(backend="ibm_aachen").concat()
        >>> print(combined)  # {0: 100, 1: 50, ...}
    """
    return ResultsQuery(_client=client, _as_int=True)
