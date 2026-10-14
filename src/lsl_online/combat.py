"""Combat: lock, fire, projectiles, pirates."""

from __future__ import annotations

import math
import random

from lsl_online.models import (
    Explosion,
    GameMode,
    GameState,
    HyperspaceParticle,
    NpcShip,
    Projectile,
    Ship,
    ShipComponent,
    Vec3,
)
from lsl_online.ship import (
    find_component,
    kind_integrity,
    is_powerless,
    PIRATE_BASE_SHIELD,
    PIRATE_HULL_SCALE,
    pirate_components,
    player_laser_damage,
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

PLAYER_PROJ_TARGET = "@"
PLAYER_HIT_RADIUS = 35.0
PIRATE_HIT_DAMAGE = 22.0 * 0.7  # laser damage only; hull/shields unchanged
PIRATE_ENGAGE_DELAY = 9.0
PROJECTILE_TTL = 2.0
# World units: hostiles only fire inside this radius; combat drops when none are this close.
COMBAT_WEAPON_RANGE = 420.0
COMBAT_ENGAGE_RANGE = 420.0



def _scaled_pirate_components(scale: float) -> list[ShipComponent]:
    return [
        ShipComponent(
            c.slot_id,
            c.kind,
            max_health=c.max_health * scale,
            health=c.health * scale,
        )
        for c in pirate_components()
    ]


def _append_hostile(
    state: GameState,
    letter: str,
    name: str,
    index: int,
    *,
    hull_scale: float,
    shield_scale: float,
    damage_scale: float,
    visual_scale: float,
    spacing: float,
) -> None:
    pirate_shield = PIRATE_BASE_SHIELD * PIRATE_HULL_SCALE * shield_scale
    state.npc_ships.append(
        NpcShip(
            letter=letter,
            name=name,
            position=Vec3(200.0 + index * spacing, -8.0 + index * 40, 0.0),
            components=_scaled_pirate_components(hull_scale),
            power=100.0 * hull_scale,
            max_power=100.0 * hull_scale,
            shield=pirate_shield,
            max_shield=pirate_shield,
            fire_cooldown=0.8,
            loot_item_id="pirate_salvage",
            loot_name="Pirate salvage",
            loot_quantity=random.randint(1, 4),
            visual_scale=visual_scale,
            damage_scale=damage_scale,
        )
    )


def spawn_pirates(state: GameState, count: int = 1, *, rim_tier: float = 0.0) -> None:
    state.npc_ships.clear()
    state.combat_time = 0.0
    state.hostile_engage_hold = 0.0
    rim_bonus = 1.0 + 0.5 * rim_tier
    letters = "ABCDEFGH"
    for i in range(min(count, len(letters))):
        roll = random.random()
        if rim_tier > 0.55 and roll < 0.15 + rim_tier * 0.2:
            _append_hostile(
                state,
                letters[i],
                f"Dread-{letters[i]}",
                i,
                hull_scale=1.75 * rim_bonus,
                shield_scale=1.75,
                damage_scale=1.6,
                visual_scale=1.35,
                spacing=180.0,
            )
        elif rim_tier > 0.25 and roll < 0.35 + rim_tier * 0.25:
            _append_hostile(
                state,
                letters[i],
                f"Marauder-{letters[i]}",
                i,
                hull_scale=1.35 * rim_bonus,
                shield_scale=1.35,
                damage_scale=1.25,
                visual_scale=1.15,
                spacing=160.0,
            )
        else:
            _append_hostile(
                state,
                letters[i],
                f"Pirate-{letters[i]}",
                i,
                hull_scale=PIRATE_HULL_SCALE * rim_bonus,
                shield_scale=1.0,
                damage_scale=1.0,
                visual_scale=1.0,
                spacing=140.0,
            )
    state.log(
        f"HOSTILE CONTACT: pirates on scope. Hostile fire in {PIRATE_ENGAGE_DELAY:.0f}s. lock / fire"
    )


def spawn_pirates_for_system(
    state: GameState,
    system_id: str,
    *,
    min_count: int = 0,
) -> None:
    from lsl_online.galaxy import system_rim_tier

    rim = system_rim_tier(state.galaxy, system_id)
    count = random.randint(1, 2) if rim < 0.45 else random.randint(2, 3)
    if min_count > 0:
        count = max(count, min_count)
    count = min(count, 8)
    spawn_pirates(state, count, rim_tier=rim)


def enter_system(state: GameState, system) -> None:
    state.npc_ships.clear()
    state.projectiles.clear()
    state.player.ship.weapons_active = False
    state.player.ship.target_letter = None
    state.player.ship.subtarget = None
    state.mode = GameMode.SPACE


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
            ttl=PROJECTILE_TTL,
        )
    )
    from lsl_online.audio import request_sound

    request_sound(state, "laserShoot")


def _spawn_enemy_laser(
    state: GameState,
    npc: NpcShip,
    tx: float,
    ty: float,
    *,
    damage_scale: float = 1.0,
) -> None:
    sx, sy = npc.position.x, npc.position.y
    dx, dy = tx - sx, ty - sy
    dist = math.hypot(dx, dy) or 1.0
    speed = 360.0
    state.projectiles.append(
        Projectile(
            x=sx - 15,
            y=sy,
            vx=dx / dist * speed,
            vy=dy / dist * speed,
            target_letter=PLAYER_PROJ_TARGET,
            friendly=False,
            ttl=PROJECTILE_TTL,
            damage_scale=damage_scale,
        )
    )
    from lsl_online.audio import request_sound

    request_sound(state, "laserShoot", volume=0.85)


def _spawn_component_explosion(state: GameState, npc: NpcShip, kind: str) -> None:
    ox, oy = COMP_BLAST_OFFSET.get(kind, (0.0, 0.0))
    state.explosions.append(
        Explosion(x=npc.position.x + ox, y=npc.position.y + oy, ttl=0.75, large=True)
    )
    state.explosions.append(
        Explosion(x=npc.position.x + ox * 0.5, y=npc.position.y + oy * 0.5, ttl=0.5, large=False)
    )


def current_ship_xy(state: GameState) -> tuple[float, float]:
    from lsl_online.travel import current_ship_coords

    c = current_ship_coords(state)
    return c.x, c.y


def all_hostiles_dead(state: GameState) -> bool:
    return not any(n.alive and n.hostile for n in state.npc_ships)


def _distance_to_player(state: GameState, npc: NpcShip) -> float:
    px, py = current_ship_xy(state)
    return math.hypot(npc.position.x - px, npc.position.y - py)


def _any_hostile_in_range(state: GameState, weapon_range: float) -> bool:
    return any(
        n.alive and n.hostile and not n.asteroid
        and _distance_to_player(state, n) <= weapon_range
        for n in state.npc_ships
    )


def _leave_combat(state: GameState, message: str | None = None) -> None:
    state.mode = GameMode.SPACE
    ship = state.player.ship
    ship.weapons_active = False
    if message:
        state.log(message)


def _update_combat_engagement(state: GameState) -> None:
    has_hostiles = any(
        n.alive and n.hostile and not n.asteroid for n in state.npc_ships
    )
    in_range = _any_hostile_in_range(state, COMBAT_ENGAGE_RANGE)
    if state.mode == GameMode.COMBAT:
        if not has_hostiles or all_hostiles_dead(state):
            _leave_combat(state)
        elif not in_range:
            state.hostile_engage_hold = 2.0
            _leave_combat(state, "Combat ended — hostiles out of range.")
    elif has_hostiles and in_range:
        state.mode = GameMode.COMBAT


def tick_projectiles(state: GameState, dt: float) -> None:
    """Move lasers and expire by TTL (runs outside combat too while shots are in flight)."""
    if not state.projectiles:
        return
    remaining: list[Projectile] = []
    px, py = current_ship_xy(state)
    resolve_hits = state.mode == GameMode.COMBAT and not state.game_over
    for p in state.projectiles:
        p.ttl -= dt
        if p.ttl <= 0:
            continue
        p.x += p.vx * dt
        p.y += p.vy * dt
        if resolve_hits:
            if p.friendly:
                npc = _npc_by_letter(state, p.target_letter)
                if npc and npc.alive:
                    if math.hypot(p.x - npc.position.x, p.y - npc.position.y) < PLAYER_HIT_RADIUS:
                        _apply_hit(state, npc)
                        continue
            elif p.target_letter == PLAYER_PROJ_TARGET:
                if math.hypot(p.x - px, p.y - py) < PLAYER_HIT_RADIUS:
                    _apply_hit_player(state, p.damage_scale)
                    continue
        remaining.append(p)
    state.projectiles = remaining


def tick(state: GameState, dt: float) -> None:
    _decay_fx(state, dt)
    tick_projectiles(state, dt)
    if state.game_over:
        return
    _update_combat_engagement(state)
    if state.mode != GameMode.COMBAT:
        return
    if state.hostile_engage_hold > 0:
        state.hostile_engage_hold = max(0.0, state.hostile_engage_hold - dt)
    state.combat_time += dt
    ship = state.player.ship

    if ship.fire_cooldown > 0:
        if not tick_weapon_recharge(ship, dt) and ship.weapons_active:
            if not ship.power_starve_logged:
                ship.power_starve_logged = True
                state.log("Weapon recharge stalled - low power.")

    if ship.weapons_active:
        if not weapons_online(ship) or is_powerless(ship):
            ship.weapons_active = False
            if is_powerless(ship):
                state.log("Weapons offline - no power.")
            else:
                state.log("Weapons destroyed.")
        elif ship.fire_cooldown <= 0 and ship.target_letter:
            npc = _npc_by_letter(state, ship.target_letter)
            if (
                npc
                and _distance_to_player(state, npc) <= COMBAT_WEAPON_RANGE
                and try_fire_shot(ship)
            ):
                ship.fire_cooldown = weapon_charge_seconds(ship)
                ship.power_starve_logged = False
                _spawn_laser(state, npc.position.x, npc.position.y, npc.letter)
            elif npc and ship.power + 1e-9 < 4.0:
                if not ship.power_starve_logged:
                    ship.power_starve_logged = True
                    state.log("Cannot fire - not enough power.")

    _tick_hostile_fire(state, dt)
    if _player_ship_destroyed(state.player.ship):
        _handle_player_game_over(state)
        return


def _alive_components(vessel: Ship | NpcShip) -> list:
    return [c for c in vessel.components if not c.destroyed]


def _player_ship_destroyed(ship: Ship) -> bool:
    return not _alive_components(ship)


def _handle_player_game_over(state: GameState) -> None:
    if state.game_over:
        return
    state.game_over = True
    sx, sy = current_ship_xy(state)
    state.explosions.append(Explosion(x=sx, y=sy, ttl=1.2, large=True))
    state.player.ship.weapons_active = False
    state.mining_active = False
    state.log("GAME OVER — ship destroyed. Type quit to exit.")
    from lsl_online.audio import request_sound, stop_all_loops

    stop_all_loops()
    request_sound(state, "explosion")


def _pick_hit_component(vessel: Ship | NpcShip, ref: str):
    comp = find_component(vessel.components, ref)
    if comp and not comp.destroyed:
        return comp
    alive = [c for c in vessel.components if not c.destroyed]
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
    from lsl_online.audio import request_sound

    request_sound(state, "explosion")
    state.log(reason)
    if npc.hostile and not npc.asteroid:
        from lsl_online.quests import note_hostile_kill

        note_hostile_kill(state)
    if npc.asteroid and npc.asteroid_id:
        from lsl_online.models import CargoStack

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
        from lsl_online.models import CargoStack

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
            request_sound(state, "pickup")
        else:
            state.log("Cargo hold full; pirate salvage lost.")


def _tick_hostile_fire(state: GameState, dt: float) -> None:
    if state.hostile_engage_hold > 0:
        return
    if state.combat_time < PIRATE_ENGAGE_DELAY:
        return
    px, py = current_ship_xy(state)
    for npc in state.npc_ships:
        if not npc.alive or not npc.hostile or npc.asteroid:
            continue
        if npc.fire_cooldown > 0:
            tick_weapon_recharge(npc, dt)
            continue
        if not weapons_online(npc) or is_powerless(npc):
            continue
        if _distance_to_player(state, npc) > COMBAT_WEAPON_RANGE:
            continue
        if try_fire_shot(npc):
            npc.fire_cooldown = weapon_charge_seconds(npc) * 0.9
            _spawn_enemy_laser(state, npc, px, py, damage_scale=npc.damage_scale)


def _apply_hit_player(state: GameState, damage_scale: float = 1.0) -> None:
    ship = state.player.ship
    if _player_ship_destroyed(ship):
        return
    sx, sy = current_ship_xy(state)
    state.explosions.append(Explosion(x=sx, y=sy, ttl=0.45, large=False))
    from lsl_online.audio import request_sound

    request_sound(state, "hit")
    damage = PIRATE_HIT_DAMAGE * max(0.1, damage_scale)
    if ship.shield > 0 and kind_integrity(ship.components, "shields") > 0:
        absorbed = min(ship.shield, damage)
        ship.shield = max(0.0, ship.shield - absorbed)
        damage -= absorbed
        if absorbed > 0:
            state.log(f"HOSTILE HIT shield ({ship.shield:.0f} left)")
    if damage <= 0:
        return
    alive = [c for c in ship.components if not c.destroyed]
    if not alive:
        state.log("HOSTILE HIT - hull breach!")
        return
    comp = random.choice(alive)
    before = comp.health
    comp.health = max(0.0, comp.health - damage)
    state.log(f"HOSTILE HIT {comp.slot_id} {comp.kind} ({comp.health:.0f} hp)")
    if before > 0 and comp.health <= 0:
        ox, oy = COMP_BLAST_OFFSET.get(comp.kind, (0.0, 0.0))
        state.explosions.append(Explosion(x=sx + ox, y=sy + oy, ttl=0.75, large=True))
        state.log(f"Your {comp.kind} DESTROYED")
        request_sound(state, "explosion")
    if is_powerless(ship):
        state.log("REACTOR OFFLINE - ship powerless!")
        ship.weapons_active = False
    if _player_ship_destroyed(ship):
        _handle_player_game_over(state)


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
    comp.health = max(0.0, comp.health - player_laser_damage(ship))
    npc.shield = max(0.0, npc.shield - 12.0)
    state.explosions.append(Explosion(x=npc.position.x, y=npc.position.y))
    from lsl_online.audio import request_sound

    request_sound(state, "hit")
    state.log(f"HIT {npc.letter} {comp.slot_id} {comp.kind} ({comp.health:.0f} hp)")
    if before > 0 and comp.health <= 0:
        _spawn_component_explosion(state, npc, comp.kind)
        state.log(f"{npc.letter} component {comp.slot_id} {comp.kind} DESTROYED")
        request_sound(state, "explosion")
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


def _hyperspace_speed_scale(state: GameState) -> float:
    from lsl_online.models import ShipStatus

    ship = state.player.ship
    jumping = state.mode == GameMode.HYPERSPACE or ship.status == ShipStatus.JUMPING
    if state.hyperspace_landing_timer > 0 and not jumping:
        return max(0.4, state.hyperspace_landing_timer / 0.45)
    if not jumping:
        return 1.0
    total = ship.transit_total_seconds
    if total <= 0:
        return 4.0
    progress = 1.0 - max(0.0, ship.eta_seconds) / total
    progress = max(0.0, min(1.0, progress))
    return 4.0 - 3.0 * progress


def tick_hyperspace_vfx(state: GameState, dt: float) -> None:
    from lsl_online.models import ShipStatus

    if state.hyperspace_landing_timer > 0:
        state.hyperspace_landing_timer = max(0.0, state.hyperspace_landing_timer - dt)

    ship = state.player.ship
    in_hyperspace = (
        state.mode == GameMode.HYPERSPACE
        or ship.status == ShipStatus.JUMPING
        or state.hyperspace_landing_timer > 0
    )
    if not in_hyperspace:
        state.hyperspace_particles.clear()
        return
    speed_scale = _hyperspace_speed_scale(state)
    if state.hyperspace_landing_timer > 0 and ship.status != ShipStatus.JUMPING:
        speed_scale = max(0.35, speed_scale * 0.5)
    seed_src = state.star_scroll if state.tutorial_step.value == "done" else state.tutorial_timer
    rng = random.Random(int(seed_src * 10))
    if rng.random() < 0.55:
        base = rng.uniform(120, 280)
        state.hyperspace_particles.append(
            HyperspaceParticle(
                x=rng.uniform(200, 800),
                y=rng.uniform(-120, 120),
                char=rng.choice(".:*"),
                speed=base * speed_scale,
            )
        )
    for p in state.hyperspace_particles:
        p.x -= p.speed * dt
    state.hyperspace_particles = [p for p in state.hyperspace_particles if p.x > -50]
