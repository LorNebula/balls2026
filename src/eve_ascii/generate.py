"""Procedural galaxy builder."""

from __future__ import annotations

import json
import math
import random
from pathlib import Path

from eve_ascii.models import Galaxy, Planet, StarSystem, Station, Vec3
from eve_ascii.names import planet_name, station_name, system_name

# Stargate grid spacing: at jump_speed 1.0, linked hops are ~5 seconds.
JUMP_UNIT = 5.0
def _connect_systems(systems: list[StarSystem], cols: int, rng: random.Random) -> None:
    n = len(systems)
    if n < 2:
        return
    by_id = {s.id: s for s in systems}

    def link(a: StarSystem, b: StarSystem) -> None:
        if b.id not in a.neighbors:
            a.neighbors.append(b.id)
            b.neighbors.append(a.id)

    # Grid stargates: east and south links only (~JUMP_UNIT light-seconds per hop).
    for i, s in enumerate(systems):
        row, col = divmod(i, cols)
        if col + 1 < cols and i + 1 < n:
            link(s, systems[i + 1])
        if i + cols < n:
            link(s, systems[i + cols])

    # Extra short links between existing grid neighbors (loops / alternate routes).
    grid_pairs: list[tuple[StarSystem, StarSystem]] = []
    for i, s in enumerate(systems):
        row, col = divmod(i, cols)
        if col + 1 < cols and i + 1 < n:
            grid_pairs.append((s, systems[i + 1]))
        if i + cols < n:
            grid_pairs.append((s, systems[i + cols]))
    rng.shuffle(grid_pairs)
    target_extra = max(1, n // 6)
    for a, b in grid_pairs[:target_extra]:
        link(a, b)


def build_galaxy(seed: int, num_systems: int = 32) -> Galaxy:
    rng = random.Random(seed)
    systems: list[StarSystem] = []
    used_names: set[str] = set()

    cols = max(1, int(math.ceil(math.sqrt(num_systems))))
    for i in range(num_systems):
        name = system_name(rng)
        while name in used_names:
            name = system_name(rng)
        used_names.add(name)
        sid = f"sys_{i:03d}"
        row, col = divmod(i, cols)
        pos = Vec3(
            col * JUMP_UNIT + rng.uniform(-0.25, 0.25),
            row * JUMP_UNIT + rng.uniform(-0.25, 0.25),
            rng.uniform(-0.5, 0.5),
        )
        num_planets = rng.randint(1, 4)
        planets: list[Planet] = []
        for p in range(num_planets):
            pid = f"{sid}_p{p}"
            planets.append(
                Planet(
                    id=pid,
                    name=planet_name(rng, name),
                    orbit_radius=80.0 + p * 120.0 + rng.uniform(-10, 10),
                    angle=rng.uniform(0, 2 * math.pi),
                )
            )
        stations: list[Station] = []
        if rng.random() < 0.75 and planets:
            planet = rng.choice(planets)
            stations.append(
                Station(
                    id=f"{sid}_st0",
                    name=station_name(rng, 1),
                    planet_id=planet.id,
                    offset=Vec3(rng.uniform(30, 80), rng.uniform(-20, 20), 0.0),
                )
            )
        systems.append(
            StarSystem(
                id=sid,
                name=name,
                position=pos,
                planets=planets,
                stations=stations,
            )
        )

    _connect_systems(systems, cols, rng)
    return Galaxy(seed=seed, systems={s.id: s for s in systems})


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
                    }
                    for st in s.stations
                ],
            }
        )
    return {"seed": galaxy.seed, "systems": systems}


def dict_to_galaxy(data: dict) -> Galaxy:
    systems: dict[str, StarSystem] = {}
    for raw in data["systems"]:
        planets = [
            Planet(
                id=p["id"],
                name=p["name"],
                orbit_radius=p["orbit_radius"],
                angle=p.get("angle", 0.0),
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
            )
            for st in raw["stations"]
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
        )
    return Galaxy(seed=data.get("seed", 0), systems=systems)


def write_galaxy_json(galaxy: Galaxy, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(galaxy_to_dict(galaxy), indent=2, ensure_ascii=False), encoding="utf-8")
