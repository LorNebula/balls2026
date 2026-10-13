"""Station market: inventory view, sell, component upgrades."""

from __future__ import annotations

from rich.style import Style
from rich.text import Text

from eve_ascii.ascii_ui import ascii_only
from eve_ascii.materials import MATERIALS, base_prices_map
from eve_ascii.models import CargoStack, GameState, ShipStatus
from eve_ascii.ship import find_component

TUTORIAL_CARGO_ID = "flagged_cargo"
TUTORIAL_CARGO_NAME = "Flagged Military Cargo"

# item_id -> base credits per unit at a typical station
BASE_PRICES: dict[str, float] = {
    TUTORIAL_CARGO_ID: 1200.0,
    "scrap": 45.0,
    "ore": 80.0,
    "ice": 60.0,
    "reactor_upgrade": 2500.0,
    "weapons_upgrade": 2500.0,
    **base_prices_map(),
}

ITEM_NAMES: dict[str, str] = {
    TUTORIAL_CARGO_ID: TUTORIAL_CARGO_NAME,
    "scrap": "Scrap",
    "ore": "Ore",
    "ice": "Ice",
    "reactor_upgrade": "Reactor upgrade",
    "weapons_upgrade": "Weapons upgrade",
}
for _mat in MATERIALS:
    ITEM_NAMES.setdefault(_mat.id, _mat.name)

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
    station = _current_station(state)
    if station and item_id in station.prices:
        return station.prices[item_id]
    station_id = state.player.ship.location.station_id or "none"
    sys_id = state.player.ship.location.system_id
    seed = sum((index + 1) * ord(char) for index, char in enumerate(f"{sys_id}:{station_id}:{item_id}")) % 1000
    factor = 0.92 + (seed / 1000.0) * 0.16
    return round(base * factor, 0)


def _current_station(state: GameState):
    system = state.galaxy.get_system(state.player.ship.location.system_id)
    if not system or not state.player.ship.location.station_id:
        return None
    return next(
        (station for station in system.stations if station.id == state.player.ship.location.station_id),
        None,
    )


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


def show_system_view(state: GameState) -> str | None:
    if state.player.ship.status == ShipStatus.DOCKED:
        state.station_view = "system"
    state.log("System view.")
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
    station = _current_station(state)
    if station:
        station.inventory[stack.item_id] = station.inventory.get(stack.item_id, 0) + quantity
    state.log(f"Sold {quantity}x {stack.name} for {total:.0f} cr ({unit:.0f}/ea).")
    state.station_view = "inventory"
    return None


def buy_item(state: GameState, item_ref: str, quantity: int) -> str | None:
    if state.player.ship.status != ShipStatus.DOCKED:
        return "Must be docked to buy."
    if quantity <= 0:
        return "Quantity must be positive."
    key = item_ref.strip().casefold()
    normalized = {
        "reactor": "reactor_upgrade",
        "weapons": "weapons_upgrade",
    }.get(key, key)
    if normalized in ("reactor_upgrade", "weapons_upgrade"):
        if quantity != 1:
            return "Ship upgrades are purchased one at a time."
        return upgrade_component(state, normalized.removesuffix("_upgrade"))

    station = _current_station(state)
    if not station:
        return "No market at this station."
    item_id = next(
        (
            item
            for item, label in ITEM_NAMES.items()
            if item == normalized or label.casefold() == key
        ),
        None,
    )
    if not item_id or item_id not in station.inventory:
        return f"Item not sold here: {item_ref}."
    available = station.inventory[item_id]
    if quantity > available:
        return f"Only {available} units in stock."
    total = local_price(state, item_id) * quantity
    if state.player.credits < total:
        return f"Need {total:.0f} cr (have {state.player.credits:.0f})."
    station.inventory[item_id] -= quantity
    state.player.credits -= total
    stack = next((cargo for cargo in state.player.cargo if cargo.item_id == item_id), None)
    if stack:
        stack.quantity += quantity
    else:
        from eve_ascii.models import CargoStack

        state.player.cargo.append(CargoStack(item_id, ITEM_NAMES[item_id], quantity))
    state.log(f"Bought {quantity}x {ITEM_NAMES[item_id]} for {total:.0f} cr.")
    state.station_view = "inventory"
    return None


def upgrade_component(state: GameState, kind: str) -> str | None:
    if state.player.ship.status != ShipStatus.DOCKED:
        return "Must be docked to upgrade."
    key = kind.strip().lower()
    if key not in UPGRADE_COST:
        return "Upgrade: reactor | weapons"
    station = _current_station(state)
    stock_id = f"{key}_upgrade"
    if station and station.inventory and station.inventory.get(stock_id, 0) <= 0:
        return f"{key.title()} upgrades are out of stock."
    cost = local_price(state, stock_id) if station and stock_id in station.inventory else UPGRADE_COST[key]
    if state.player.credits < cost:
        return f"Need {cost:.0f} cr (have {state.player.credits:.0f})."
    comp = find_component(state.player.ship.components, key)
    if not comp:
        return f"No {key} module installed."
    state.player.credits -= cost
    if station and stock_id in station.inventory:
        station.inventory[stock_id] -= 1
    comp.max_health += UPGRADE_HP_BONUS
    comp.health = comp.max_health
    state.log(f"Upgraded {comp.kind}: +{UPGRADE_HP_BONUS:.0f} max hp ({cost:.0f} cr).")
    if key == "reactor":
        state.player.ship.max_power += 15.0
        state.player.ship.power = min(state.player.ship.max_power, state.player.ship.power + 15.0)
    return None


def render_inventory_view(state: GameState, width: int, height: int) -> Text:
    ship = state.player.ship
    sys = state.galaxy.get_system(ship.location.system_id)
    st_name = "station"
    station = None
    if sys and ship.location.station_id:
        station = next((s for s in sys.stations if s.id == ship.location.station_id), None)
        if station:
            st_name = station.name

    inner_w = max(20, width - 2)
    slug_w, market_w, hold_w, price_w = 16, 7, 5, 9
    name_w = max(12, inner_w - slug_w - market_w - hold_w - price_w - 4)
    table_w = name_w + slug_w + market_w + hold_w + price_w + 4
    header = Text()
    header.append(f" {ascii_only(st_name)} MARKET ", style=Style(color="#c9a86a", bold=True))
    header.append(f"| credits {state.player.credits:.0f} cr\n", style=Style(color="#88ccaa"))
    rule = "-" * min(inner_w, table_w)
    header.append(rule + "\n", style=Style(color="#556677"))
    header.append(
        f" {'item name':<{name_w}}{'id/slug':<{slug_w}}{'stock':>{market_w}}{'hold':>{hold_w}}{'price':>{price_w}}\n",
        style=Style(color="#aaccee", bold=True),
    )
    header.append(rule + "\n", style=Style(color="#556677"))

    cargo = {stack.item_id: stack for stack in state.player.cargo if stack.quantity > 0}
    inventory = station.inventory if station else {}
    item_ids = sorted(set(cargo) | {item_id for item_id, qty in inventory.items() if qty > 0})
    if not item_ids:
        header.append(" (no stock or cargo)\n", style=Style(color="#778899"))
    for item_id in item_ids:
        stack = cargo.get(item_id)
        name = stack.name if stack else ITEM_NAMES.get(item_id, item_id.replace("_", " ").title())
        nm = ascii_only(name)[:name_w]
        slug = ascii_only(item_id)[:slug_w]
        stock = inventory.get(item_id, 0)
        hold = stack.quantity if stack else 0
        price = local_price(state, item_id)
        header.append(f" {nm:<{name_w}}", style=Style(color="#ddeeff"))
        header.append(f"{slug:<{slug_w}}", style=Style(color="#99aabb"))
        header.append(f"{stock:>{market_w}}", style=Style(color="#ffee88"))
        header.append(f"{hold:>{hold_w}}", style=Style(color="#ffee88"))
        header.append(f"{price:>{price_w}.0f}\n", style=Style(color="#88ffaa"))

    header.append(rule + "\n", style=Style(color="#556677"))
    header.append(
        " commands: buy <item> <qty>  |  sell <item> <qty>  |  upgrade reactor|weapons\n",
        style=Style(color="#668899"),
    )
    return header
