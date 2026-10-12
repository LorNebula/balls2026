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
    Vec3,
)
from eve_ascii.ship import (
    find_component,
    is_powerless,
    pirate_components,
    weapon_charge_seconds,
    weapons_online,
)


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
                shield=40.0,
                max_shield=40.0,
            )
        )
    state.log("HOSTILE CONTACT: pirate on scope. lock / fire")


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
        return "No power — reactor offline."
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


def current_ship_xy(state: GameState) -> tuple[float, float]:
    from eve_ascii.travel import current_ship_coords

    c = current_ship_coords(state)
    return c.x, c.y


def all_hostiles_dead(state: GameState) -> bool:
    return not any(n.alive and n.hostile for n in state.npc_ships)


def tick(state: GameState, dt: float) -> None:
    if state.mode != GameMode.COMBAT:
        _decay_fx(state, dt)
        return
    state.combat_time += dt
    ship = state.player.ship
    ship.fire_cooldown = max(0.0, ship.fire_cooldown - dt)

    if ship.weapons_active:
        if not weapons_online(ship) or is_powerless(ship):
            ship.weapons_active = False
            if is_powerless(ship):
                state.log("Weapons offline — no power.")
            else:
                state.log("Weapons destroyed.")
        elif ship.target_letter and ship.fire_cooldown <= 0:
            npc = _npc_by_letter(state, ship.target_letter)
            if npc:
                ship.fire_cooldown = weapon_charge_seconds(ship)
                _spawn_laser(state, npc.position.x, npc.position.y, npc.letter)

    _tick_projectiles(state, dt)
    _decay_fx(state, dt)

    if state.tutorial_step.value == "combat" and state.combat_time >= 18.0:
        for n in state.npc_ships:
            if n.alive:
                n.alive = False
                state.explosions.append(Explosion(x=n.position.x, y=n.position.y))


def _tick_projectiles(state: GameState, dt: float) -> None:
    remaining: list[Projectile] = []
    for p in state.projectiles:
        p.ttl -= dt
        if p.ttl <= 0:
            continue
        p.x += p.vx * dt
        p.y += p.vy * dt
        npc = _npc_by_letter(state, p.target_letter)
        if npc:
            if math.hypot(p.x - npc.position.x, p.y - npc.position.y) < 35:
                _apply_hit(state, npc)
                continue
        remaining.append(p)
    state.projectiles = remaining


def _apply_hit(state: GameState, npc: NpcShip) -> None:
    ship = state.player.ship
    ref = ship.subtarget or "shields"
    comp = find_component(npc.components, ref) or (npc.components[0] if npc.components else None)
    if not comp:
        return
    comp.health = max(0.0, comp.health - 22.0)
    npc.shield = max(0.0, npc.shield - 8.0)
    state.explosions.append(Explosion(x=npc.position.x, y=npc.position.y))
    state.log(f"HIT {npc.letter} {comp.slot_id} {comp.kind} ({comp.health:.0f} hp)")
    if is_powerless(npc):
        npc.alive = False
        state.explosions.append(Explosion(x=npc.position.x, y=npc.position.y, ttl=0.8))
        state.log(f"{npc.name} reactor destroyed — ship powerless.")
        return
    if all(c.destroyed for c in npc.components):
        npc.alive = False
        state.explosions.append(Explosion(x=npc.position.x, y=npc.position.y, ttl=0.8))
        state.log(f"{npc.name} destroyed.")


def _decay_fx(state: GameState, dt: float) -> None:
    alive: list[Explosion] = []
    for e in state.explosions:
        e.ttl -= dt
        if e.ttl > 0:
            alive.append(e)
    state.explosions = alive


def tick_hyperspace_vfx(state: GameState, dt: float) -> None:
    if state.mode != GameMode.HYPERSPACE:
        state.hyperspace_particles.clear()
        return
    rng = random.Random(int(state.tutorial_timer * 10))
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
