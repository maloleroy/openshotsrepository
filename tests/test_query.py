"""Tests for the query interface."""

import pytest
from datetime import datetime
from unittest.mock import MagicMock

from openshots.query import ResultsQuery, results, results_int, FilterField, FilterCondition
from openshots.models import Shot, ShotMetadata


def make_shot(
    id: str,
    counts: dict[str, int],
    backend: str = "ibm_aachen",
    n_qubits: int = 2,
) -> Shot:
    """Helper to create test shots."""
    return Shot(
        id=id,
        counts=counts,
        metadata=ShotMetadata(
            backend=backend,
            n_qubits=n_qubits,
            timestamp=datetime.now(),
            circuit_hash="test_hash",
        ),
    )


class TestResultsQuery:
    def test_filter_returns_new_query(self) -> None:
        query1 = ResultsQuery()
        query2 = query1.filter(backend="ibm_aachen")
        assert query1 is not query2
        assert query1._filters == {}
        assert query2._filters == {"backend": "ibm_aachen"}

    def test_filter_chaining(self) -> None:
        query = (
            ResultsQuery()
            .filter(backend="ibm_aachen")
            .filter(n_qubits=5)
        )
        assert query._filters == {"backend": "ibm_aachen", "n_qubits": 5}

    def test_filter_with_condition(self) -> None:
        condition = FilterCondition(_conditions={"backend": "ibm_aachen"})
        query = ResultsQuery().filter(condition)
        assert query._filters == {"backend": "ibm_aachen"}

    def test_filter_and_conditions(self) -> None:
        cond1 = FilterCondition(_conditions={"backend": "ibm_aachen"})
        cond2 = FilterCondition(_conditions={"n_qubits": 5})
        combined = cond1 & cond2
        query = ResultsQuery().filter(combined)
        assert query._filters == {"backend": "ibm_aachen", "n_qubits": 5}


class TestResultsQueryExecution:
    def test_iter_returns_counts(self) -> None:
        mock_client = MagicMock()
        mock_client.iter_shots.return_value = [
            make_shot("1", {"00": 100, "11": 100}),
            make_shot("2", {"01": 50, "10": 50}),
        ]

        query = ResultsQuery(_client=mock_client)
        results_list = list(query)

        assert results_list == [
            {"00": 100, "11": 100},
            {"01": 50, "10": 50},
        ]

    def test_iter_as_int(self) -> None:
        mock_client = MagicMock()
        mock_client.iter_shots.return_value = [
            make_shot("1", {"00": 100, "11": 100}),
        ]

        query = ResultsQuery(_client=mock_client, _as_int=True)
        results_list = list(query)

        assert results_list == [{0: 100, 3: 100}]

    def test_concat(self) -> None:
        mock_client = MagicMock()
        mock_client.iter_shots.return_value = [
            make_shot("1", {"00": 100, "11": 100}),
            make_shot("2", {"00": 50, "01": 50}),
        ]

        query = ResultsQuery(_client=mock_client)
        combined = query.concat()

        assert combined == {"00": 150, "11": 100, "01": 50}

    def test_concat_as_int(self) -> None:
        mock_client = MagicMock()
        mock_client.iter_shots.return_value = [
            make_shot("1", {"00": 100, "11": 100}),
            make_shot("2", {"00": 50, "01": 50}),
        ]

        query = ResultsQuery(_client=mock_client, _as_int=True)
        combined = query.concat()

        assert combined == {0: 150, 3: 100, 1: 50}

    def test_count(self) -> None:
        mock_client = MagicMock()
        mock_client.iter_shots.return_value = [
            make_shot("1", {"00": 100}),
            make_shot("2", {"00": 100}),
            make_shot("3", {"00": 100}),
        ]

        query = ResultsQuery(_client=mock_client)
        mock_client.iter_collections.return_value = [type("Counts", (), {"weighted": False})() for _ in range(3)]
        assert query.count() == 3

    def test_first(self) -> None:
        mock_client = MagicMock()
        shot = make_shot("1", {"00": 100})
        mock_client.iter_shots.return_value = iter([shot])

        query = ResultsQuery(_client=mock_client)
        assert query.first() == shot

    def test_first_empty(self) -> None:
        mock_client = MagicMock()
        mock_client.iter_shots.return_value = iter([])

        query = ResultsQuery(_client=mock_client)
        assert query.first() is None

    def test_all(self) -> None:
        mock_client = MagicMock()
        shots = [make_shot("1", {"00": 100}), make_shot("2", {"11": 100})]
        mock_client.iter_shots.return_value = shots

        query = ResultsQuery(_client=mock_client)
        mock_client.query_shots.return_value = shots
        assert query.all() == shots


class TestFilterField:
    def test_equality(self) -> None:
        field = FilterField("backend")
        condition = field == "ibm_aachen"
        assert isinstance(condition, FilterCondition)
        assert condition.to_dict() == {"backend": "ibm_aachen"}


class TestModuleLevelFunctions:
    def test_results_creates_query(self) -> None:
        query = results()
        assert isinstance(query, ResultsQuery)
        assert query._as_int is False

    def test_results_int_creates_query(self) -> None:
        query = results_int()
        assert isinstance(query, ResultsQuery)
        assert query._as_int is True

    def test_results_with_client(self) -> None:
        mock_client = MagicMock()
        query = results(mock_client)
        assert query._client is mock_client
