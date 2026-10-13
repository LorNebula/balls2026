"""Asteroid fields, lock/mine, cargo."""

from __future__ import annotations

import random
import re

from eve_ascii.materials import Material
from eve_ascii.models import Asteroid, CargoStack, GameMode, GameState, ShipStatus, TutorialStep, Vec3
from eve_ascii.space_render import tutorial_arena

ASTEROID_CAP = 9
RESPAWN_INTERVAL = 8.0
MINE_INTERVAL = 1.0
PICKUP_SOUND_COOLDOWN = 0.3
WORLD_SPAN = 600.0
_pickup_sound_timer = 0.0
CODE_PATTERN = re.compile(r"^R\d+$", re.IGNORECASE)


def _system_rng(state: GameState, system_id: str) -> random.Random:
    seed = (hash((state.galaxy.seed, system_id)) & 0xFFFFFFFF) ^ 0xA57E
    return random.Random(seed)


def system_materials(state: GameState, system_id: str) -> list[Material]:
    from eve_ascii.materials import MATERIALS

    rng = _system_rng(state, system_id)
    count = rng.randint(2, 4)
    weights = [max(1, 6 - m.rarity) for m in MATERIALS]
    picked: list[Material] = []
    pool = list(MATERIALS)
    for _ in range(count):
        if not pool:
            break
        m = rng.choices(pool, weights=[weights[MATERIALS.index(x)] for x in pool], k=1)[0]
        picked.append(m)
        pool = [x for x in pool if x.id != m.id]
    return picked or [MATERIALS[0]]


def _next_code(state: GameState) -> str | None:
    used = {a.code.upper() for a in state.asteroids if a.alive}
    for i in range(1, ASTEROID_CAP + 1):
        code = f"R{i}"
        if code not in used:
            return code
    return None


def _spawn_group(
    state: GameState,
    system_id: str,
    materials: list[Material],
    rng: random.Random,
    *,
    count: int | None = None,
) -> int:
    spawned = 0
    group_count = count if count is not None else rng.randint(1, 4)
    cx = rng.uniform(-WORLD_SPAN, WORLD_SPAN)
    cy = rng.uniform(-WORLD_SPAN, WORLD_SPAN)
    for _ in range(group_count):
        if _alive_count(state) >= ASTEROID_CAP:
            break
        code = _next_code(state)
        if not code:
            break
        mat = rng.choice(materials)
        max_yield = rng.randint(3, 12) + rng.randint(0, 23)
        state.asteroids.append(
            Asteroid(
                code=code,
                material_id=mat.id,
                material_name=mat.name,
                position=Vec3(
                    cx + rng.uniform(-80, 80),
                    cy + rng.uniform(-80, 80),
                    0.0,
                ),
                yield_left=max_yield,
                max_yield=max_yield,
            )
        )
        spawned += 1
    return spawned


def _alive_count(state: GameState) -> int:
    return sum(1 for a in state.asteroids if a.alive)


def fill_tutorial_mining_field(state: GameState) -> None:
    """Spawn a small cluster near the ship for the post-jump mining beat."""
    from eve_ascii.travel import current_ship_coords

    system_id = state.player.ship.location.system_id
    materials = system_materials(state, system_id)
    mat = materials[0] if materials else None
    if not mat:
        from eve_ascii.materials import MATERIALS

        mat = MATERIALS[0]
    sc = current_ship_coords(state)
    state.asteroids.clear()
    offsets = ((110.0, 35.0), (130.0, -25.0), (95.0, 5.0))
    for i, (dx, dy) in enumerate(offsets, start=1):
        state.asteroids.append(
            Asteroid(
                code=f"R{i}",
                material_id=mat.id,
                material_name=mat.name,
                position=Vec3(sc.x + dx, sc.y + dy, 0.0),
                yield_left=12,
                max_yield=12,
            )
        )


def fill_asteroid_field(state: GameState) -> None:
    if state.tutorial_step != TutorialStep.DONE:
        return
    system_id = state.player.ship.location.system_id
    state.asteroids.clear()
    materials = system_materials(state, system_id)
    rng = _system_rng(state, system_id + ":fill")
    while _alive_count(state) < ASTEROID_CAP:
        before = _alive_count(state)
        _spawn_group(state, system_id, materials, rng)
        if _alive_count(state) == before:
            break


def asteroid_by_code(state: GameState, code: str) -> Asteroid | None:
    key = code.upper()
    return next((a for a in state.asteroids if a.alive and a.code.upper() == key), None)


def lock_asteroid(state: GameState, code: str) -> str | None:
    if tutorial_arena(state):
        return "No asteroids on scope."
    ast = asteroid_by_code(state, code)
    if not ast:
        return f"No asteroid {code.upper()} on scope."
    ship = state.player.ship
    ship.target_letter = ast.code.upper()
    ship.subtarget = None
    state.log(f"Locked {ast.code} ({ast.material_name}, yld {ast.yield_left})")
    return None


def lock_target_unified(state: GameState, ref: str, subtarget: str | None = None) -> str | None:
    from eve_ascii import combat

    ref_u = ref.upper()
    if CODE_PATTERN.match(ref_u):
        if subtarget:
            return "Asteroids have no subtarget."
        return lock_asteroid(state, ref_u)
    return combat.lock_target(state, ref_u, subtarget)


def start_mining(state: GameState) -> str | None:
    if tutorial_arena(state):
        return "Cannot mine here."
    ship = state.player.ship
    if ship.status in (ShipStatus.DOCKED, ShipStatus.JUMPING, ShipStatus.WARPING):
        return "Cannot mine while docked or in transit."
    if state.mode == GameMode.HYPERSPACE:
        return "Cannot mine in hyperspace."
    if not ship.target_letter or not CODE_PATTERN.match(ship.target_letter):
        return "Lock an asteroid first (lock R1)."
    ast = asteroid_by_code(state, ship.target_letter)
    if not ast:
        return "Locked asteroid is gone."
    state.mining_active = True
    state.log(f"Mining laser on {ast.code} ({ast.material_id}).")
    return None


def cease_mining(state: GameState) -> None:
    if state.mining_active:
        state.mining_active = False
        state.log("Cease mining.")
        from eve_ascii.audio import stop_all_loops

        stop_all_loops()


def cargo_total(player) -> int:
    return sum(c.quantity for c in player.cargo)


def add_cargo(state: GameState, item_id: str, name: str, qty: int) -> int:
    """Add qty to hold; returns amount actually added."""
    if qty <= 0:
        return 0
    player = state.player
    room = player.max_cargo - cargo_total(player)
    if room <= 0:
        return 0
    add = min(qty, room)
    for stack in player.cargo:
        if stack.item_id == item_id:
            stack.quantity += add
            return add
    player.cargo.append(CargoStack(item_id, name, add))
    return add


def _tick_mining(state: GameState, dt: float) -> None:
    global _pickup_sound_timer
    ship = state.player.ship
    if ship.mine_cooldown > 0:
        ship.mine_cooldown = max(0.0, ship.mine_cooldown - dt)
    if _pickup_sound_timer > 0:
        _pickup_sound_timer = max(0.0, _pickup_sound_timer - dt)
    if not state.mining_active:
        return
    if not ship.target_letter:
        state.mining_active = False
        return
    ast = asteroid_by_code(state, ship.target_letter)
    if not ast:
        state.mining_active = False
        state.log("Mining target lost.")
        return
    if ship.mine_cooldown > 0:
        return
    added = add_cargo(state, ast.material_id, ast.material_name, 1)
    if added <= 0:
        state.mining_active = False
        state.log("Cargo hold full.")
        return
    ast.yield_left -= 1
    ship.mine_cooldown = MINE_INTERVAL
    if state.tutorial_step == TutorialStep.MINE:
        state.tutorial_mined_units += added
    state.log(f"Mined 1x {ast.material_id} -> hold ({ast.yield_left} left on {ast.code})")
    if added > 0 and _pickup_sound_timer <= 0:
        from eve_ascii.audio import request_sound

        request_sound(state, "pickup")
        _pickup_sound_timer = PICKUP_SOUND_COOLDOWN
    if ast.yield_left <= 0:
        ast.alive = False
        state.mining_active = False
        if ship.target_letter == ast.code.upper():
            ship.target_letter = None
        state.log(f"{ast.code} depleted.")


def tick(state: GameState, dt: float) -> None:
    if tutorial_arena(state):
        return
    _tick_mining(state, dt)
    if state.tutorial_step not in (TutorialStep.DONE, TutorialStep.MINE):
        return
    if state.tutorial_step == TutorialStep.MINE:
        return
    if _alive_count(state) >= ASTEROID_CAP:
        state.asteroid_respawn_timer = 0.0
        return
    state.asteroid_respawn_timer += dt
    if state.asteroid_respawn_timer < RESPAWN_INTERVAL:
        return
    state.asteroid_respawn_timer = 0.0
    system_id = state.player.ship.location.system_id
    materials = system_materials(state, system_id)
    rng = random.Random(int(state.star_scroll * 1000) + _alive_count(state))
    _spawn_group(state, system_id, materials, rng, count=rng.randint(1, 3))
