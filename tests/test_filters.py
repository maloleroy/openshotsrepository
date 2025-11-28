"""Tests for the filters module."""

import pytest

from openshots.filters import backend, n_qubits, circuit_hash, circuit, CircuitFilter
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
        condition = circuit == "test_circuit_string"
        result = condition.to_dict()
        assert "circuit_hash" in result
        assert len(result["circuit_hash"]) == 64  # SHA256 hex
