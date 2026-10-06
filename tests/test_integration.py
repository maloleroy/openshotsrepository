"""Integration tests that require a running server.

Run these with:
    OSR_INTEGRATION_TESTS=1 OSR_SERVER_URL=http://localhost:8000 \
        uv run pytest tests/test_integration.py -v

Make sure the server is running:
    cd ../server && DATABASE_URL=postgres://... cargo run --locked
"""

import os

import pytest

# Skip all tests if server is not available
pytestmark = pytest.mark.skipif(
    os.environ.get("OSR_INTEGRATION_TESTS") != "1",
    reason="Integration tests disabled. Set OSR_INTEGRATION_TESTS=1 to run.",
)


@pytest.fixture
def client():
    """Get a client connected to the test server."""
    from openshots.client import OSRClient

    client = OSRClient(
        base_url=os.environ.get("OSR_SERVER_URL", "http://localhost:8000")
    )
    yield client
    client.close()


class TestIntegration:
    def test_health_check(self, client):
        assert client.health_check() is True

    def test_store_and_retrieve_shot(self, client):
        # Store a shot
        shot = client.store_shot(
            counts={"00": 500, "11": 500},
            backend="integration_test",
            circuit_hash="a" * 64,
            n_qubits=2,
            tags={"test": True},
        )

        assert shot.id is not None
        assert shot.counts == {"00": 500, "11": 500}
        assert shot.metadata.backend == "integration_test"

        # Retrieve it
        retrieved = client.get_shot(shot.id)
        assert retrieved.id == shot.id
        assert retrieved.counts == shot.counts

    def test_query_with_filters(self, client):
        # Store shots with different properties
        for i, backend in enumerate(["backend_a", "backend_a", "backend_b"]):
            client.store_shot(
                counts={"00": 100 + i},
                backend=backend,
                circuit_hash=str(i) * 64,
                n_qubits=2,
            )

        # Query with filter
        shots = client.query_shots(backend="backend_a")
        assert len(shots) >= 2
        for shot in shots:
            assert shot.metadata.backend == "backend_a"

    def test_query_interface(self, client):
        from openshots import results

        # Store a shot
        client.store_shot(
            counts={"00": 250, "11": 250},
            backend="query_interface_test",
            circuit_hash="b" * 64,
            n_qubits=2,
        )

        # Query using the results interface
        query = results(client).filter(backend="query_interface_test")
        count = query.count()
        assert count >= 1

        # Test iteration
        for counts in query:
            assert isinstance(counts, dict)
            assert all(isinstance(k, str) for k in counts)

    def test_concat_results(self, client):
        from openshots import results_int

        # Store multiple shots
        for _ in range(3):
            client.store_shot(
                counts={"00": 100, "11": 100},
                backend="concat_test",
                circuit_hash="c" * 64,
                n_qubits=2,
            )

        # Concat results
        query = results_int(client).filter(backend="concat_test", circuit_hash="c" * 64)
        combined = query.concat()

        assert isinstance(combined, dict)
        # All keys should be integers
        assert all(isinstance(k, int) for k in combined)
        # Should have 0 (for "00") and 3 (for "11") as keys
        assert 0 in combined or 3 in combined


def test_v2_cache_round_trip_and_autostore(client):
    from types import SimpleNamespace
    from uuid import uuid4

    from qiskit import ClassicalRegister, QuantumCircuit, QuantumRegister
    from qiskit.primitives import StatevectorSampler

    from openshots import SamplerCache
    from openshots.cache import _joint_counts

    backend = f"integration_v2_{uuid4()}"
    q = QuantumRegister(2, "q")
    a = ClassicalRegister(1, "alpha")
    b = ClassicalRegister(1, "beta")
    qc = QuantumCircuit(q, a, b)
    qc.h(0)
    qc.cx(0, 1)
    qc.measure(0, a)
    qc.measure(1, b)
    client.store_shot({"00": 10, "11": 10}, backend=backend, circuit=qc, n_qubits=2)

    class HitSampler:
        def __init__(self):
            self.backend = SimpleNamespace(name=backend, simulator=False)

        def run(self, pubs, *, shots):
            raise AssertionError("hardware called on cache hit")

    result = SamplerCache(HitSampler(), client).run([qc, qc], shots=7)
    assert result.from_cache
    actual = result.result()
    assert len(actual) == 2
    assert sum(_joint_counts(qc, actual[0].data, ()).values()) == 7
    simulator = SamplerCache(
        StatevectorSampler(seed=1),
        client,
        _backend_name=f"{backend}_sim",
        result_kind="simulation_counts",
    )
    job = simulator.run(qc, shots=11)
    assert not job.from_cache
    returned = job.result()
    assert job.result() is returned
    rows = client.query_shots(backend=f"{backend}_sim")
    assert len(rows) == 1 and sum(rows[0].counts.values()) == 11
    assert rows[0].metadata.result_kind == "simulation_counts"
