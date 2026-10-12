from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Literal

COMPONENT_KINDS = ("reactor", "thrusters", "shields", "weapons")
COMPONENT_ALIASES = {
    "reactor": "reactor",
    "thruster": "thrusters",
    "thrusters": "thrusters",
    "shield": "shields",
    "shields": "shields",
    "weapon": "weapons",
    "weapons": "weapons",
}


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
    DOCK = "dock"
    SELL = "sell"
    UPGRADE = "upgrade"
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


@dataclass
class ShipComponent:
    slot_id: str
    kind: str
    max_health: float = 100.0
    health: float = 100.0

    @property
    def destroyed(self) -> bool:
        return self.health <= 0.0

    @property
    def integrity(self) -> float:
        if self.max_health <= 0:
            return 0.0
        return max(0.0, min(1.0, self.health / self.max_health))


def starter_components() -> list[ShipComponent]:
    """Starter hull: one of each main component, slots 01-04."""
    return [
        ShipComponent("01", "reactor"),
        ShipComponent("02", "thrusters"),
        ShipComponent("03", "shields"),
        ShipComponent("04", "weapons"),
    ]


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
    max_slots: int = 4
    components: list[ShipComponent] = field(default_factory=starter_components)
    power: float = 100.0
    max_power: float = 100.0
    shield: float = 100.0
    max_shield: float = 100.0
    target_letter: str | None = None
    subtarget: str | None = None
    weapons_active: bool = False
    fire_cooldown: float = 0.0
    power_starve_logged: bool = False


@dataclass
class NpcShip:
    letter: str
    name: str
    position: Vec3
    hostile: bool = True
    max_slots: int = 4
    components: list[ShipComponent] = field(default_factory=starter_components)
    power: float = 100.0
    max_power: float = 100.0
    shield: float = 40.0
    max_shield: float = 40.0
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
    large: bool = False


@dataclass
class BackgroundStar:
    """Normalized star field for slow parallax drift."""

    x: float
    y: int
    char: str
    parallax: float = 0.5


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
class CargoStack:
    item_id: str
    name: str
    quantity: int


@dataclass
class Player:
    ship: Ship
    system_id: str
    credits: float = 0.0
    cargo: list[CargoStack] = field(default_factory=list)

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
    tutorial_jump_from_system: str | None = None
    screen_flash: float = 0.0
    station_view: str = "hangar"
    tutorial_sell_done: bool = False
    tutorial_upgraded_reactor: bool = False
    tutorial_upgraded_weapons: bool = False
    star_scroll: float = 0.0
    background_stars: list[BackgroundStar] = field(default_factory=list)

    def log(self, message: str) -> None:
        from eve_ascii.ascii_ui import ascii_only

        self.events.append(ascii_only(message))
        if len(self.events) > 200:
            self.events = self.events[-200:]
