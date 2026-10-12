from eve_ascii.ascii_ui import ascii_only
from eve_ascii.models import GameState


def format_status(state: GameState) -> str:
    ship = state.player.ship
    sys = state.galaxy.get_system(ship.location.system_id)
    sys_name = ascii_only(sys.name) if sys else "?"
    line = (
        f" {sys_name} | {ship.status.value} | "
        f"({ship.location.coords.x:.0f},{ship.location.coords.y:.0f},{ship.location.coords.z:.0f})"
    )
    if ship.eta_seconds > 0:
        line += f" | ETA {ship.eta_seconds:.1f}s"
    return line
