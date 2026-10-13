from eve_ascii.ascii_ui import ascii_only
from eve_ascii.models import GameState
from eve_ascii.quests import current_objective
from eve_ascii.ship import hull_totals


def format_status(state: GameState) -> str:
    ship = state.player.ship
    sys = state.galaxy.get_system(ship.location.system_id)
    sys_name = ascii_only(sys.name) if sys else "?"
    if state.game_over:
        return " GAME OVER | type quit to exit "
    hp, hp_max = hull_totals(ship)
    cargo_used = sum(s.quantity for s in state.player.cargo)
    line = (
        f" {sys_name} | {state.mode.value} | {ship.status.value} | "
        f"cargo {cargo_used}/{state.player.max_cargo} | "
        f"nrg {ship.power:.0f}/{ship.max_power:.0f} | "
        f"hp {hp:.0f}/{hp_max:.0f} | "
        f"shd {ship.shield:.0f}/{ship.max_shield:.0f} | "
        f"fuel {ship.fuel:.0f}/{ship.max_fuel:.0f} | "
        f"cr {state.player.credits:.0f}"
    )
    if ship.target_letter:
        sub = ship.subtarget or "hull"
        line += f" | tgt {ship.target_letter}/{sub}"
    if ship.weapons_active:
        line += " | FIRING"
    if ship.eta_seconds > 0:
        line += f" | ETA {ship.eta_seconds:.1f}s"
    objective = ascii_only(current_objective(state))
    if objective:
        line += f" | obj: {objective}"
    return line
