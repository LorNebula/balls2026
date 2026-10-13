"""Procedural galaxy builder."""

from __future__ import annotations

import json
import math
import random
from pathlib import Path

from eve_ascii.models import BlackHole, Galaxy, Moon, Nebula, Planet, StarSystem, Station, SystemAsteroid, Vec3
from eve_ascii.names import planet_name, station_name, system_name, water_name
from eve_ascii.shipyard import SHIP_TYPES


def _system_layout(
    rng: random.Random,
    count: int,
) -> tuple[list[Vec3], list[list[int]], list[list[int]]]:
    positions: list[Vec3 | None] = [None] * count
    if count < 24:
        radius = 2.5 + count * 0.12
        ring = list(range(count))
        for index in ring:
            angle = 2 * math.pi * index / max(1, count)
            positions[index] = Vec3(
                radius * math.cos(angle),
                radius * math.sin(angle),
                rng.uniform(-0.3, 0.3),
            )
        return [position for position in positions if position is not None], [ring], []

    arm_count = rng.randint(4, 6)
    layer_count = rng.randint(2, 3)
    ring_count = min(count - arm_count * 2, max(arm_count * 2, round(count * 0.4)))
    layer_sizes = [ring_count // layer_count] * layer_count
    for index in range(ring_count % layer_count):
        layer_sizes[index] += 1

    ring_layers: list[list[int]] = []
    cursor = 0
    outer_radius = 0.0
    for layer, size in enumerate(layer_sizes):
        outer_radius = 3.0 + layer * 0.9
        indices = list(range(cursor, cursor + size))
        ring_layers.append(indices)
        phase = layer * math.pi / size
        for sector, index in enumerate(indices):
            angle = phase + 2 * math.pi * sector / size
            positions[index] = Vec3(
                outer_radius * math.cos(angle) + rng.uniform(-0.08, 0.08),
                outer_radius * math.sin(angle) + rng.uniform(-0.08, 0.08),
                rng.uniform(-0.3, 0.3),
            )
        cursor += size

    arm_sizes = [(count - ring_count) // arm_count] * arm_count
    for index in range((count - ring_count) % arm_count):
        arm_sizes[index] += 1

    arms: list[list[int]] = []
    for arm_index, arm_size in enumerate(arm_sizes):
        indices = list(range(cursor, cursor + arm_size))
        arms.append(indices)
        phase = 2 * math.pi * arm_index / arm_count + rng.uniform(-0.025, 0.025)
        for step, index in enumerate(indices):
            radius = outer_radius + 0.8 + step * 0.72
            angle = phase + step * 0.15
            positions[index] = Vec3(
                radius * math.cos(angle) + rng.uniform(-0.08, 0.08),
                radius * math.sin(angle) + rng.uniform(-0.08, 0.08),
                rng.uniform(-0.3, 0.3),
            )
        cursor += arm_size

    return [position for position in positions if position is not None], ring_layers, arms


def _connect_layout(
    systems: list[StarSystem],
    ring_layers: list[list[int]],
    arms: list[list[int]],
) -> None:
    def link(first: StarSystem, second: StarSystem) -> None:
        if second.id not in first.neighbors:
            first.neighbors.append(second.id)
        if first.id not in second.neighbors:
            second.neighbors.append(first.id)

    for layer in ring_layers:
        if len(layer) > 1:
            for index, system_index in enumerate(layer):
                link(systems[system_index], systems[layer[(index + 1) % len(layer)]])

    for inner, outer in zip(ring_layers, ring_layers[1:]):
        for outer_index in outer:
            outer_system = systems[outer_index]
            angle = math.atan2(outer_system.position.y, outer_system.position.x)
            nearest_inner = min(
                inner,
                key=lambda inner_index: abs(
                    (math.atan2(systems[inner_index].position.y, systems[inner_index].position.x)
                     - angle + math.pi) % (2 * math.pi) - math.pi
                ),
            )
            link(systems[outer_index], systems[nearest_inner])

    outer_ring = ring_layers[-1] if ring_layers else []

    def nearest_ring(angle: float, excluded: set[int] | None = None) -> int:
        candidates = [index for index in outer_ring if not excluded or index not in excluded]
        if not candidates:
            candidates = outer_ring
        return min(
            candidates,
            key=lambda index: abs(
                (math.atan2(systems[index].position.y, systems[index].position.x)
                 - angle + math.pi) % (2 * math.pi) - math.pi
            ),
        )

    for arm in arms:
        if not arm:
            continue
        first = systems[arm[0]]
        if outer_ring:
            arm_angle = math.atan2(first.position.y, first.position.x)
            root = nearest_ring(arm_angle)
            link(systems[root], first)
        for previous_index, next_index in zip(arm, arm[1:]):
            link(systems[previous_index], systems[next_index])
        if outer_ring:
            tip = systems[arm[-1]]
            tip_angle = math.atan2(tip.position.y, tip.position.x)
            tip_gate = nearest_ring(tip_angle, {root})
            link(tip, systems[tip_gate])


def build_galaxy(seed: int, num_systems: int = 72) -> Galaxy:
    if num_systems < 1:
        raise ValueError("A galaxy must contain at least one star system.")
    from eve_ascii.market import BASE_PRICES, ITEM_NAMES

    rng = random.Random(seed)
    layout_rng = random.Random(seed + 1)
    positions, ring_layers, arms = _system_layout(layout_rng, num_systems)
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
        pos = positions[i]
        rng.uniform(-0.15, 0.15)
        rng.uniform(-0.15, 0.15)
        rng.uniform(-0.5, 0.5)
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
            trade_items = sorted(
                item_id
                for item_id in ITEM_NAMES
                if not item_id.endswith("_upgrade")
            )
            stock_count = min(len(trade_items), rng.randint(4, 8))
            stocked_items = rng.sample(trade_items, stock_count)
            inventory = {
                item_id: rng.randint(2, 12)
                for item_id in stocked_items
            }
            abundant_item = rng.choice(stocked_items)
            inventory[abundant_item] = rng.randint(45, 100)
            inventory.update({
                "reactor_upgrade": 1,
                "weapons_upgrade": 1,
            })
            available_hulls = [ship_type.id for ship_type in SHIP_TYPES if ship_type.id != "venture"]
            rng.shuffle(available_hulls)
            hangar_inventory = {
                hull_id: 1
                for hull_id in available_hulls[:rng.randint(1, min(3, len(available_hulls)))]
            }
            stations.append(
                Station(
                    id=f"{sid}_st0",
                    name=station_name(rng, 1),
                    planet_id=planet.id,
                    offset=Vec3(rng.uniform(30, 80), rng.uniform(-20, 20), 0.0),
                    inventory=inventory,
                    hangar_inventory=hangar_inventory,
                    prices={
                        item_id: round(price * rng.uniform(0.9, 1.1), 0)
                        for item_id, price in BASE_PRICES.items()
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

    _connect_layout(systems, ring_layers, arms)
    for _ in range(max(0, num_systems - 3)):
        rng.random()

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
                        "hangar_inventory": st.hangar_inventory,
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
                hangar_inventory=dict(st.get("hangar_inventory", {})),
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
