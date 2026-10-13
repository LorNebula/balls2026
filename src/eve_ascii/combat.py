"""Combat: lock, fire, projectiles, pirates."""

from __future__ import annotations

import math
import random

from eve_ascii.models import (
    Explosion,
    GameMode,
    GameState,
    HyperspaceParticle,
    NpcShip,
    Projectile,
    ShipComponent,
    Vec3,
)
from eve_ascii.ship import (
    find_component,
    is_powerless,
    pirate_components,
    tick_weapon_recharge,
    try_fire_shot,
    weapon_charge_seconds,
    weapons_online,
)

# Local offset from ship center for component explosions (world units)
COMP_BLAST_OFFSET = {
    "reactor": (0.0, -18.0),
    "thrusters": (-14.0, 0.0),
    "shields": (14.0, 0.0),
    "weapons": (0.0, 18.0),
}



def spawn_pirates(state: GameState, count: int = 1) -> None:
    state.npc_ships.clear()
    letters = "ABCDEFGH"
    for i in range(min(count, len(letters))):
        state.npc_ships.append(
            NpcShip(
                letter=letters[i],
                name=f"Pirate-{letters[i]}",
                position=Vec3(200.0 + i * 140, -8.0 + i * 40, 0.0),
                components=pirate_components(),
                shield=55.0,
                max_shield=55.0,
                loot_item_id="pirate_scrap",
                loot_name="Pirate salvage",
                loot_quantity=random.randint(1, 4),
            )
        )
    state.log("HOSTILE CONTACT: pirate on scope. lock / fire")


def enter_system(state: GameState, system) -> None:
    state.npc_ships.clear()
    state.projectiles.clear()
    state.player.ship.weapons_active = False
    state.player.ship.target_letter = None
    state.player.ship.subtarget = None
    state.mode = GameMode.SPACE
    if system.stations:
        return

    letters = "ABCDEFGH"
    for asteroid in system.asteroids:
        if asteroid.id in state.depleted_asteroids:
            continue
        if len(state.npc_ships) >= len(letters):
            break
        state.npc_ships.append(
            NpcShip(
                letter=letters[len(state.npc_ships)],
                name=asteroid.name,
                position=asteroid.position,
                components=[ShipComponent("01", "reactor", max_health=28.0, health=28.0)],
                shield=0.0,
                max_shield=0.0,
                asteroid=True,
                asteroid_id=asteroid.id,
                loot_item_id=asteroid.loot_item_id,
                loot_name=asteroid.loot_name,
                loot_quantity=asteroid.loot_quantity,
            )
        )
    if state.npc_ships:
        state.mode = GameMode.COMBAT
        state.log("ASTEROID CONTACT: lock a rock and fire to mine its ore.")


def lock_target(state: GameState, letter: str, subtarget: str | None = None) -> str | None:
    letter = letter.upper()
    npc = next((n for n in state.npc_ships if n.letter == letter and n.alive), None)
    if not npc:
        return f"No ship {letter} on scope."
    ship = state.player.ship
    ship.target_letter = letter
    if subtarget:
        comp = find_component(npc.components, subtarget)
        if not comp:
            return "Subtarget: reactor|thrusters|shields|weapons or 01-04"
        ship.subtarget = comp.slot_id
        state.log(f"Locked {letter} {comp.slot_id} {comp.kind}")
    else:
        ship.subtarget = None
        state.log(f"Locked target {letter} ({npc.name})")
    return None


def start_fire(state: GameState) -> str | None:
    if state.mode != GameMode.COMBAT:
        return "Not in combat."
    ship = state.player.ship
    if is_powerless(ship):
        return "No power - reactor offline."
    if not weapons_online(ship):
        return "Weapons destroyed."
    if not ship.target_letter:
        return "No target locked."
    ship.weapons_active = True
    state.log("Weapons HOT. Lasers tracking.")
    return None


def cease_fire(state: GameState) -> str | None:
    state.player.ship.weapons_active = False
    state.log("Cease fire.")
    return None


def _npc_by_letter(state: GameState, letter: str) -> NpcShip | None:
    return next((n for n in state.npc_ships if n.letter == letter and n.alive), None)


def _spawn_laser(state: GameState, tx: float, ty: float, target: str) -> None:
    sx, sy = current_ship_xy(state)
    dx, dy = tx - sx, ty - sy
    dist = math.hypot(dx, dy) or 1.0
    speed = 400.0
    state.projectiles.append(
        Projectile(
            x=sx + 20,
            y=sy,
            vx=dx / dist * speed,
            vy=dy / dist * speed,
            target_letter=target,
            friendly=True,
        )
    )


def _spawn_component_explosion(state: GameState, npc: NpcShip, kind: str) -> None:
    ox, oy = COMP_BLAST_OFFSET.get(kind, (0.0, 0.0))
    state.explosions.append(
        Explosion(x=npc.position.x + ox, y=npc.position.y + oy, ttl=0.75, large=True)
    )
    state.explosions.append(
        Explosion(x=npc.position.x + ox * 0.5, y=npc.position.y + oy * 0.5, ttl=0.5, large=False)
    )


def current_ship_xy(state: GameState) -> tuple[float, float]:
    from eve_ascii.travel import current_ship_coords

    c = current_ship_coords(state)
    return c.x, c.y


def all_hostiles_dead(state: GameState) -> bool:
    return not any(n.alive and n.hostile for n in state.npc_ships)


def tick(state: GameState, dt: float) -> None:
    _decay_fx(state, dt)
    if state.mode != GameMode.COMBAT:
        return
    state.combat_time += dt
    ship = state.player.ship
    ship.fire_cooldown = max(0.0, ship.fire_cooldown - dt)

    if ship.weapons_active:
        if not weapons_online(ship) or is_powerless(ship):
            ship.weapons_active = False
            if is_powerless(ship):
                state.log("Weapons offline - no power.")
            else:
                state.log("Weapons destroyed.")
        elif ship.target_letter and ship.fire_cooldown <= 0:
            npc = _npc_by_letter(state, ship.target_letter)
            if npc:
                ship.fire_cooldown = weapon_charge_seconds(ship)
                _spawn_laser(state, npc.position.x, npc.position.y, npc.letter)

    _tick_projectiles(state, dt)
    if state.npc_ships and all_hostiles_dead(state):
        state.mode = GameMode.SPACE
        state.player.ship.weapons_active = False


def _alive_components(npc: NpcShip) -> list:
    return [c for c in npc.components if not c.destroyed]


def _pick_hit_component(npc: NpcShip, ref: str):
    comp = find_component(npc.components, ref)
    if comp and not comp.destroyed:
        return comp
    alive = _alive_components(npc)
    if not alive:
        return None
    order = ("reactor", "weapons", "thrusters", "shields")
    for kind in order:
        for c in alive:
            if c.kind == kind:
                return c
    return alive[0]


def _destroy_npc(state: GameState, npc: NpcShip, *, reason: str) -> None:
    if not npc.alive:
        return
    npc.alive = False
    state.explosions.append(Explosion(x=npc.position.x, y=npc.position.y, ttl=0.8, large=True))
    state.log(reason)
    if npc.asteroid and npc.asteroid_id:
        from eve_ascii.models import CargoStack

        state.depleted_asteroids.add(npc.asteroid_id)
        item_id = npc.loot_item_id or "ore"
        item_name = npc.loot_name or "Ore"
        stack = next((item for item in state.player.cargo if item.item_id == item_id), None)
        if stack:
            stack.quantity += npc.loot_quantity
        else:
            state.player.cargo.append(CargoStack(item_id, item_name, npc.loot_quantity))
        state.log(f"Mined {npc.loot_quantity}x {item_name}.")
    elif npc.hostile and npc.loot_item_id and npc.loot_quantity > 0:
        from eve_ascii.models import CargoStack

        cargo_used = sum(stack.quantity for stack in state.player.cargo)
        quantity = min(npc.loot_quantity, max(0, state.player.max_cargo - cargo_used))
        if quantity > 0:
            stack = next(
                (item for item in state.player.cargo if item.item_id == npc.loot_item_id),
                None,
            )
            if stack:
                stack.quantity += quantity
            else:
                state.player.cargo.append(CargoStack(npc.loot_item_id, npc.loot_name or npc.name, quantity))
            state.log(f"Recovered {quantity}x {npc.loot_name or npc.name}.")
        else:
            state.log("Cargo hold full; pirate salvage lost.")


def _tick_projectiles(state: GameState, dt: float) -> None:
    remaining: list[Projectile] = []
    for p in state.projectiles:
        p.ttl -= dt
        if p.ttl <= 0:
            continue
        p.x += p.vx * dt
        p.y += p.vy * dt
        npc = _npc_by_letter(state, p.target_letter)
        if npc and npc.alive:
            if math.hypot(p.x - npc.position.x, p.y - npc.position.y) < 35:
                _apply_hit(state, npc)
                continue
        remaining.append(p)
    state.projectiles = remaining


def _apply_hit(state: GameState, npc: NpcShip) -> None:
    if not npc.alive:
        return
    ship = state.player.ship
    ref = ship.subtarget or "reactor"
    comp = _pick_hit_component(npc, ref)
    if not comp:
        _destroy_npc(state, npc, reason=f"{npc.name} destroyed.")
        return
    if ship.subtarget:
        locked = find_component(npc.components, ship.subtarget)
        if locked and locked.destroyed:
            ship.subtarget = None
    before = comp.health
    comp.health = max(0.0, comp.health - 28.0)
    npc.shield = max(0.0, npc.shield - 12.0)
    state.explosions.append(Explosion(x=npc.position.x, y=npc.position.y))
    state.log(f"HIT {npc.letter} {comp.slot_id} {comp.kind} ({comp.health:.0f} hp)")
    if before > 0 and comp.health <= 0:
        _spawn_component_explosion(state, npc, comp.kind)
        state.log(f"{npc.letter} component {comp.slot_id} {comp.kind} DESTROYED")
    if is_powerless(npc):
        _destroy_npc(state, npc, reason=f"{npc.name} reactor destroyed - ship powerless.")
        return
    if not _alive_components(npc):
        _destroy_npc(state, npc, reason=f"{npc.name} destroyed.")


def _decay_fx(state: GameState, dt: float) -> None:
    alive: list[Explosion] = []
    for e in state.explosions:
        e.ttl -= dt
        if e.ttl > 0:
            alive.append(e)
    state.explosions = alive


def tick_hyperspace_vfx(state: GameState, dt: float) -> None:
    from eve_ascii.models import ShipStatus

    ship = state.player.ship
    in_hyperspace = state.mode == GameMode.HYPERSPACE or ship.status == ShipStatus.JUMPING
    if not in_hyperspace:
        state.hyperspace_particles.clear()
        return
    seed_src = state.star_scroll if state.tutorial_step.value == "done" else state.tutorial_timer
    rng = random.Random(int(seed_src * 10))
    if rng.random() < 0.4:
        state.hyperspace_particles.append(
            HyperspaceParticle(
                x=rng.uniform(200, 800),
                y=rng.uniform(-120, 120),
                char=rng.choice(".:*"),
                speed=rng.uniform(120, 280),
            )
        )
    for p in state.hyperspace_particles:
        p.x -= p.speed * dt
    state.hyperspace_particles = [p for p in state.hyperspace_particles if p.x > -50]
