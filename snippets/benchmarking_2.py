"""Compose filter expressions with &, preserving both conditions."""

from qiskit import QuantumCircuit

import openshots as osr
from openshots.filters import circuit, n_qubits


def matching_results(qc: QuantumCircuit):
    # n_qubits is the measured classical width, not the physical device width.
    return osr.results().filter((circuit == qc) & (n_qubits == qc.num_clbits))
