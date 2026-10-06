"""Apply your mitigation function to matching stored count collections."""

from collections.abc import Callable

from qiskit import QuantumCircuit

import openshots as osr


def benchmark(
    qc: QuantumCircuit,
    perform_qem: Callable[[dict[str, int]], dict[str, int]],
    *,
    backend: str = "ibm_aachen",
):
    """Pass a bound measured circuit and your counts-to-counts mitigation function."""
    query = osr.results().filter(backend=backend).filter(circuit=qc)
    for before in query:
        yield before, perform_qem(before)


def combined_counts(qc: QuantumCircuit, *, backend: str = "ibm_aachen"):
    return osr.results().filter(backend=backend, circuit=qc).concat()


def combined_counts_int(qc: QuantumCircuit, *, backend: str = "ibm_aachen"):
    return osr.results_int().filter(backend=backend, circuit=qc).concat()
