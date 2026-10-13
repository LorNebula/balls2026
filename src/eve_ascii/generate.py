"""Procedural galaxy builder."""

from __future__ import annotations

import json
import math
import random
from pathlib import Path

from eve_ascii.models import BlackHole, Galaxy, Moon, Nebula, Planet, StarSystem, Station, SystemAsteroid, Vec3
from eve_ascii.names import planet_name, station_name, system_name, water_name

def build_galaxy(seed: int, num_systems: int = 32) -> Galaxy:
    if num_systems < 1:
        raise ValueError("A galaxy must contain at least one star system.")
    rng = random.Random(seed)
    systems: list[StarSystem] = []
    used_names: set[str] = set()

    for i in range(num_systems):
        base_name = system_name(rng)
        name = base_name
        suffix = 2
        while name in used_names:
            name = f"{base_name}-{suffix}"
            suffix += 1
        used_names.add(name)
        sid = f"sys_{i:03d}"
        radius = 2.5 + i * 0.62
        angle = i * 0.58
        pos = Vec3(
            radius * math.cos(angle) + rng.uniform(-0.15, 0.15),
            radius * math.sin(angle) + rng.uniform(-0.15, 0.15),
            rng.uniform(-0.5, 0.5),
        )
        num_planets = rng.randint(1, 3) if i == 1 else rng.randint(0, 3)
        planets: list[Planet] = []
        for p in range(num_planets):
            pid = f"{sid}_p{p}"
            moon = None
            if rng.random() < 0.5:
                moon = Moon(
                    id=f"{pid}_m0",
                    name=f"{water_name(rng)}-{p + 1}",
                    size=rng.choice(("tiny", "small")),
                )
            planets.append(
                Planet(
                    id=pid,
                    name=planet_name(rng, name),
                    orbit_radius=80.0 + p * 120.0 + rng.uniform(-10, 10),
                    angle=rng.uniform(0, 2 * math.pi),
                    size=rng.choice(("small", "medium", "large")),
                    planet_type=rng.choice(("gas", "terra", "oceanic", "volcanic")),
                    moon=moon,
                )
            )
        stations: list[Station] = []
        has_station = bool(planets) and rng.random() < 0.75
        if has_station and planets:
            planet = rng.choice(planets)
            inventory = {
                "ore": rng.randint(8, 30),
                "scrap": rng.randint(4, 20),
                "ice": rng.randint(4, 16),
                "reactor_upgrade": 1,
                "weapons_upgrade": 1,
            }
            base_prices = {
                "ore": 80.0,
                "scrap": 45.0,
                "ice": 60.0,
                "reactor_upgrade": 2500.0,
                "weapons_upgrade": 2500.0,
            }
            stations.append(
                Station(
                    id=f"{sid}_st0",
                    name=station_name(rng, 1),
                    planet_id=planet.id,
                    offset=Vec3(rng.uniform(30, 80), rng.uniform(-20, 20), 0.0),
                    inventory=inventory,
                    prices={
                        item_id: round(price * rng.uniform(0.9, 1.1), 0)
                        for item_id, price in base_prices.items()
                    },
                )
            )
        asteroids = []
        if not stations and i != 0 and rng.random() < 0.55:
            for asteroid_index in range(rng.randint(1, 3)):
                asteroids.append(
                    SystemAsteroid(
                        id=f"{sid}_a{asteroid_index}",
                        name=f"{water_name(rng)} Rock",
                        position=Vec3(
                            rng.uniform(180.0, 520.0),
                            rng.uniform(-180.0, 180.0),
                            0.0,
                        ),
                        loot_quantity=rng.randint(2, 6),
                    )
                )
        systems.append(
            StarSystem(
                id=sid,
                name=name,
                position=pos,
                planets=planets,
                stations=stations,
                asteroids=asteroids,
            )
        )

    # A spiral chain guarantees reachability; skip-links create alternate routes.
    for i in range(1, len(systems)):
        systems[i - 1].neighbors.append(systems[i].id)
        systems[i].neighbors.append(systems[i - 1].id)
    for i in range(2, len(systems)):
        if rng.random() < 0.24:
            systems[i - 2].neighbors.append(systems[i].id)
            systems[i].neighbors.append(systems[i - 2].id)

    nebulae: list[Nebula] = []
    for nebula_index in range(max(1, num_systems // 10)):
        center = rng.choice(systems)
        affected = sorted(
            systems,
            key=lambda system: system.position.distance_to(center.position),
        )[: rng.randint(1, min(5, num_systems))]
        nebulae.append(
            Nebula(
                id=f"neb_{nebula_index:02d}",
                name=water_name(rng),
                position=Vec3(center.position.x, center.position.y, center.position.z),
                system_ids=[system.id for system in affected],
            )
        )
    return Galaxy(
        seed=seed,
        systems={system.id: system for system in systems},
        black_hole=BlackHole(water_name(rng)),
        nebulae=nebulae,
    )


def galaxy_to_dict(galaxy: Galaxy) -> dict:
    systems = []
    for s in galaxy.systems.values():
        systems.append(
            {
                "id": s.id,
                "name": s.name,
                "position": {"x": s.position.x, "y": s.position.y, "z": s.position.z},
                "neighbors": s.neighbors,
                "planets": [
                    {
                        "id": p.id,
                        "name": p.name,
                        "orbit_radius": p.orbit_radius,
                        "angle": p.angle,
                        "size": p.size,
                        "type": p.planet_type,
                        "moon": (
                            {"id": p.moon.id, "name": p.moon.name, "size": p.moon.size}
                            if p.moon
                            else None
                        ),
                    }
                    for p in s.planets
                ],
                "stations": [
                    {
                        "id": st.id,
                        "name": st.name,
                        "planet_id": st.planet_id,
                        "offset": {
                            "x": st.offset.x,
                            "y": st.offset.y,
                            "z": st.offset.z,
                        },
                        "inventory": st.inventory,
                        "prices": st.prices,
                    }
                    for st in s.stations
                ],
                "asteroids": [
                    {
                        "id": asteroid.id,
                        "name": asteroid.name,
                        "position": {
                            "x": asteroid.position.x,
                            "y": asteroid.position.y,
                            "z": asteroid.position.z,
                        },
                        "loot_item_id": asteroid.loot_item_id,
                        "loot_name": asteroid.loot_name,
                        "loot_quantity": asteroid.loot_quantity,
                    }
                    for asteroid in s.asteroids
                ],
            }
        )
    return {
        "seed": galaxy.seed,
        "systems": systems,
        "black_hole": (
            {
                "name": galaxy.black_hole.name,
                "position": {
                    "x": galaxy.black_hole.position.x,
                    "y": galaxy.black_hole.position.y,
                    "z": galaxy.black_hole.position.z,
                },
            }
            if galaxy.black_hole
            else None
        ),
        "nebulae": [
            {
                "id": nebula.id,
                "name": nebula.name,
                "position": {
                    "x": nebula.position.x,
                    "y": nebula.position.y,
                    "z": nebula.position.z,
                },
                "system_ids": nebula.system_ids,
            }
            for nebula in galaxy.nebulae
        ],
    }


def dict_to_galaxy(data: dict) -> Galaxy:
    systems: dict[str, StarSystem] = {}
    for raw in data["systems"]:
        planets = [
            Planet(
                id=p["id"],
                name=p["name"],
                orbit_radius=p["orbit_radius"],
                angle=p.get("angle", 0.0),
                size=p.get("size", "medium"),
                planet_type=p.get("type", "terra"),
                moon=(
                    Moon(
                        id=p["moon"]["id"],
                        name=p["moon"]["name"],
                        size=p["moon"].get("size", "small"),
                    )
                    if p.get("moon")
                    else None
                ),
            )
            for p in raw["planets"]
        ]
        stations = [
            Station(
                id=st["id"],
                name=st["name"],
                planet_id=st.get("planet_id"),
                offset=Vec3(
                    st["offset"]["x"],
                    st["offset"]["y"],
                    st["offset"].get("z", 0.0),
                ),
                inventory=dict(st.get("inventory", {})),
                prices=dict(st.get("prices", {})),
            )
            for st in raw["stations"]
        ]
        asteroids = [
            SystemAsteroid(
                id=asteroid["id"],
                name=asteroid["name"],
                position=Vec3(
                    asteroid["position"]["x"],
                    asteroid["position"]["y"],
                    asteroid["position"].get("z", 0.0),
                ),
                loot_item_id=asteroid.get("loot_item_id", "ore"),
                loot_name=asteroid.get("loot_name", "Ore"),
                loot_quantity=asteroid.get("loot_quantity", 1),
            )
            for asteroid in raw.get("asteroids", [])
        ]
        systems[raw["id"]] = StarSystem(
            id=raw["id"],
            name=raw["name"],
            position=Vec3(
                raw["position"]["x"],
                raw["position"]["y"],
                raw["position"]["z"],
            ),
            neighbors=list(raw.get("neighbors", [])),
            planets=planets,
            stations=stations,
            asteroids=asteroids,
        )
    raw_black_hole = data.get("black_hole")
    black_hole = None
    if raw_black_hole:
        position = raw_black_hole.get("position", {})
        black_hole = BlackHole(
            name=raw_black_hole["name"],
            position=Vec3(
                position.get("x", 0.0),
                position.get("y", 0.0),
                position.get("z", 0.0),
            ),
        )
    nebulae = [
        Nebula(
            id=nebula["id"],
            name=nebula["name"],
            position=Vec3(
                nebula["position"]["x"],
                nebula["position"]["y"],
                nebula["position"].get("z", 0.0),
            ),
            system_ids=list(nebula.get("system_ids", [])),
        )
        for nebula in data.get("nebulae", [])
    ]
    return Galaxy(
        seed=data.get("seed", 0),
        systems=systems,
        black_hole=black_hole,
        nebulae=nebulae,
    )


def write_galaxy_json(galaxy: Galaxy, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(galaxy_to_dict(galaxy), indent=2, ensure_ascii=False), encoding="utf-8")
