"""Wrap an existing Qiskit sampler without executing jobs at module import."""

from qiskit import QuantumCircuit

import openshots as osr


def run_cached(qiskit_sampler, qc: QuantumCircuit, *, shots: int = 1024):
    """Provide a bound measured circuit appropriate for the sampler's backend."""
    sampler = osr.SamplerCache(qiskit_sampler)
    job = sampler.run(qc, shots=shots)
    # A hit uses raw hardware counts from the same backend and bound circuit.
    # A miss calls the provider; .result() stores the returned result once.
    return job, job.result()
