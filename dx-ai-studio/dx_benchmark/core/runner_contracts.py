"""Benchmark runner contracts — structural typing for result objects.

Both ModelResult and PipelineResult conform to BenchmarkResultProtocol
without inheriting from it.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class BenchmarkResultProtocol(Protocol):
    """Structural contract shared by all benchmark result dataclasses."""

    status: str

    def as_dict(self) -> dict:
        """Serialize the result to a plain dict."""
        ...
