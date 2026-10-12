from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Literal

COMPONENT_NAMES = ("reactor", "shield", "hyperdrive", "cargo")
COMPONENT_IDS = {"01": "reactor", "02": "shield", "03": "hyperdrive", "04": "cargo"}


class ShipStatus(str, Enum):
    IDLE = "idle"
    WARPING = "warping"
    JUMPING = "jumping"
    DOCKED = "docked"
    ORBITING = "orbiting"


class GameMode(str, Enum):
    HYPERSPACE = "hyperspace"
    SPACE = "space"
    COMBAT = "combat"


class TutorialStep(str, Enum):
    HYPERSPACE = "hyperspace"
    WARNING = "warning"
    INTERDICT = "interdict"
    COMBAT = "combat"
    JUMP_STATION = "jump_station"
    GALAXY = "galaxy"
    QUESTS = "quests"
    DONE = "done"


class QuestStatus(str, Enum):
    AVAILABLE = "available"
    ACTIVE = "active"
    DONE = "done"


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


def default_components() -> dict[str, float]:
    return {"reactor": 100.0, "shield": 100.0, "hyperdrive": 100.0, "cargo": 100.0}


@dataclass
class Ship:
    name: str
    location: ShipLocation
    status: ShipStatus = ShipStatus.IDLE
    destination: TravelTarget | None = None
    eta_seconds: float = 0.0
    warp_speed: float = 100.0
    jump_speed: float = 1.0
    fuel: float = 100.0
    max_fuel: float = 100.0
    fuel_per_jump: float = 15.0
    components: dict[str, float] = field(default_factory=default_components)
    target_letter: str | None = None
    subtarget: str | None = None
    weapons_active: bool = False
    fire_cooldown: float = 0.0


@dataclass
class NpcShip:
    letter: str
    name: str
    position: Vec3
    hostile: bool = True
    components: dict[str, float] = field(default_factory=default_components)
    alive: bool = True


@dataclass
class Projectile:
    x: float
    y: float
    vx: float
    vy: float
    target_letter: str
    ttl: float = 2.0
    friendly: bool = True


@dataclass
class Explosion:
    x: float
    y: float
    ttl: float = 0.4


@dataclass
class HyperspaceParticle:
    x: float
    y: float
    char: str
    speed: float


@dataclass
class Message:
    sender: str
    body: str
    tick: float = 0.0


@dataclass
class Quest:
    id: str
    title: str
    summary: str
    status: QuestStatus = QuestStatus.AVAILABLE


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
    mode: GameMode = GameMode.SPACE
    tutorial_step: TutorialStep = TutorialStep.DONE
    tutorial_timer: float = 0.0
    npc_ships: list[NpcShip] = field(default_factory=list)
    projectiles: list[Projectile] = field(default_factory=list)
    explosions: list[Explosion] = field(default_factory=list)
    hyperspace_particles: list[HyperspaceParticle] = field(default_factory=list)
    inbox: list[Message] = field(default_factory=list)
    quests: list[Quest] = field(default_factory=list)
    quests_unlocked: bool = False
    combat_time: float = 0.0
    tutorial_force_galaxy: bool = False
    tutorial_step_elapsed: float = 0.0
    tutorial_post_combat: bool = False

    def log(self, message: str) -> None:
        from eve_ascii.ascii_ui import ascii_only

        self.events.append(ascii_only(message))
        if len(self.events) > 200:
            self.events = self.events[-200:]
