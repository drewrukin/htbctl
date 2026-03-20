"""HTBctl data models."""

from dataclasses import dataclass


@dataclass
class SpawnedMachine:
    """A spawned HTB machine."""
    name: str
    machine_id: int
    ip: str          # guaranteed valid IPv4 after spawn()
    os: str
    difficulty: str
