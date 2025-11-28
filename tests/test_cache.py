"""Tests for the caching layer."""

import pytest
from unittest.mock import MagicMock, PropertyMock
from datetime import datetime

from openshots.cache import SamplerCache, CachedJob, CachedResult
from openshots.models import Shot, ShotMetadata


class TestCachedResult:
    def test_from_counts(self) -> None:
        counts = {"00": 500, "11": 500}
        result = CachedResult.from_counts(counts)

        assert len(result.quasi_dists) == 1
        assert result.quasi_dists[0] == {0: 0.5, 3: 0.5}
        assert result.metadata[0]["shots"] == 1000

    def test_from_counts_with_explicit_shots(self) -> None:
        counts = {"00": 500, "11": 500}
        result = CachedResult.from_counts(counts, shots=2000)

        assert result.quasi_dists[0] == {0: 0.25, 3: 0.25}
        assert result.metadata[0]["shots"] == 2000


class TestCachedJob:
    def test_result_from_cache(self) -> None:
        result = CachedResult.from_counts({"00": 100})
        job = CachedJob(_result=result, _from_cache=True)

        assert job.from_cache is True
        assert job.result() is result

    def test_result_from_backend(self) -> None:
        backend_result = MagicMock()
        backend_job = MagicMock()
        backend_job.result.return_value = backend_result

        job = CachedJob(_backend_job=backend_job, _from_cache=False)

        assert job.from_cache is False
        assert job.result() is backend_result

    def test_result_no_data_raises(self) -> None:
        job = CachedJob()
        with pytest.raises(RuntimeError, match="No result available"):
            job.result()


class TestSamplerCache:
    def test_infer_backend_name(self) -> None:
        mock_sampler = MagicMock()
        mock_sampler.backend = MagicMock(name="ibm_aachen")
        mock_sampler.backend.name = "ibm_aachen"

        cache = SamplerCache(sampler=mock_sampler)
        assert cache._backend_name == "ibm_aachen"

    def test_infer_backend_name_unknown(self) -> None:
        mock_sampler = MagicMock(spec=[])  # No attributes

        cache = SamplerCache(sampler=mock_sampler)
        assert cache._backend_name == "unknown"

    def test_run_cache_hit(self) -> None:
        mock_sampler = MagicMock()
        mock_client = MagicMock()

        # Mock a cached shot with enough data
        cached_shot = Shot(
            id="cached-1",
            counts={"00": 600, "11": 600},
            metadata=ShotMetadata(
                backend="ibm_aachen",
                n_qubits=2,
                timestamp=datetime.now(),
                circuit_hash="test_hash",
            ),
        )
        mock_client.query_shots.return_value = [cached_shot]

        cache = SamplerCache(sampler=mock_sampler, client=mock_client)

        # Mock circuit
        mock_circuit = MagicMock()
        mock_circuit.num_qubits = 2

        job = cache.run(mock_circuit, shots=1024)

        assert job.from_cache is True
        mock_sampler.run.assert_not_called()

    def test_run_cache_miss(self) -> None:
        mock_sampler = MagicMock()
        mock_sampler.run.return_value = MagicMock()

        mock_client = MagicMock()
        mock_client.query_shots.return_value = []  # No cached data

        cache = SamplerCache(sampler=mock_sampler, client=mock_client)

        mock_circuit = MagicMock()
        mock_circuit.num_qubits = 2

        job = cache.run(mock_circuit, shots=1024)

        assert job.from_cache is False
        mock_sampler.run.assert_called_once()

    def test_run_cache_insufficient_shots(self) -> None:
        mock_sampler = MagicMock()
        mock_sampler.run.return_value = MagicMock()

        mock_client = MagicMock()

        # Cache has only 500 shots, but we need 1024
        cached_shot = Shot(
            id="cached-1",
            counts={"00": 250, "11": 250},
            metadata=ShotMetadata(
                backend="ibm_aachen",
                n_qubits=2,
                timestamp=datetime.now(),
                circuit_hash="test_hash",
            ),
        )
        mock_client.query_shots.return_value = [cached_shot]

        cache = SamplerCache(sampler=mock_sampler, client=mock_client)

        mock_circuit = MagicMock()
        mock_circuit.num_qubits = 2

        job = cache.run(mock_circuit, shots=1024)

        assert job.from_cache is False
        mock_sampler.run.assert_called_once()

    def test_run_cache_error_falls_back(self) -> None:
        mock_sampler = MagicMock()
        mock_sampler.run.return_value = MagicMock()

        mock_client = MagicMock()
        mock_client.query_shots.side_effect = Exception("Connection error")

        cache = SamplerCache(sampler=mock_sampler, client=mock_client)

        mock_circuit = MagicMock()
        mock_circuit.num_qubits = 2

        job = cache.run(mock_circuit, shots=1024)

        assert job.from_cache is False
        mock_sampler.run.assert_called_once()
