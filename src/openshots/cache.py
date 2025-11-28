"""Caching wrappers for quantum primitives."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

from openshots.client import get_client
from openshots.models import circuit_to_hash

if TYPE_CHECKING:
    from openshots.client import OSRClient


@runtime_checkable
class SamplerLike(Protocol):
    """Protocol for sampler-like objects (e.g., Qiskit's Sampler)."""

    def run(self, circuits: Any, **kwargs: Any) -> Any:
        """Run circuits and return a job."""
        ...


@dataclass
class CachedJob:
    """A job that may be served from cache or run on hardware."""

    _result: Any | None = None
    _backend_job: Any | None = None
    _from_cache: bool = False

    def result(self) -> Any:
        """Get the result, blocking if necessary."""
        if self._result is not None:
            return self._result
        if self._backend_job is not None:
            return self._backend_job.result()
        raise RuntimeError("No result available")

    @property
    def from_cache(self) -> bool:
        """Whether this result was served from cache."""
        return self._from_cache


@dataclass
class CachedResult:
    """A result that mimics Qiskit's SamplerResult."""

    quasi_dists: list[dict[int, float]]
    """Quasi-probability distributions for each circuit."""

    metadata: list[dict[str, Any]] = field(default_factory=list)
    """Metadata for each circuit."""

    @classmethod
    def from_counts(
        cls, counts: dict[str, int], shots: int | None = None
    ) -> CachedResult:
        """Create a CachedResult from counts dict.

        Args:
            counts: Bitstring -> count mapping.
            shots: Total number of shots (inferred if not provided).

        Returns:
            A CachedResult mimicking Qiskit's format.
        """
        if shots is None:
            shots = sum(counts.values())

        # Convert to quasi-probability distribution
        quasi_dist = {int(k, 2): v / shots for k, v in counts.items()}

        return cls(
            quasi_dists=[quasi_dist],
            metadata=[{"shots": shots}],
        )


@dataclass
class SamplerCache:
    """A caching wrapper for Qiskit's Sampler.

    Transparently caches results from the Open Shots Repository,
    falling back to the underlying sampler when no cached data exists.

    Example:
        >>> from qiskit_ibm_runtime import Sampler
        >>> qiskit_sampler = Sampler(...)
        >>> sampler = osr.SamplerCache(qiskit_sampler)
        >>> job = sampler.run(circuit, shots=1024)
        >>> result = job.result()
    """

    sampler: SamplerLike
    """The underlying sampler to wrap."""

    client: OSRClient | None = None
    """OSR client to use. Uses the default client if not provided."""

    auto_store: bool = True
    """Whether to automatically store results in the repository."""

    _backend_name: str | None = None

    def __post_init__(self) -> None:
        # Try to extract backend name from sampler
        if self._backend_name is None:
            self._backend_name = self._infer_backend_name()

    def _infer_backend_name(self) -> str:
        """Try to infer the backend name from the sampler."""
        # Try common attributes
        for attr in ("backend", "_backend", "session"):
            obj = getattr(self.sampler, attr, None)
            if obj is not None:
                name = getattr(obj, "name", None)
                if name is not None:
                    return str(name)
        return "unknown"

    @property
    def osr_client(self) -> OSRClient:
        """Get the OSR client."""
        if self.client is None:
            return get_client()
        return self.client

    def run(
        self,
        circuits: Any,
        *,
        shots: int = 1024,
        **kwargs: Any,
    ) -> CachedJob:
        """Run circuits, using cache when possible.

        Args:
            circuits: Circuit or list of circuits to run.
            shots: Number of shots to execute.
            **kwargs: Additional arguments passed to the underlying sampler.

        Returns:
            A CachedJob that provides the result.
        """
        # Handle single circuit
        if not isinstance(circuits, (list, tuple)):
            circuits = [circuits]

        # Try to get from cache
        for circuit in circuits:
            circuit_hash = circuit_to_hash(circuit)
            try:
                n_qubits = circuit.num_qubits
            except AttributeError:
                n_qubits = 0

            try:
                cached_shots = self.osr_client.query_shots(
                    circuit_hash=circuit_hash,
                    backend=self._backend_name,
                    limit=1,
                )

                if cached_shots:
                    # Sum up cached counts
                    total_counts: dict[str, int] = {}
                    for shot in cached_shots:
                        for k, v in shot.counts.items():
                            total_counts[k] = total_counts.get(k, 0) + v

                    total_cached = sum(total_counts.values())
                    if total_cached >= shots:
                        # Enough cached shots, return from cache
                        result = CachedResult.from_counts(total_counts, shots)
                        return CachedJob(_result=result, _from_cache=True)
            except Exception:
                # Cache lookup failed, fall through to sampler
                pass

        # Run on actual hardware
        job = self.sampler.run(circuits, shots=shots, **kwargs)

        if self.auto_store:
            # TODO: Store results after job completes
            # This would require async handling or a callback
            pass

        return CachedJob(_backend_job=job, _from_cache=False)
