"""Data models for the Open Shots Repository."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class ShotMetadata:
    """Metadata associated with a shot execution."""

    backend: str
    """Name of the quantum backend (e.g., 'ibm_aachen')."""

    n_qubits: int
    """Number of qubits in the circuit."""

    timestamp: datetime
    """When the shot was executed."""

    circuit_hash: str
    """Hash of the circuit for deduplication."""

    tags: dict[str, Any] = field(default_factory=dict)
    """Additional metadata tags."""


@dataclass
class Shot:
    """Represents a single circuit execution result."""

    id: str
    """Unique identifier for this shot."""

    counts: dict[str, int]
    """Measurement outcomes as bitstring -> count mapping."""

    metadata: ShotMetadata
    """Associated metadata."""

    def counts_int(self) -> dict[int, int]:
        """Return counts with integer keys instead of bitstrings."""
        return {int(k, 2): v for k, v in self.counts.items()}


def circuit_to_hash(circuit: Any) -> str:
    """Compute a hash for a quantum circuit.

    Supports Qiskit QuantumCircuit objects.
    """
    try:
        from qiskit import QuantumCircuit
        from qiskit.qasm3 import dumps

        if isinstance(circuit, QuantumCircuit):
            import hashlib

            qasm = dumps(circuit)
            return hashlib.sha256(qasm.encode()).hexdigest()
    except ImportError:
        pass

    # Fallback: use repr hash
    import hashlib

    return hashlib.sha256(repr(circuit).encode()).hexdigest()
