"""Tests for the OSR client."""

import pytest
from datetime import datetime

import httpx
from pytest_httpx import HTTPXMock

from openshots.client import OSRClient
from openshots.models import Shot, ShotMetadata


class TestOSRClient:
    def test_default_base_url(self) -> None:
        client = OSRClient()
        assert client.base_url == "http://localhost:8000"

    def test_custom_base_url(self) -> None:
        client = OSRClient(base_url="http://custom:9000")
        assert client.base_url == "http://custom:9000"

    def test_context_manager(self) -> None:
        with OSRClient() as client:
            assert client._client is None  # Lazy init

    def test_health_check_success(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(url="http://localhost:8000/health", status_code=200)

        with OSRClient() as client:
            assert client.health_check() is True

    def test_health_check_failure(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(url="http://localhost:8000/health", status_code=500)

        with OSRClient() as client:
            assert client.health_check() is False


class TestOSRClientQueryShots:
    def test_query_shots_no_filters(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(
            url="http://localhost:8000/shots",
            json=[
                {
                    "id": "shot-001",
                    "counts": {"00": 500, "11": 500},
                    "backend": "ibm_aachen",
                    "n_qubits": 2,
                    "timestamp": "2024-01-01T12:00:00",
                    "circuit_hash": "abc123",
                    "tags": {},
                }
            ],
        )

        with OSRClient() as client:
            shots = client.query_shots()

        assert len(shots) == 1
        assert shots[0].id == "shot-001"
        assert shots[0].counts == {"00": 500, "11": 500}
        assert shots[0].metadata.backend == "ibm_aachen"

    def test_query_shots_with_backend_filter(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(
            url=httpx.URL("http://localhost:8000/shots", params={"backend": "ibm_aachen"}),
            json=[],
        )

        with OSRClient() as client:
            shots = client.query_shots(backend="ibm_aachen")

        assert shots == []

    def test_query_shots_with_multiple_filters(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(
            url=httpx.URL(
                "http://localhost:8000/shots",
                params={"backend": "ibm_aachen", "n_qubits": "5"},
            ),
            json=[],
        )

        with OSRClient() as client:
            shots = client.query_shots(backend="ibm_aachen", n_qubits=5)

        assert shots == []


class TestOSRClientStoreShot:
    def test_store_shot(self, httpx_mock: HTTPXMock) -> None:
        response_data = {
            "id": "shot-new",
            "counts": {"00": 100, "11": 100},
            "backend": "ibm_aachen",
            "n_qubits": 2,
            "timestamp": "2024-01-01T12:00:00",
            "circuit_hash": "test_hash",
            "tags": {},
        }
        httpx_mock.add_response(
            url="http://localhost:8000/shots",
            method="POST",
            json=response_data,
        )

        with OSRClient() as client:
            shot = client.store_shot(
                counts={"00": 100, "11": 100},
                backend="ibm_aachen",
                circuit_hash="test_hash",
                n_qubits=2,
            )

        assert shot.id == "shot-new"
        assert shot.counts == {"00": 100, "11": 100}

    def test_store_shot_requires_circuit(self) -> None:
        with OSRClient() as client:
            with pytest.raises(ValueError, match="circuit or circuit_hash"):
                client.store_shot(
                    counts={"00": 100},
                    backend="ibm_aachen",
                    n_qubits=2,
                )


class TestOSRClientGetShot:
    def test_get_shot(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(
            url="http://localhost:8000/shots/shot-001",
            json={
                "id": "shot-001",
                "counts": {"00": 500, "11": 500},
                "backend": "ibm_aachen",
                "n_qubits": 2,
                "timestamp": "2024-01-01T12:00:00",
                "circuit_hash": "abc123",
                "tags": {"experiment": "test"},
            },
        )

        with OSRClient() as client:
            shot = client.get_shot("shot-001")

        assert shot.id == "shot-001"
        assert shot.metadata.tags == {"experiment": "test"}
