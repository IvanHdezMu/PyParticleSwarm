from dataclasses import dataclass


@dataclass(frozen=True)
class RefuelConfig:
    """Refueling settings: capacity in liters and consumption in km/liter.

    None preserves the previous defaults; TSPWR rejects missing capacity or
    consumption during initialization. Dataset prices are supplied separately.
    """

    max_capacity: int | float | None = None
    consumption: int | float | None = None
    full_init: bool = False
