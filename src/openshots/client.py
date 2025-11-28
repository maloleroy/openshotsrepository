"""HTTP client for the Open Shots Repository server."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import httpx

from openshots.models import Shot, ShotMetadata, circuit_to_hash


@dataclass
class OSRClient:
    """Client for interacting with the Open Shots Repository server."""

    base_url: str = "http://localhost:8000"
    """Base URL of the OSR server."""

    timeout: float = 30.0
    """Request timeout in seconds."""

    _client: httpx.Client | None = None

    def __post_init__(self) -> None:
        # Allow override from environment
        self.base_url = os.environ.get("OSR_SERVER_URL", self.base_url)

    @property
    def client(self) -> httpx.Client:
        """Lazy-initialize HTTP client."""
        if self._client is None:
            self._client = httpx.Client(base_url=self.base_url, timeout=self.timeout)
        return self._client

    def close(self) -> None:
        """Close the HTTP client."""
        if self._client is not None:
            self._client.close()
            self._client = None

    def __enter__(self) -> OSRClient:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    def query_shots(
        self,
        *,
        backend: str | None = None,
        circuit: Any | None = None,
        circuit_hash: str | None = None,
        n_qubits: int | None = None,
        limit: int | None = None,
    ) -> list[Shot]:
        """Query shots from the repository.

        Args:
            backend: Filter by backend name.
            circuit: Filter by circuit (will be hashed).
            circuit_hash: Filter by circuit hash directly.
            n_qubits: Filter by number of qubits.
            limit: Maximum number of results to return.

        Returns:
            List of Shot objects matching the query.
        """
        params: dict[str, Any] = {}

        if backend is not None:
            params["backend"] = backend

        if circuit is not None:
            params["circuit_hash"] = circuit_to_hash(circuit)
        elif circuit_hash is not None:
            params["circuit_hash"] = circuit_hash

        if n_qubits is not None:
            params["n_qubits"] = n_qubits

        if limit is not None:
            params["limit"] = limit

        response = self.client.get("/shots", params=params)
        response.raise_for_status()

        return [self._parse_shot(s) for s in response.json()]

    def store_shot(
        self,
        counts: dict[str, int],
        *,
        backend: str,
        circuit: Any | None = None,
        circuit_hash: str | None = None,
        n_qubits: int,
        tags: dict[str, Any] | None = None,
    ) -> Shot:
        """Store a new shot in the repository.

        Args:
            counts: Measurement outcomes as bitstring -> count mapping.
            backend: Name of the quantum backend.
            circuit: The circuit (will be hashed).
            circuit_hash: Circuit hash directly.
            n_qubits: Number of qubits in the circuit.
            tags: Additional metadata tags.

        Returns:
            The created Shot object.
        """
        if circuit is not None:
            computed_hash = circuit_to_hash(circuit)
        elif circuit_hash is not None:
            computed_hash = circuit_hash
        else:
            raise ValueError("Either circuit or circuit_hash must be provided")

        payload = {
            "counts": counts,
            "backend": backend,
            "circuit_hash": computed_hash,
            "n_qubits": n_qubits,
            "tags": tags or {},
        }

        response = self.client.post("/shots", json=payload)
        response.raise_for_status()

        return self._parse_shot(response.json())

    def get_shot(self, shot_id: str) -> Shot:
        """Get a specific shot by ID."""
        response = self.client.get(f"/shots/{shot_id}")
        response.raise_for_status()
        return self._parse_shot(response.json())

    def health_check(self) -> bool:
        """Check if the server is healthy."""
        try:
            response = self.client.get("/health")
            return response.status_code == 200
        except httpx.RequestError:
            return False

    @staticmethod
    def _parse_shot(data: dict[str, Any]) -> Shot:
        """Parse a shot from JSON response."""
        return Shot(
            id=data["id"],
            counts=data["counts"],
            metadata=ShotMetadata(
                backend=data["backend"],
                n_qubits=data["n_qubits"],
                timestamp=datetime.fromisoformat(data["timestamp"]),
                circuit_hash=data["circuit_hash"],
                tags=data.get("tags", {}),
            ),
        )


# Global default client instance
_default_client: OSRClient | None = None


def get_client() -> OSRClient:
    """Get the default global client instance."""
    global _default_client
    if _default_client is None:
        _default_client = OSRClient()
    return _default_client


def set_client(client: OSRClient) -> None:
    """Set the default global client instance."""
    global _default_client
    _default_client = client
