# OSR 0.2 client extensions

The README and existing high-level functions are preserved: OSRClient, results/results_int, filter/concat/all/first/count and SamplerCache. Python 3.13+, Qiskit 2.3+ and PostgreSQL-backed OSR 0.2 are supported. The editable package and wheel build use hatchling.

## Typed collections and streaming

```python
from openshots import OSRClient

with OSRClient() as client:
    for collection in client.iter_collections(result_kind="hardware_counts", backend="ibm_boston"):
        print(collection.id, collection.metadata["shots"])
        for state, occurrences in collection.iter_entries():
            pass  # state is an integer with up to 256 bits
```

`query_shots()` and `.all()` materialize Shot objects as before. Query iteration loads one collection at a time; `Collection.iter_entries()` loads only one binary block. `Collection.values(as_int=True)` explicitly materializes a distribution. Float collections stay accessible through the collection API and are never silently converted to counts. `ShotMetadata.timestamp` is ingestion time; `executed_at` is separate and can be unknown.

Use `store_collection(values, metadata=...)` for count/float mappings, or `store_entries(sorted_entries, metadata=..., idempotency_key=...)` for bounded-memory uploads. Entries must be unique and numerically sorted, states must fit the declared width, and counts must be positive u32. Retries verify the uploaded chunks; changed content under the same key fails. For resumable custom importers, use start_upload/upload_status/put_chunk/finalize_upload.

`store_circuit(qc, problem_id=..., qaoa_p=..., data=...)` fingerprints bound QASM3 bytes. Circuits unsupported by QASM3 export (for example initialize) use an explicit artifact-sha256-v1 QPY fingerprint. Use `store_artifact`, `create_resource`, `get_resource` and `iter_resources` for original circuit archives, sources, problems, solutions, calibration and executions. `get_artifact` validates the content checksum. Every server resource ID is UUIDv4; fingerprints are separate content hashes.

## SamplerCache

The wrapper supports V2 PUB batches, parameter sweeps and classical registers, plus legacy V1 sampler results. A cache hit uses only confirmed hardware counts from the requested backend and exact bound circuit/width. Historical runs can be combined. Set executed_after/executed_before/calibration_id on the wrapper for narrower reuse.

Each request receives exactly its requested observation count. Counts retain joint register correlations; cached shot order is reconstructed and labeled. If one PUB/parameter point misses, the entire batch delegates to the wrapped sampler. Unsupported run options also delegate. HTTP cache failures delegate; malformed cached data raises an error.

Auto-storage occurs once when a delegated job's result is retrieved. V2 raw observations retain register correlations, bound parameters and job ID. Simulator results are labeled simulation_counts when backend evidence establishes that; unknown origins stay unknown_counts. `result_kind=` can explicitly declare origin when a provider cannot expose it. V1 quasi distributions are stored as quasi_probabilities and cannot satisfy the hardware cache.

Parent/backend job methods remain available through delegation. Cached jobs return `from_cache=True`; cached V2 results are normal Qiskit PrimitiveResult/SamplerPubResult/DataBin/BitArray objects.

## Filters and server setup

`results([fields.solution(int), fields.estimate])` also supports the field descriptors already exposed by the package. The solution projection means the most frequent observed outcome; it does not assert problem optimality. Missing estimates remain None. Metadata filters such as problem_id, qaoa_p, result_kind, execution time and include_superseded can be passed to `.filter()`; typed distributions use the collection API.

Both the unchanged README expression and ordinary parenthesized `&` expressions work. Python `and` raises an explicit error because it would otherwise drop a condition. Prefer `(backend == name) & (n_qubits == width)`.

The server now requires DATABASE_URL for PostgreSQL. See `../server/docs/deployment.md`, `api.md`, `database-design.md` and `importing.md` for startup, immutable versions, binary encoding and historical-data imports. No public deployment is performed by the local test suite.
