# Open Shots Repository - Open data for Quantum Computing

A shared dynamic database of quantum computing circuit shots on real hardware.

## Installation

```bash
pip install openshots
# or with uv
uv add openshots
```

## Quick Start

### Query existing shots

```python
import openshots as osr

# Iterate over shots from a specific backend
for counts in osr.results().filter(backend="ibm_aachen"):
    print(counts)  # {"00": 500, "11": 500}

# Get combined counts as integers
combined = osr.results_int().filter(circuit=qc).concat()
# {0: 1000, 3: 500}
```

### Cache Qiskit Sampler calls

```python
from qiskit_ibm_runtime import Sampler
import openshots as osr

qiskit_sampler = Sampler(backend)
sampler = osr.SamplerCache(qiskit_sampler)

# Transparently uses cache when available
job = sampler.run(circuit, shots=1024)
result = job.result()
```

### Filter expressions

```python
from openshots.filters import backend, n_qubits, circuit

# Combine filters
osr.results().filter(backend == "ibm_aachen" & n_qubits == 5)
```

## Development

```bash
# Install dependencies
uv sync --all-extras

# Install the Git hooks (Pyright before commits, pytest before pushes)
uv run pre-commit install --hook-type pre-commit --hook-type pre-push

# Run the checks manually
uv run pyright

# Run tests
uv run pytest -v

# Start the server (from ../server)
cd ../server && cargo run
```

## Configuration

Set the `OSR_SERVER_URL` environment variable to point to your server:

```bash
export OSR_SERVER_URL=http://localhost:8000
```

## Overview

As quantum hardware proliferates, along with pre-processing steps such as parameter optimization and transpilation, and post-processing techniques like quantum error mitigation (QEM), the demand for open access to shots, individual circuit executions on real quantum devices, has become increasingly critical.

The Open Shots Repository aims to address this need by providing a **dynamic, shared database of quantum shots**, deployable either in the cloud or locally, and easily integrable into existing codebases. This resource would offer users, researchers, and learners:
- Faster development through execution fast-forwarding
- Lower costs via global caching that reduces redundant executions, ideal for teams with limited budgets or educational use
- Greater transparency by enabling reproducibility of research and simplifying hardware benchmarking across vendors, empowering projects like Metriq or Mitiq
