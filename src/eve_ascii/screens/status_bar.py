from eve_ascii.ascii_ui import ascii_only
from eve_ascii.models import GameState


def format_status(state: GameState) -> str:
    ship = state.player.ship
    sys = state.galaxy.get_system(ship.location.system_id)
    sys_name = ascii_only(sys.name) if sys else "?"
    line = (
        f" {sys_name} | {state.mode.value} | {ship.status.value} | "
        f"pwr {ship.power:.0f} | shd {ship.shield:.0f}/{ship.max_shield:.0f} | "
        f"fuel {ship.fuel:.0f}/{ship.max_fuel:.0f}"
    )
    if ship.target_letter:
        sub = ship.subtarget or "hull"
        line += f" | tgt {ship.target_letter}/{sub}"
    if ship.weapons_active:
        line += " | FIRING"
    if ship.eta_seconds > 0:
        line += f" | ETA {ship.eta_seconds:.1f}s"
    if state.tutorial_step.value != "done":
        line += f" | tut:{state.tutorial_step.value}"
    return line
