"""Open Shots Repository - Open data for Quantum Computing.

A shared dynamic database of quantum computing circuit shots on real hardware.
"""

from openshots.client import OSRClient
from openshots.query import ResultsQuery, results, results_int
from openshots.cache import SamplerCache
from openshots.models import Shot, ShotMetadata

__all__ = [
    "OSRClient",
    "ResultsQuery",
    "results",
    "results_int",
    "SamplerCache",
    "Shot",
    "ShotMetadata",
]

__version__ = "0.1.0"
