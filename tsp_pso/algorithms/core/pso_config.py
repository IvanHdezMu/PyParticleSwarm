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
