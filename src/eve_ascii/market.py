"""Station market: inventory view, sell, component upgrades."""

from __future__ import annotations

from rich.style import Style
from rich.text import Text

from eve_ascii.ascii_ui import ascii_only
from eve_ascii.models import CargoStack, GameState, ShipStatus
from eve_ascii.ship import find_component

TUTORIAL_CARGO_ID = "flagged_cargo"
TUTORIAL_CARGO_NAME = "Flagged Military Cargo"

# item_id -> base credits per unit at a typical station
BASE_PRICES: dict[str, float] = {
    TUTORIAL_CARGO_ID: 1200.0,
    "scrap": 45.0,
    "ore": 80.0,
}

UPGRADE_COST: dict[str, float] = {
    "reactor": 2500.0,
    "weapons": 2500.0,
}
UPGRADE_HP_BONUS = 30.0


def starter_cargo() -> list[CargoStack]:
    return [
        CargoStack(TUTORIAL_CARGO_ID, TUTORIAL_CARGO_NAME, 10),
    ]


def local_price(state: GameState, item_id: str) -> float:
    base = BASE_PRICES.get(item_id, 100.0)
    station_id = state.player.ship.location.station_id or "none"
    sys_id = state.player.system_id
    # Stable per-station variance
    seed = hash((sys_id, station_id, item_id)) % 1000
    factor = 0.92 + (seed / 1000.0) * 0.16
    return round(base * factor, 0)


def find_cargo(player, ref: str) -> CargoStack | None:
    key = ref.strip().casefold()
    for stack in player.cargo:
        if stack.quantity <= 0:
            continue
        if stack.item_id.casefold() == key or key in stack.name.casefold():
            return stack
    return None


def show_inventory(state: GameState) -> str | None:
    if state.player.ship.status != ShipStatus.DOCKED:
        return "Inventory is only available while docked."
    state.station_view = "inventory"
    state.log("Station inventory / market prices.")
    return None


def show_hangar(state: GameState) -> str | None:
    if state.player.ship.status != ShipStatus.DOCKED:
        return "Not docked."
    state.station_view = "hangar"
    state.log("Hangar view.")
    return None


def sell_item(state: GameState, item_ref: str, quantity: int) -> str | None:
    if state.player.ship.status != ShipStatus.DOCKED:
        return "Must be docked to sell."
    if quantity <= 0:
        return "Quantity must be positive."
    stack = find_cargo(state.player, item_ref)
    if not stack:
        return f"No cargo matching '{item_ref}'."
    if quantity > stack.quantity:
        return f"Only {stack.quantity} units available."
    unit = local_price(state, stack.item_id)
    total = unit * quantity
    stack.quantity -= quantity
    if stack.quantity <= 0:
        state.player.cargo = [c for c in state.player.cargo if c.quantity > 0]
    state.player.credits += total
    state.log(f"Sold {quantity}x {stack.name} for {total:.0f} cr ({unit:.0f}/ea).")
    if stack.item_id == TUTORIAL_CARGO_ID and not any(
        c.item_id == TUTORIAL_CARGO_ID and c.quantity > 0 for c in state.player.cargo
    ):
        state.tutorial_sell_done = True
    state.station_view = "inventory"
    return None


def upgrade_component(state: GameState, kind: str) -> str | None:
    if state.player.ship.status != ShipStatus.DOCKED:
        return "Must be docked to upgrade."
    key = kind.strip().lower()
    if key not in UPGRADE_COST:
        return "Upgrade: reactor | weapons"
    cost = UPGRADE_COST[key]
    if state.player.credits < cost:
        return f"Need {cost:.0f} cr (have {state.player.credits:.0f})."
    comp = find_component(state.player.ship.components, key)
    if not comp:
        return f"No {key} module installed."
    state.player.credits -= cost
    comp.max_health += UPGRADE_HP_BONUS
    comp.health = comp.max_health
    state.log(f"Upgraded {comp.kind}: +{UPGRADE_HP_BONUS:.0f} max hp ({cost:.0f} cr).")
    if key == "reactor":
        state.tutorial_upgraded_reactor = True
        state.player.ship.max_power += 15.0
        state.player.ship.power = min(state.player.ship.max_power, state.player.ship.power + 15.0)
    elif key == "weapons":
        state.tutorial_upgraded_weapons = True
    return None


def render_inventory_view(state: GameState, width: int, height: int) -> Text:
    ship = state.player.ship
    sys = state.galaxy.get_system(ship.location.system_id)
    st_name = "station"
    if sys and ship.location.station_id:
        st = next((s for s in sys.stations if s.id == ship.location.station_id), None)
        if st:
            st_name = st.name

    inner_w = max(20, width - 2)
    slug_w, qty_w, price_w = 16, 5, 9
    name_w = max(12, inner_w - slug_w - qty_w - price_w - 2)
    table_w = name_w + slug_w + qty_w + price_w + 1
    header = Text()
    header.append(f" {ascii_only(st_name)} MARKET ", style=Style(color="#c9a86a", bold=True))
    header.append(f"| credits {state.player.credits:.0f} cr\n", style=Style(color="#88ccaa"))
    rule = "-" * min(inner_w, table_w)
    header.append(rule + "\n", style=Style(color="#556677"))
    header.append(
        f" {'item name':<{name_w}}{'id/slug':<{slug_w}}{'qty':>{qty_w}}{'price':>{price_w}}\n",
        style=Style(color="#aaccee", bold=True),
    )
    header.append(rule + "\n", style=Style(color="#556677"))

    rows = state.player.cargo
    if not rows:
        header.append(" (empty hold)\n", style=Style(color="#778899"))
    for stack in rows:
        if stack.quantity <= 0:
            continue
        price = local_price(state, stack.item_id)
        nm = ascii_only(stack.name)[:name_w]
        slug = ascii_only(stack.item_id)[:slug_w]
        header.append(f" {nm:<{name_w}}", style=Style(color="#ddeeff"))
        header.append(f"{slug:<{slug_w}}", style=Style(color="#99aabb"))
        header.append(f"{stack.quantity:>{qty_w}}", style=Style(color="#ffee88"))
        header.append(f"{price:>{price_w}.0f}\n", style=Style(color="#88ffaa"))

    header.append(rule + "\n", style=Style(color="#556677"))
    header.append(
        " commands: sell <name|id> <qty>  |  hangar  |  upgrade reactor|weapons\n",
        style=Style(color="#668899"),
    )
    return header
