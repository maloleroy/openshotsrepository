from qiskit_ibm_runtime import Sampler
import openshots as osr

qiskit_sampler = Sampler(...)
sampler = osr.SamplerCache(qiskit_sampler)
job = sampler.run(qc, shots=1024) # exact same use as the Qiskit sampler

# Here, if the Open Shots Repository contains 1024 or more
# shots for this circuit, backend and sampler options, it
# provides the result without needing to re-run the circuit.
# Otherwise, it simply calls the Qiskit sampler, store the result.
result = job.result()