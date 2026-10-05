"""Integration tests that require a running server.

Run these with: OSR_SERVER_URL=http://localhost:8000 uv run pytest tests/test_integration.py -v

Make sure the server is running:
    cd ../server && cargo run
"""

import os
import pytest

# Skip all tests if server is not available
pytestmark = pytest.mark.skipif(
    os.environ.get("OSR_INTEGRATION_TESTS") != "1",
    reason="Integration tests disabled. Set OSR_INTEGRATION_TESTS=1 to run."
)


@pytest.fixture
def client():
    """Get a client connected to the test server."""
    from openshots.client import OSRClient
    client = OSRClient(base_url=os.environ.get("OSR_SERVER_URL", "http://localhost:8000"))
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
            assert all(isinstance(k, str) for k in counts.keys())

    def test_concat_results(self, client):
        from openshots import results_int

        # Store multiple shots
        for i in range(3):
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
        assert all(isinstance(k, int) for k in combined.keys())
        # Should have 0 (for "00") and 3 (for "11") as keys
        assert 0 in combined or 3 in combined
