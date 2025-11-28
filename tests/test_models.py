"""Tests for the data models."""

import pytest
from datetime import datetime

from openshots.models import Shot, ShotMetadata, circuit_to_hash


def _has_qiskit() -> bool:
    try:
        import qiskit  # noqa: F401
        return True
    except ImportError:
        return False


class TestShotMetadata:
    def test_creation(self) -> None:
        metadata = ShotMetadata(
            backend="ibm_aachen",
            n_qubits=5,
            timestamp=datetime(2024, 1, 1, 12, 0, 0),
            circuit_hash="abc123",
        )
        assert metadata.backend == "ibm_aachen"
        assert metadata.n_qubits == 5
        assert metadata.circuit_hash == "abc123"
        assert metadata.tags == {}

    def test_with_tags(self) -> None:
        metadata = ShotMetadata(
            backend="ibm_aachen",
            n_qubits=5,
            timestamp=datetime.now(),
            circuit_hash="abc123",
            tags={"experiment": "qem_test"},
        )
        assert metadata.tags == {"experiment": "qem_test"}


class TestShot:
    def test_creation(self) -> None:
        shot = Shot(
            id="shot-001",
            counts={"00": 500, "11": 500},
            metadata=ShotMetadata(
                backend="ibm_aachen",
                n_qubits=2,
                timestamp=datetime.now(),
                circuit_hash="abc123",
            ),
        )
        assert shot.id == "shot-001"
        assert shot.counts == {"00": 500, "11": 500}
        assert shot.metadata.backend == "ibm_aachen"

    def test_counts_int(self) -> None:
        shot = Shot(
            id="shot-001",
            counts={"00": 500, "11": 500, "01": 100, "10": 200},
            metadata=ShotMetadata(
                backend="ibm_aachen",
                n_qubits=2,
                timestamp=datetime.now(),
                circuit_hash="abc123",
            ),
        )
        int_counts = shot.counts_int()
        assert int_counts == {0: 500, 3: 500, 1: 100, 2: 200}

    def test_counts_int_larger_bitstrings(self) -> None:
        shot = Shot(
            id="shot-001",
            counts={"0000": 100, "1111": 200, "1010": 50},
            metadata=ShotMetadata(
                backend="ibm_aachen",
                n_qubits=4,
                timestamp=datetime.now(),
                circuit_hash="abc123",
            ),
        )
        int_counts = shot.counts_int()
        assert int_counts == {0: 100, 15: 200, 10: 50}


class TestCircuitToHash:
    def test_hash_string(self) -> None:
        """Hash of a simple string should be consistent."""
        hash1 = circuit_to_hash("test_circuit")
        hash2 = circuit_to_hash("test_circuit")
        assert hash1 == hash2
        assert len(hash1) == 64  # SHA256 hex digest

    def test_different_inputs_different_hash(self) -> None:
        hash1 = circuit_to_hash("circuit_a")
        hash2 = circuit_to_hash("circuit_b")
        assert hash1 != hash2

    @pytest.mark.skipif(
        not _has_qiskit(), reason="Qiskit not installed"
    )
    def test_hash_qiskit_circuit(self) -> None:
        from qiskit import QuantumCircuit

        qc = QuantumCircuit(2)
        qc.h(0)
        qc.cx(0, 1)

        hash1 = circuit_to_hash(qc)
        hash2 = circuit_to_hash(qc)
        assert hash1 == hash2
        assert len(hash1) == 64
