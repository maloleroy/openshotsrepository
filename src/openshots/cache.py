"""Qiskit sampler caching with exact shot counts, PUB shapes and joint registers."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Callable, Protocol, runtime_checkable
import logging
import httpx
from openshots.client import get_client, OSRClient
from openshots.models import circuit_to_hash

log = logging.getLogger(__name__)
@runtime_checkable
class SamplerLike(Protocol):
    def run(self, circuits: Any, **kwargs: Any) -> Any: ...

@dataclass
class CachedJob:
    _result: Any | None = None
    _backend_job: Any | None = None
    _from_cache: bool = False
    _on_result: Callable | None = None
    def result(self, *args, **kwargs):
        if self._result is None:
            if self._backend_job is None:
                raise RuntimeError('No result available')
            self._result = self._backend_job.result(*args, **kwargs)
            callback, self._on_result = self._on_result, None
            if callback is not None:
                try:
                    callback(self._result)
                except (httpx.HTTPError, ValueError, TypeError) as error:
                    log.warning('OSR could not store sampler result: %s', error)
        return self._result
    @property
    def from_cache(self):
        return self._from_cache
    def __getattr__(self, name):
        if self._backend_job is not None:
            return getattr(self._backend_job, name)
        if name == 'job_id':
            return lambda: None
        raise AttributeError(name)

@dataclass
class CachedResult:
    quasi_dists: list[dict[int, float]]
    metadata: list[dict[str, Any]] = field(default_factory=list)
    @classmethod
    def from_counts(cls, counts, shots=None):
        total = sum(counts.values())
        if total <= 0 or (shots is not None and shots != total):
            raise ValueError('shots must equal the sum of positive counts')
        if any(type(v) is not int or v <= 0 for v in counts.values()):
            raise ValueError('counts must be positive integers')
        return cls([{int(k, 2): v / total for k, v in counts.items()}], [{'shots': total, 'shot_order': 'reconstructed_from_counts'}])

@dataclass
class SamplerCache:
    sampler: SamplerLike
    client: OSRClient | None = None
    auto_store: bool = True
    _backend_name: str | None = None
    executed_after: str | None = None
    executed_before: str | None = None
    calibration_id: str | None = None
    result_kind: str | None = None
    def __post_init__(self):
        if self._backend_name is None:
            self._backend_name = self._infer_backend_name()
    def _backend(self):
        for attr in ('backend', '_backend'):
            obj = getattr(self.sampler, attr, None)
            if callable(obj):
                obj = obj()
            if obj is not None:
                return obj
        return None
    def _infer_backend_name(self):
        obj = self._backend()
        name = getattr(obj, 'name', None)
        if callable(name):
            name = name()
        return name if isinstance(name, str) else 'unknown'
    @property
    def osr_client(self):
        return self.client or get_client()
    def _origin(self):
        if self.result_kind is not None:
            return self.result_kind
        obj = self._backend()
        simulator = getattr(obj, 'simulator', None)
        if hasattr(obj, 'configuration'):
            simulator = getattr(obj.configuration(), 'simulator', simulator)
        if simulator is True:
            return 'simulation_counts'
        if simulator is False or type(self.sampler).__module__.startswith('qiskit_ibm_runtime'):
            return 'hardware_counts'
        return 'unknown_counts'
    def _lookup(self, circuit, shots):
        if self._backend_name == 'unknown' or not 1 <= circuit.num_clbits <= 256:
            return None
        try:
            response = self.osr_client.sample_cache(backend=self._backend_name, circuit_hash=circuit_to_hash(circuit), n_qubits=circuit.num_clbits, shots=shots, executed_after=self.executed_after, executed_before=self.executed_before, calibration_id=self.calibration_id)
        except httpx.HTTPError as error:
            log.debug('OSR cache unavailable: %s', error)
            return None
        if not response['hit']:
            return None
        counts = response['counts']
        if sum(counts.values()) != shots or any(type(n) is not int or n <= 0 for n in counts.values()) or any(len(k) != circuit.num_clbits or set(k) - {'0', '1'} for k in counts):
            raise ValueError('invalid cache response')
        return response
    def run(self, circuits, *, shots=1024, **kwargs):
        from qiskit import QuantumCircuit
        from qiskit.primitives import BaseSamplerV2
        import inspect
        is_v2 = isinstance(self.sampler, BaseSamplerV2) or 'pubs' in inspect.signature(self.sampler.run).parameters
        items = [circuits] if isinstance(circuits, QuantumCircuit) else list(circuits)
        if not items:
            raise ValueError('at least one circuit is required')
        if type(shots) is not int or shots <= 0:
            raise ValueError('shots must be a positive integer')
        if is_v2:
            return self._run_v2(items, shots, kwargs)
        # V1 binding is explicit; unsupported run options bypass cache.
        bound = items
        parameters = kwargs.get('parameter_values')
        if parameters is not None:
            if len(parameters) != len(items):
                raise ValueError('parameter_values must match circuits')
            bound = [qc.assign_parameters(values) for qc, values in zip(items, parameters)]
        hits = []
        if not (set(kwargs) - {'parameter_values'}):
            for qc in bound:
                hit = self._lookup(qc, shots)
                if hit is None:
                    break
                hits.append(hit)
        if len(hits) == len(items):
            distributions = [CachedResult.from_counts(h['counts'], shots) for h in hits]
            return CachedJob(CachedResult([r.quasi_dists[0] for r in distributions], [{**r.metadata[0], 'collection_ids': h['collection_ids']} for r, h in zip(distributions, hits)]), _from_cache=True)
        job = self.sampler.run(items, shots=shots, **kwargs)
        def store(result):
            # V1 exposes quasi distributions rather than raw joint observations.
            for qc, dist in zip(bound, result.quasi_dists):
                circuit = self.osr_client.store_circuit(qc)
                self.osr_client.store_collection(dict(dist), metadata={'result_kind': 'quasi_probabilities', 'n_qubits': qc.num_clbits, 'backend': self._backend_name, 'circuit_hash': circuit['circuit_hash'], 'circuit_id': circuit['id'], 'circuit_association': 'confirmed', 'metadata': {'sampler': 'V1', 'requested_shots': shots}})
        return CachedJob(_backend_job=job, _on_result=store if self.auto_store else None)
    def _run_v2(self, items, shots, kwargs):
        import numpy as np
        from qiskit.primitives.containers.sampler_pub import SamplerPub
        from qiskit.primitives import BitArray, DataBin, SamplerPubResult, PrimitiveResult
        pubs = [SamplerPub.coerce(item, shots) for item in items]
        bound_arrays = [pub.parameter_values.bind_all(pub.circuit) for pub in pubs]
        hits = []
        compatible = all(_register_bits(pub.circuit) for pub in pubs)
        if compatible and not kwargs:
            for pub, bound in zip(pubs, bound_arrays):
                pub_hits = []
                for loc in np.ndindex(pub.shape):
                    hit = self._lookup(bound[loc], pub.shots)
                    if hit is None:
                        break
                    pub_hits.append(hit)
                if len(pub_hits) != bound.size:
                    break
                hits.append(pub_hits)
        if len(hits) == len(pubs):
            results = []
            for pub, pub_hits in zip(pubs, hits):
                array = np.empty(pub.shape + (pub.shots, (pub.circuit.num_clbits + 7) // 8), dtype=np.uint8)
                for loc, hit in zip(np.ndindex(pub.shape), pub_hits):
                    samples = (int(state, 2) for state, count in hit['counts'].items() for _ in range(count))
                    array[loc] = BitArray.from_samples(samples, pub.circuit.num_clbits).array
                joint = BitArray(array, pub.circuit.num_clbits)
                data = {reg.name: joint.slice_bits([pub.circuit.find_bit(bit).index for bit in reg]) for reg in pub.circuit.cregs}
                results.append(SamplerPubResult(DataBin(shape=pub.shape, **data), {'shots': pub.shots, 'osr': {'shot_order': 'reconstructed_from_counts', 'collection_ids': [h['collection_ids'] for h in pub_hits]}}))
            return CachedJob(PrimitiveResult(results, metadata={'osr_cache': True}), _from_cache=True)
        job = self.sampler.run(pubs, shots=shots, **kwargs)
        def store(result):
            if not compatible:
                return
            if len(result) != len(pubs):
                raise ValueError('sampler returned wrong number of PUB results')
            job_id = getattr(job, 'job_id', lambda: None)()
            for pub, bound, res in zip(pubs, bound_arrays, result):
                # Reconstruct classical positions from aligned register shots, preserving correlations.
                for loc in np.ndindex(pub.shape):
                    counts = _joint_counts(pub.circuit, res.data, loc)
                    circuit = self.osr_client.store_circuit(bound[loc])
                    execution = self.osr_client.create_resource('executions', {'backend': self._backend_name, 'circuit_id': circuit['id'], 'job_id': job_id, 'data': {'pub_shape': list(pub.shape), 'parameter_index': list(loc), 'sampler_metadata': _jsonable(res.metadata)}})
                    self.osr_client.store_collection(counts, metadata={'result_kind': self._origin(), 'n_qubits': pub.circuit.num_clbits, 'backend': self._backend_name, 'circuit_hash': circuit['circuit_hash'], 'circuit_id': circuit['id'], 'execution_id': execution['id'], 'circuit_association': 'confirmed', 'metadata': {'sampler': 'V2', 'requested_shots': pub.shots}})
        return CachedJob(_backend_job=job, _on_result=store if self.auto_store else None)

def _register_bits(circuit):
    return bool(circuit.cregs) and set(circuit.clbits) == {bit for reg in circuit.cregs for bit in reg}

def _joint_counts(circuit, data, loc):
    registers = [(reg, data[reg.name]) for reg in circuit.cregs]
    nshots = registers[0][1].num_shots
    if any(bits.num_shots != nshots or bits.num_bits != len(reg) for reg, bits in registers):
        raise ValueError('register data dimensions differ from circuit')
    counts = {}
    for shot in range(nshots):
        state = 0
        seen = {}
        for reg, bits in registers:
            value = int.from_bytes(bits.array[loc][shot].tobytes(), 'big')
            for i, bit in enumerate(reg):
                position = circuit.find_bit(bit).index
                actual = (value >> i) & 1
                if position in seen and seen[position] != actual:
                    raise ValueError('overlapping registers disagree')
                seen[position] = actual
                state |= actual << position
        counts[state] = counts.get(state, 0) + 1
    return counts

def _jsonable(value):
    import json
    return json.loads(json.dumps(value, default=lambda v: v.tolist() if hasattr(v, 'tolist') else str(v)))
