"""htbctl — HackTheBox machine lifecycle automation."""

__version__ = "0.1.0"

from .client import HTBIntegration
from .exceptions import (
    HTBAuthError,
    HTBError,
    HTBMachineNotFoundError,
    HTBRateLimitError,
    HTBSpawnError,
)
from .models import SpawnedMachine

__all__ = [
    "HTBIntegration",
    "SpawnedMachine",
    "HTBError",
    "HTBAuthError",
    "HTBMachineNotFoundError",
    "HTBSpawnError",
    "HTBRateLimitError",
]
