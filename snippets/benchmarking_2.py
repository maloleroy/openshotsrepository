import openshots as osr
from openshots.filters import circuit, n_qubits

osr.results().filter(circuit == qc and n_qubits == 50)