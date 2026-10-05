"""Public data models. Ingestion time and execution time are separate."""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, TYPE_CHECKING
import hashlib
if TYPE_CHECKING:
    from openshots.client import OSRClient

@dataclass
class ShotMetadata:
    backend: str | None
    n_qubits: int
    timestamp: datetime
    circuit_hash: str | None
    tags: dict[str, Any] = field(default_factory=dict)
    result_kind: str = 'hardware_counts'
    executed_at: datetime | None = None
    provenance: dict[str, Any] = field(default_factory=dict)

@dataclass
class Shot:
    id: str
    counts: dict[str, int]
    metadata: ShotMetadata
    def counts_int(self) -> dict[int, int]:
        return {int(k, 2): v for k, v in self.counts.items()}

@dataclass
class Collection:
    """Metadata and lazy, bounded-memory access to a published result."""
    metadata: dict[str, Any]
    _client: OSRClient
    @property
    def id(self) -> str:
        return self.metadata['id']
    @property
    def weighted(self) -> bool:
        return not self.metadata['result_kind'].endswith('_counts')
    def iter_entries(self):
        from openshots.binary import decode_block
        previous = -1
        entries = 0
        total = 0
        for index in range(self.metadata['chunks']):
            response = self._client.client.get(f'/collections/{self.id}/chunks/{index}')
            response.raise_for_status()
            for state, value in decode_block(response.content, width=self.metadata['n_qubits'], weighted=self.weighted, checksum=response.headers.get('X-Content-SHA256')):
                if state <= previous:
                    raise ValueError('collection blocks overlap or are out of order')
                previous = state
                entries += 1
                total += value
                yield state, value
        if entries != self.metadata['entries'] or (not self.weighted and total != self.metadata['shots']):
            raise ValueError('collection totals differ from payloads')
    def values(self, *, as_int: bool = False) -> dict:
        width = self.metadata['n_qubits']
        return {state if as_int else format(state, f'0{width}b'): value for state, value in self.iter_entries()}
    def shot(self) -> Shot:
        if self.weighted:
            raise TypeError('weighted collections are distributions, not count histograms')
        m = self.metadata
        return Shot(self.id, self.values(), ShotMetadata(m['backend'], m['n_qubits'], datetime.fromisoformat(m['created_at']), m['circuit_hash'], m.get('metadata', {}), m['result_kind'], datetime.fromisoformat(m['executed_at']) if m.get('executed_at') else None, m))

def circuit_bytes(circuit: Any) -> bytes:
    from qiskit import QuantumCircuit
    from qiskit.qasm3 import dumps
    if not isinstance(circuit, QuantumCircuit):
        raise TypeError('expected a Qiskit QuantumCircuit; use circuit_hash for explicit fingerprints')
    if circuit.num_parameters:
        raise ValueError('bind circuit parameters before storing or querying')
    return dumps(circuit).encode('utf-8')

def circuit_to_hash(circuit: Any) -> str:
    return hashlib.sha256(circuit_bytes(circuit)).hexdigest()
