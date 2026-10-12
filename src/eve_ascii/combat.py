"""Combat: lock, fire, projectiles, pirates."""

from __future__ import annotations

import math
import random

from eve_ascii.models import (
    COMPONENT_IDS,
    COMPONENT_NAMES,
    Explosion,
    GameMode,
    GameState,
    HyperspaceParticle,
    NpcShip,
    Projectile,
    Vec3,
)

# Local offset from ship center for component explosions (world units)
COMP_BLAST_OFFSET = {
    "reactor": (0.0, -18.0),
    "shield": (-14.0, 0.0),
    "hyperdrive": (14.0, 0.0),
    "cargo": (0.0, 18.0),
}


def resolve_subtarget(name: str) -> str | None:
    key = name.lower().strip()
    if key in COMPONENT_NAMES:
        return key
    if key in COMPONENT_IDS:
        return COMPONENT_IDS[key]
    return None


def spawn_pirates(state: GameState, count: int = 2) -> None:
    state.npc_ships.clear()
    letters = "AB"
    for i in range(count):
        state.npc_ships.append(
            NpcShip(
                letter=letters[i],
                name=f"Pirate-{letters[i]}",
                position=Vec3(420.0 + i * 140, -20.0 + i * 60, 0.0),
                components={
                    "reactor": 30.0,
                    "shield": 25.0,
                    "hyperdrive": 20.0,
                    "cargo": 15.0,
                },
            )
        )
    state.log("HOSTILE CONTACT: pirates on scope. lock / fire")


def lock_target(state: GameState, letter: str, subtarget: str | None = None) -> str | None:
    letter = letter.upper()
    npc = next((n for n in state.npc_ships if n.letter == letter and n.alive), None)
    if not npc:
        return f"No ship {letter} on scope."
    ship = state.player.ship
    ship.target_letter = letter
    if subtarget:
        comp = resolve_subtarget(subtarget)
        if not comp:
            return "Subtarget: reactor|shield|hyperdrive|cargo or 01-04"
        ship.subtarget = comp
        state.log(f"Locked {letter} subtarget {comp}")
    else:
        ship.subtarget = None
        state.log(f"Locked target {letter} ({npc.name})")
    return None


def start_fire(state: GameState) -> str | None:
    if state.mode != GameMode.COMBAT:
        return "Not in combat."
    ship = state.player.ship
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


def _spawn_component_explosion(state: GameState, npc: NpcShip, comp: str) -> None:
    ox, oy = COMP_BLAST_OFFSET.get(comp, (0.0, 0.0))
    state.explosions.append(
        Explosion(x=npc.position.x + ox, y=npc.position.y + oy, ttl=0.75, large=True)
    )
    state.explosions.append(
        Explosion(x=npc.position.x + ox * 0.5, y=npc.position.y + oy * 0.5, ttl=0.5, large=False)
    )


def _apply_damage(state: GameState, npc: NpcShip, comp: str, amount: float) -> None:
    before = npc.components.get(comp, 0.0)
    after = max(0.0, before - amount)
    npc.components[comp] = after
    if before > 0 and after <= 0:
        _spawn_component_explosion(state, npc, comp)
        state.log(f"{npc.letter} component {comp} DESTROYED")


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

    if ship.weapons_active and ship.target_letter and ship.fire_cooldown <= 0:
        npc = _npc_by_letter(state, ship.target_letter)
        if npc:
            ship.fire_cooldown = 0.35
            _spawn_laser(state, npc.position.x, npc.position.y, npc.letter)

    _tick_projectiles(state, dt)

    if state.tutorial_step.value == "combat" and state.combat_time >= 18.0:
        for n in state.npc_ships:
            if n.alive:
                n.alive = False
                state.explosions.append(
                    Explosion(x=n.position.x, y=n.position.y, ttl=0.8, large=True)
                )


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
                primary = state.player.ship.subtarget or "shield"
                _apply_damage(state, npc, primary, 22.0)
                _apply_damage(state, npc, "reactor", 8.0)
                state.explosions.append(
                    Explosion(x=npc.position.x, y=npc.position.y, ttl=0.25, large=False)
                )
                state.log(f"HIT {npc.letter} {primary} ({npc.components.get(primary, 0):.0f}%)")
                if npc.components.get("reactor", 0) <= 0 or sum(npc.components.values()) <= 5:
                    npc.alive = False
                    state.explosions.append(
                        Explosion(x=npc.position.x, y=npc.position.y, ttl=0.9, large=True)
                    )
                    state.log(f"{npc.name} destroyed.")
                continue
        remaining.append(p)
    state.projectiles = remaining


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
