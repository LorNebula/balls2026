from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Literal


class ShipStatus(str, Enum):
    IDLE = "idle"
    WARPING = "warping"
    JUMPING = "jumping"
    DOCKED = "docked"
    ORBITING = "orbiting"


@dataclass
class Vec3:
    x: float
    y: float
    z: float

    def distance_to(self, other: Vec3) -> float:
        return (
            (self.x - other.x) ** 2 + (self.y - other.y) ** 2 + (self.z - other.z) ** 2
        ) ** 0.5


@dataclass
class Planet:
    id: str
    name: str
    orbit_radius: float
    angle: float = 0.0

    def position(self) -> Vec3:
        import math

        return Vec3(
            self.orbit_radius * math.cos(self.angle),
            self.orbit_radius * math.sin(self.angle),
            0.0,
        )


@dataclass
class Station:
    id: str
    name: str
    planet_id: str | None
    offset: Vec3 = field(default_factory=lambda: Vec3(50.0, 0.0, 0.0))

    def position(self, planets: dict[str, Planet]) -> Vec3:
        if self.planet_id and self.planet_id in planets:
            base = planets[self.planet_id].position()
            return Vec3(base.x + self.offset.x, base.y + self.offset.y, base.z + self.offset.z)
        return Vec3(self.offset.x, self.offset.y, self.offset.z)


@dataclass
class StarSystem:
    id: str
    name: str
    position: Vec3
    neighbors: list[str] = field(default_factory=list)
    planets: list[Planet] = field(default_factory=list)
    stations: list[Station] = field(default_factory=list)


@dataclass
class Galaxy:
    seed: int
    systems: dict[str, StarSystem]

    def get_system(self, system_id: str) -> StarSystem | None:
        return self.systems.get(system_id)


PlaceKind = Literal["space", "orbit", "docked"]


@dataclass
class ShipLocation:
    system_id: str
    kind: PlaceKind
    coords: Vec3
    planet_id: str | None = None
    station_id: str | None = None


@dataclass
class TravelTarget:
    kind: Literal["coords", "planet", "station", "system"]
    system_id: str
    coords: Vec3 | None = None
    planet_id: str | None = None
    station_id: str | None = None
    label: str = ""


@dataclass
class Ship:
    name: str
    location: ShipLocation
    status: ShipStatus = ShipStatus.IDLE
    destination: TravelTarget | None = None
    eta_seconds: float = 0.0
    warp_speed: float = 100.0
    jump_speed: float = 1.0


@dataclass
class Player:
    ship: Ship
    system_id: str

    @property
    def location(self) -> ShipLocation:
        return self.ship.location


@dataclass
class GameState:
    galaxy: Galaxy
    player: Player
    events: list[str] = field(default_factory=list)

    def log(self, message: str) -> None:
        from eve_ascii.ascii_ui import ascii_only

        self.events.append(ascii_only(message))
        if len(self.events) > 200:
            self.events = self.events[-200:]
