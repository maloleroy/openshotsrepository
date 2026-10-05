"""HTTP API, immutable resources and chunked result transport."""
from __future__ import annotations
import os
from dataclasses import dataclass
from typing import Any
from collections.abc import Iterable, Mapping
import httpx
from openshots.models import Shot, Collection, circuit_bytes, circuit_to_hash
from openshots.binary import normalize, encode_blocks

@dataclass
class OSRClient:
    base_url: str = 'http://localhost:8000'
    timeout: float = 30.0
    _client: httpx.Client | None = None
    def __post_init__(self):
        self.base_url = os.environ.get('OSR_SERVER_URL', self.base_url)
    @property
    def client(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(base_url=self.base_url, timeout=self.timeout)
        return self._client
    def close(self):
        if self._client is not None:
            self._client.close()
            self._client = None
    def __enter__(self):
        return self
    def __exit__(self, *args):
        self.close()
    def _json(self, method: str, path: str, **kwargs):
        response = self.client.request(method, path, **kwargs)
        response.raise_for_status()
        return response.json()
    @staticmethod
    def _headers(idempotency_key):
        return {'Idempotency-Key': idempotency_key} if idempotency_key is not None else {}
    def create_resource(self, resource: str, data: dict, *, idempotency_key: str | None = None) -> dict:
        if resource not in {'sources', 'problems', 'solutions', 'circuits', 'calibrations', 'executions'}:
            raise ValueError('unknown resource')
        return self._json('POST', f'/{resource}', json=data, headers=self._headers(idempotency_key))
    def get_resource(self, resource: str, resource_id: str) -> dict:
        return self._json('GET', f'/{resource}/{resource_id}')
    def iter_resources(self, resource: str, **filters):
        yield from self._pages(f'/{resource}', filters)
    def store_artifact(self, content: bytes, *, format: str, media_type: str = 'application/octet-stream') -> dict:
        return self._json('POST', '/artifacts', params={'format': format, 'media_type': media_type}, content=content)
    def get_artifact(self, artifact_id: str) -> bytes:
        import hashlib
        response = self.client.get(f'/artifacts/{artifact_id}')
        response.raise_for_status()
        if hashlib.sha256(response.content).hexdigest() != response.headers.get('X-Content-SHA256'):
            raise ValueError('artifact checksum mismatch')
        return response.content
    def store_circuit(self, circuit, *, problem_id=None, qaoa_p=None, data=None, idempotency_key=None):
        payload = circuit_bytes(circuit)
        artifact = self.store_artifact(payload, format='qasm3', media_type='text/plain')
        return self.create_resource('circuits', {'circuit_hash': artifact['sha256'], 'fingerprint_scheme': 'qasm3-sha256-v1', 'fingerprint_artifact_id': artifact['id'], 'n_qubits': circuit.num_qubits, 'n_clbits': circuit.num_clbits, 'problem_id': problem_id, 'qaoa_p': qaoa_p, 'data': {**(data or {}), 'bound': True}}, idempotency_key=idempotency_key)
    def start_upload(self, metadata: dict, *, idempotency_key=None) -> dict:
        return self._json('POST', '/uploads', json=metadata, headers=self._headers(idempotency_key))
    def upload_status(self, upload_id: str) -> dict:
        return self._json('GET', f'/uploads/{upload_id}')
    def put_chunk(self, upload_id: str, index: int, payload: bytes):
        response = self.client.put(f'/uploads/{upload_id}/chunks/{index}', content=payload, headers={'Content-Type': 'application/vnd.osr.osb1'})
        response.raise_for_status()
    def finalize_upload(self, upload_id: str) -> Collection:
        return Collection(self._json('POST', f'/uploads/{upload_id}/finalize'), self)
    def store_entries(self, entries: Iterable[tuple[int, int | float]], *, metadata: dict, idempotency_key=None) -> Collection:
        """Upload sorted entries without building a string-keyed histogram.

        Retrying with the same key verifies each chunk against existing data.
        """
        upload = self.start_upload(metadata, idempotency_key=idempotency_key)
        weighted = not metadata.get('result_kind', 'hardware_counts').endswith('_counts')
        count = 0
        for count, payload in enumerate(encode_blocks(entries, metadata['n_qubits'], weighted), 1):
            self.put_chunk(upload['id'], count - 1, payload)
        if not count:
            raise ValueError('empty collection')
        if upload['completed'] and self.get_collection(upload['id']).metadata['chunks'] != count:
            raise ValueError('idempotent retry has a different number of chunks')
        return self.finalize_upload(upload['id'])
    def store_collection(self, values: Mapping[str | int, int | float], *, metadata: dict, idempotency_key=None) -> Collection:
        weighted = not metadata.get('result_kind', 'hardware_counts').endswith('_counts')
        return self.store_entries(normalize(values, metadata['n_qubits'], weighted), metadata=metadata, idempotency_key=idempotency_key)
    def store_shot(self, counts: dict[str, int], *, backend: str, circuit=None, circuit_hash=None, n_qubits: int, tags=None, **metadata) -> Shot:
        if circuit is not None:
            record = self.store_circuit(circuit)
            if n_qubits != circuit.num_clbits:
                raise ValueError('n_qubits must equal the measured classical width')
            circuit_hash = record['circuit_hash']
            metadata.setdefault('circuit_id', record['id'])
        elif circuit_hash is None:
            raise ValueError('Either circuit or circuit_hash must be provided')
        idempotency_key = metadata.pop('idempotency_key', None)
        meta = {'result_kind': 'hardware_counts', 'backend': backend, 'n_qubits': n_qubits, 'circuit_hash': circuit_hash, 'circuit_association': 'confirmed', 'metadata': tags or {}, **metadata}
        collection = self.store_collection(counts, metadata=meta, idempotency_key=idempotency_key)
        return collection.shot()
    def _pages(self, path, filters):
        filters = {k: v for k, v in filters.items() if v is not None}
        remaining = filters.pop('limit', None)
        if remaining is not None and (type(remaining) is not int or remaining < 0):
            raise ValueError('limit must be a nonnegative integer')
        seen = set()
        while remaining is None or remaining > 0:
            page = self._json('GET', path, params={**filters, 'limit': min(1000, remaining) if remaining is not None else 100})
            for item in page['items']:
                yield item
                if remaining is not None:
                    remaining -= 1
            cursor = page['next_cursor']
            if cursor is None:
                break
            if cursor in seen:
                raise ValueError('repeated pagination cursor')
            seen.add(cursor)
            filters['cursor'] = cursor
    def iter_collections(self, *, circuit=None, circuit_hash=None, **filters):
        if circuit is not None:
            circuit_hash = circuit_to_hash(circuit)
        if circuit_hash is not None:
            filters['circuit_hash'] = circuit_hash
        for metadata in self._pages('/collections', filters):
            yield Collection(metadata, self)
    def get_collection(self, collection_id: str) -> Collection:
        return Collection(self._json('GET', f'/collections/{collection_id}'), self)
    def iter_shots(self, **filters):
        for collection in self.iter_collections(**filters):
            if not collection.weighted:
                yield collection.shot()
    def query_shots(self, *, backend=None, circuit=None, circuit_hash=None, n_qubits=None, limit=None, **filters) -> list[Shot]:
        return list(self.iter_shots(backend=backend, circuit=circuit, circuit_hash=circuit_hash, n_qubits=n_qubits, limit=limit, **filters))
    def get_shot(self, shot_id: str) -> Shot:
        return self.get_collection(shot_id).shot()
    def sample_cache(self, *, backend: str, circuit_hash: str, n_qubits: int, shots: int, **filters) -> dict:
        return self._json('POST', '/cache/sample', json={'backend': backend, 'circuit_hash': circuit_hash, 'n_qubits': n_qubits, 'shots': shots, **filters})
    def health_check(self) -> bool:
        try:
            return self.client.get('/health').status_code == 200
        except httpx.RequestError:
            return False

_default_client: OSRClient | None = None

def get_client() -> OSRClient:
    global _default_client
    if _default_client is None:
        _default_client = OSRClient()
    return _default_client

def set_client(client: OSRClient) -> None:
    global _default_client
    _default_client = client
