"""Procedural galaxy builder."""

from __future__ import annotations

import json
import math
import random
from pathlib import Path

from eve_ascii.models import Galaxy, Planet, StarSystem, Station, Vec3
from eve_ascii.names import planet_name, station_name, system_name


def _connect_systems(systems: list[StarSystem], rng: random.Random) -> None:
    n = len(systems)
    if n < 2:
        return
    # Minimum spanning tree via greedy on distance
    in_tree = {systems[0].id}
    while len(in_tree) < n:
        best = None
        best_dist = float("inf")
        for sid in in_tree:
            s = next(x for x in systems if x.id == sid)
            for t in systems:
                if t.id in in_tree:
                    continue
                d = s.position.distance_to(t.position)
                if d < best_dist:
                    best_dist = d
                    best = (sid, t.id)
        if best:
            a, b = best
            sa = next(x for x in systems if x.id == a)
            sb = next(x for x in systems if x.id == b)
            sa.neighbors.append(b)
            sb.neighbors.append(a)
            in_tree.add(b)
    # Extra random links
    for _ in range(max(1, n // 4)):
        a, b = rng.sample(systems, 2)
        if b.id not in a.neighbors:
            a.neighbors.append(b.id)
            b.neighbors.append(a.id)


def build_galaxy(seed: int, num_systems: int = 32) -> Galaxy:
    rng = random.Random(seed)
    systems: list[StarSystem] = []
    used_names: set[str] = set()

    for i in range(num_systems):
        name = system_name(rng)
        while name in used_names:
            name = system_name(rng)
        used_names.add(name)
        sid = f"sys_{i:03d}"
        pos = Vec3(
            rng.uniform(-500, 500),
            rng.uniform(-500, 500),
            rng.uniform(-200, 200),
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
        num_stations = rng.randint(0, 2)
        stations: list[Station] = []
        for s in range(num_stations):
            planet = rng.choice(planets) if planets else None
            stations.append(
                Station(
                    id=f"{sid}_st{s}",
                    name=station_name(rng, s + 1),
                    planet_id=planet.id if planet else None,
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

    _connect_systems(systems, rng)
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
