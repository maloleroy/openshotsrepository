"""Tests for the filters module."""

import pytest

from openshots.filters import backend, circuit, circuit_hash, n_qubits
from openshots.query import FilterCondition


class TestFilterFields:
    def test_backend_equality(self) -> None:
        condition = backend == "ibm_aachen"
        assert isinstance(condition, FilterCondition)
        assert condition.to_dict() == {"backend": "ibm_aachen"}

    def test_n_qubits_equality(self) -> None:
        condition = n_qubits == 5
        assert isinstance(condition, FilterCondition)
        assert condition.to_dict() == {"n_qubits": 5}

    def test_circuit_hash_equality(self) -> None:
        condition = circuit_hash == "abc123"
        assert isinstance(condition, FilterCondition)
        assert condition.to_dict() == {"circuit_hash": "abc123"}

    def test_combining_conditions(self) -> None:
        cond1 = backend == "ibm_aachen"
        cond2 = n_qubits == 5
        combined = cond1 & cond2
        assert combined.to_dict() == {"backend": "ibm_aachen", "n_qubits": 5}


class TestCircuitFilter:
    def test_circuit_filter_hashes_input(self) -> None:
        from qiskit import QuantumCircuit

        condition = circuit == QuantumCircuit(2)
        result = condition.to_dict()
        assert "circuit_hash" in result
        assert len(result["circuit_hash"]) == 64  # SHA256 hex


def test_readme_expression_preserves_both_filters():
    assert (backend == "ibm_aachen" & n_qubits == 5).to_dict() == {
        "backend": "ibm_aachen",
        "n_qubits": 5,
    }


def test_python_and_does_not_silently_drop_a_filter():
    with pytest.raises(TypeError, match="combine"):
        _ = (backend == "ibm_aachen") and (n_qubits == 5)
