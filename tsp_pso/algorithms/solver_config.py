"""Immutable solver settings; validation remains in the solvers in its original order."""

from dataclasses import dataclass


@dataclass(frozen=True)
class PSOConfig:
    """Requested PSO settings; solvers retain the original numeric conversions."""

    N: int | float
    c1: int | float
    ring_mode: bool = False
    reset_threshold_divisor: int | float = 1000
    primary_operator_share: float = 0.2
    progress_warmup_multiplier: int | float = 5


@dataclass(frozen=True)
class RefuelConfig:
    """Refueling settings: capacity in liters and consumption in km/liter.

    None preserves the previous defaults; TSPWR rejects missing capacity or
    consumption during initialization. Dataset prices are supplied separately.
    """

    max_capacity: int | float | None = None
    consumption: int | float | None = None
    full_init: bool = False
