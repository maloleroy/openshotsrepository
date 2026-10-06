import hashlib

import httpx
import pytest

from openshots import OSRClient
from openshots.binary import encode_blocks


def metadata(id="one", **extra):
    return {
        "id": id,
        "result_kind": "hardware_counts",
        "n_qubits": 2,
        "backend": "device",
        "circuit_hash": "a" * 64,
        "created_at": "2026-01-01T00:00:00+00:00",
        "executed_at": None,
        "metadata": {"experiment": "test"},
        "entries": 2,
        "shots": 10,
        "chunks": 1,
        **extra,
    }


def block_response(mock, id="one", entries=None):
    payload = next(encode_blocks(entries or [(0, 4), (3, 6)], 2))
    mock.add_response(
        url=f"http://localhost:8000/collections/{id}/chunks/0",
        content=payload,
        headers={"X-Content-SHA256": hashlib.sha256(payload).hexdigest()},
    )


def test_lazy_client_and_health(httpx_mock):
    with OSRClient() as client:
        assert client._client is None
        httpx_mock.add_response(url="http://localhost:8000/health", status_code=503)
        assert not client.health_check()


def test_pagination_and_high_level_api(httpx_mock):
    httpx_mock.add_response(
        url=httpx.URL(
            "http://localhost:8000/collections",
            params={"backend": "device", "result_kind": "counts", "limit": 100},
        ),
        json={"items": [metadata()], "next_cursor": "one"},
    )
    block_response(httpx_mock)
    httpx_mock.add_response(
        url=httpx.URL(
            "http://localhost:8000/collections",
            params={
                "backend": "device",
                "cursor": "one",
                "result_kind": "counts",
                "limit": 100,
            },
        ),
        json={"items": [metadata("two")], "next_cursor": None},
    )
    block_response(httpx_mock, "two")
    with OSRClient() as client:
        shots = client.query_shots(backend="device")
    assert [s.id for s in shots] == ["one", "two"]
    assert shots[0].counts_int() == {0: 4, 3: 6}
    assert shots[0].metadata.executed_at is None


def test_upload_and_get_shot(httpx_mock):
    httpx_mock.add_response(
        url="http://localhost:8000/uploads",
        method="POST",
        json={"id": "one", "completed": False},
    )
    httpx_mock.add_response(
        url="http://localhost:8000/uploads/one/chunks/0", method="PUT", status_code=204
    )
    httpx_mock.add_response(
        url="http://localhost:8000/uploads/one/finalize", method="POST", json=metadata()
    )
    block_response(httpx_mock)
    httpx_mock.add_response(
        url="http://localhost:8000/collections/one", json=metadata()
    )
    block_response(httpx_mock)
    with OSRClient() as client:
        shot = client.store_shot(
            {"00": 4, "11": 6}, backend="device", circuit_hash="a" * 64, n_qubits=2
        )
        assert client.get_shot(shot.id).counts == shot.counts
    chunk = httpx_mock.get_requests()[1].content
    assert chunk[:4] == b"OSB1"


def test_weighted_results_do_not_become_shots(httpx_mock):
    httpx_mock.add_response(
        url="http://localhost:8000/collections?result_kind=counts&limit=100",
        json={
            "items": [metadata(result_kind="quasi_probabilities", shots=None)],
            "next_cursor": None,
        },
    )
    with OSRClient() as client:
        assert client.query_shots() == []


def test_invalid_count_input():
    from openshots.binary import encode_blocks, normalize

    with pytest.raises(ValueError):
        list(encode_blocks([(0, 2**32)], 2))
    with pytest.raises(ValueError):
        normalize({"0": 1}, 2)
    with (
        OSRClient() as client,
        pytest.raises(ValueError, match="circuit or circuit_hash"),
    ):
        client.store_shot({"00": 1}, backend="device", n_qubits=2)


def test_explicit_server_url_takes_precedence_over_environment(monkeypatch):
    monkeypatch.setenv("OSR_SERVER_URL", "http://environment:8000")
    assert OSRClient().base_url == "http://environment:8000"
    assert OSRClient("http://localhost:8000").base_url == "http://localhost:8000"


def test_migrated_user_tags_stay_accessible_through_shot_api(httpx_mock):
    data = metadata(
        metadata={
            "migration": "osr-sqlite-v0.1; original format",
            "legacy_tags": {"experiment": "old"},
        }
    )
    httpx_mock.add_response(url="http://localhost:8000/collections/one", json=data)
    block_response(httpx_mock)
    with OSRClient() as client:
        shot = client.get_shot("one")
    assert shot.metadata.tags == {"experiment": "old"}
    assert shot.metadata.provenance["metadata"]["migration"].startswith(
        "osr-sqlite-v0.1;"
    )
