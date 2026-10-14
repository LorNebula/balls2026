"""Load and query galaxy data."""

from __future__ import annotations

from pathlib import Path

from lsl_online.generate import dict_to_galaxy
from lsl_online.models import Galaxy, Planet, StarSystem, Station, Vec3


def default_galaxy_path() -> Path:
    return Path(__file__).resolve().parents[2] / "data" / "galaxy.json"


def load_galaxy(path: Path | None = None) -> Galaxy:
    p = path or default_galaxy_path()
    import json

    data = json.loads(p.read_text(encoding="utf-8"))
    return dict_to_galaxy(data)


def find_system_by_name(galaxy: Galaxy, name: str) -> StarSystem | None:
    name_lower = name.lower()
    for s in galaxy.systems.values():
        if s.name.lower() == name_lower or s.id.lower() == name_lower:
            return s
    for s in galaxy.systems.values():
        if name_lower in s.name.lower():
            return s
    return None


def find_planet(system: StarSystem, name: str) -> Planet | None:
    name_lower = name.lower()
    for p in system.planets:
        if p.name.lower() == name_lower or p.id.lower() == name_lower:
            return p
    for p in system.planets:
        if name_lower in p.name.lower():
            return p
    return None


def find_station(system: StarSystem, name: str) -> Station | None:
    name_lower = name.lower()
    for st in system.stations:
        if st.name.lower() == name_lower or st.id.lower() == name_lower:
            return st
    for st in system.stations:
        if name_lower in st.name.lower():
            return st
    return None


def station_position(system: StarSystem, station: Station) -> Vec3:
    planets = {p.id: p for p in system.planets}
    return station.position(planets)


def planet_position(planet: Planet) -> Vec3:
    return planet.position()


def galaxy_core(galaxy: Galaxy) -> Vec3:
    if galaxy.black_hole:
        return galaxy.black_hole.position
    return Vec3(0.0, 0.0, 0.0)


def system_rim_tier(galaxy: Galaxy, system_id: str) -> float:
    """0 = core-adjacent, 1 = outer rim (normalized by farthest system)."""
    system = galaxy.get_system(system_id)
    if not system or not galaxy.systems:
        return 0.0
    center = galaxy_core(galaxy)
    dist = system.position.distance_to(center)
    max_dist = max(
        (s.position.distance_to(center) for s in galaxy.systems.values()),
        default=1.0,
    )
    if max_dist <= 0:
        return 0.0
    return max(0.0, min(1.0, dist / max_dist))
