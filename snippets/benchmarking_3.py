"""Project the most frequent observed state and any stored estimate."""

from qiskit import QuantumCircuit

import openshots as osr
from openshots import fields as f


def observed_solutions(qc: QuantumCircuit, *, backend: str = "ibm_aachen"):
    # This is an observed outcome; problem optimality needs separate evidence.
    # The estimate can be None when no estimate was supplied.
    return osr.results([f.solution(int, f.higher_better), f.estimate]).filter(
        backend=backend, circuit=qc
    )
