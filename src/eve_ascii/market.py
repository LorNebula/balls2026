"""Station market: inventory view, sell, component upgrades."""

from __future__ import annotations

import random

from rich.style import Style
from rich.text import Text

from eve_ascii.ascii_ui import ascii_only
from eve_ascii.materials import MATERIALS, base_prices_map
from eve_ascii.models import CargoStack, GameState, ShipLocation, ShipStatus
from eve_ascii.ship import find_component
from eve_ascii.shipyard import SHIP_TYPES, SHIP_TYPES_BY_ID, build_ship

TUTORIAL_CARGO_ID = "flagged_cargo"
TUTORIAL_CARGO_NAME = "Flagged Military Cargo"

# item_id -> base credits per unit at a typical station
BASE_PRICES: dict[str, float] = {
    TUTORIAL_CARGO_ID: 1200.0,
    "scrap": 45.0,
    "pirate_scrap": 110.0,
    "ore": 80.0,
    "ice": 60.0,
    "reactor_upgrade": 2500.0,
    "weapons_upgrade": 2500.0,
    **base_prices_map(),
}

ITEM_NAMES: dict[str, str] = {
    TUTORIAL_CARGO_ID: TUTORIAL_CARGO_NAME,
    "scrap": "Scrap",
    "pirate_scrap": "Pirate salvage",
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
MARKET_RESTOCK_INTERVAL = 60.0


def starter_cargo() -> list[CargoStack]:
    return [
        CargoStack(TUTORIAL_CARGO_ID, TUTORIAL_CARGO_NAME, 10),
    ]


def _station_price(station, item_id: str) -> float:
    base = station.prices.get(item_id, BASE_PRICES.get(item_id, 100.0))
    stock = station.inventory.get(item_id, 0)
    supply_factor = max(0.5, min(1.5, 1.0 + (20 - stock) / 50.0))
    return round(base * supply_factor, 0)


def local_price(state: GameState, item_id: str) -> float | None:
    station = _current_station(state)
    return _station_price(station, item_id) if station else None


def global_price(state: GameState, item_id: str) -> float:
    stations = [station for system in state.galaxy.systems.values() for station in system.stations]
    if not stations:
        return round(BASE_PRICES.get(item_id, 100.0), 0)
    return round(sum(_station_price(station, item_id) for station in stations) / len(stations), 0)


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


def show_market(state: GameState) -> str | None:
    if state.player.ship.status != ShipStatus.DOCKED:
        return "Market is only available while docked."
    if not _current_station(state):
        return "No market at this station."
    state.map_view = "system"
    state.station_view = "market"
    state.log("Station market opened.")
    return None


def show_cargo(state: GameState) -> str | None:
    state.map_view = "system"
    state.station_view = "cargo"
    state.log("Cargo hold opened.")
    return None


def show_inventory(state: GameState) -> str | None:
    return show_cargo(state)


def show_hangar(state: GameState) -> str | None:
    if state.player.ship.status != ShipStatus.DOCKED:
        return "Not docked."
    station = _current_station(state)
    if not station or not station.hangar_inventory:
        return "This station has no hangar."
    state.map_view = "system"
    state.station_view = "hangar"
    state.log("Station hangar opened.")
    return None


def show_system_view(state: GameState) -> str | None:
    state.station_view = "system"
    state.log("System view.")
    return None


def _require_hangar(state: GameState):
    if state.player.ship.status != ShipStatus.DOCKED:
        return None, "Must be docked at a hangar."
    station = _current_station(state)
    if not station or not station.hangar_inventory:
        return None, "This station has no hangar."
    return station, None


def buy_ship(state: GameState, hull_ref: str) -> str | None:
    station, error = _require_hangar(state)
    if error:
        return error
    key = hull_ref.casefold().strip()
    ship_type = next(
        (
            hull
            for hull in SHIP_TYPES
            if hull.id == key or hull.name.casefold() == key
        ),
        None,
    )
    if not ship_type or ship_type.id == "venture":
        return f"Unknown purchasable ship: {hull_ref}."
    if station.hangar_inventory.get(ship_type.id, 0) <= 0:
        return f"{ship_type.name} is not in this hangar's stock."
    if state.player.credits < ship_type.price:
        return f"Need {ship_type.price} cr (have {state.player.credits:.0f})."
    serial = state.player.next_ship_serial
    ship_id = f"{ship_type.id}-{serial}"
    location = ShipLocation(
        system_id=state.player.ship.location.system_id,
        kind="docked",
        coords=state.player.ship.location.coords,
        station_id=state.player.ship.location.station_id,
    )
    new_ship = build_ship(ship_type.id, location, ship_id)
    state.player.next_ship_serial += 1
    state.player.fleet.append(new_ship)
    state.player.credits -= ship_type.price
    station.hangar_inventory[ship_type.id] -= 1
    state.station_view = "hangar"
    state.log(f"Purchased {ship_type.name} ({ship_id}) for {ship_type.price} cr.")
    return None


def switch_ship(state: GameState, ship_ref: str) -> str | None:
    station, error = _require_hangar(state)
    if error:
        return error
    key = ship_ref.casefold().strip()
    new_ship = next(
        (
            ship
            for ship in state.player.fleet
            if ship.ship_id.casefold() == key or ship.name.casefold() == key
        ),
        None,
    )
    if not new_ship:
        return f"Ship not found in fleet: {ship_ref}."
    if new_ship is state.player.ship:
        return f"{new_ship.name} is already active."
    current = state.player.ship
    current_system_id = current.location.system_id
    current_station_id = current.location.station_id
    current_coords = current.location.coords
    current.status = ShipStatus.DOCKED
    new_ship.location = ShipLocation(
        system_id=current_system_id,
        kind="docked",
        coords=current_coords,
        station_id=current_station_id,
    )
    new_ship.status = ShipStatus.DOCKED
    state.player.ship = new_ship
    state.player.system_id = current_system_id
    state.station_view = "hangar"
    state.log(f"Switched to {new_ship.name} ({new_ship.ship_id}).")
    return None


def sell_ship(state: GameState, ship_ref: str) -> str | None:
    station, error = _require_hangar(state)
    if error:
        return error
    key = ship_ref.casefold().strip()
    ship = next(
        (
            owned
            for owned in state.player.fleet
            if owned.ship_id.casefold() == key or owned.name.casefold() == key
        ),
        None,
    )
    if not ship:
        return f"Ship not found in fleet: {ship_ref}."
    if len(state.player.fleet) <= 1:
        return "You cannot sell your last ship."
    if ship.cargo:
        return "Empty this ship's cargo before selling it."
    refund = round(ship.purchase_price * 0.6)
    current_system_id = state.player.ship.location.system_id
    current_station_id = state.player.ship.location.station_id
    current_coords = state.player.ship.location.coords
    state.player.fleet.remove(ship)
    if ship is state.player.ship:
        state.player.ship = state.player.fleet[0]
        state.player.ship.location = ShipLocation(
            system_id=current_system_id,
            kind="docked",
            coords=current_coords,
            station_id=current_station_id,
        )
        state.player.ship.status = ShipStatus.DOCKED
        state.player.system_id = current_system_id
    state.player.credits += refund
    station.hangar_inventory[ship.hull_id] = station.hangar_inventory.get(ship.hull_id, 0) + 1
    state.station_view = "hangar"
    state.log(f"Sold {ship.name} ({ship.ship_id}) for {refund} cr.")
    return None


def tick(state: GameState, dt: float) -> None:
    markets = [station for system in state.galaxy.systems.values() for station in system.stations]
    if not markets:
        return
    state.market_restock_timer += dt
    while state.market_restock_timer >= MARKET_RESTOCK_INTERVAL:
        state.market_restock_timer -= MARKET_RESTOCK_INTERVAL
        state.market_restock_count += 1
        rng = random.Random(state.galaxy.seed + state.market_restock_count * 1_000_003)
        for station in markets:
            trade_items = [item_id for item_id in station.prices if not item_id.endswith("_upgrade")]
            if not trade_items:
                trade_items = [item_id for item_id in BASE_PRICES if not item_id.endswith("_upgrade")]
            for _ in range(rng.randint(1, 2)):
                item_id = rng.choice(trade_items)
                station.inventory[item_id] = min(
                    500,
                    station.inventory.get(item_id, 0) + rng.randint(2, 8),
                )


def sell_item(state: GameState, item_ref: str, quantity: int | str) -> str | None:
    if state.player.ship.status != ShipStatus.DOCKED:
        return "Must be docked to sell."
    stack = find_cargo(state.player, item_ref)
    if not stack:
        return f"No cargo matching '{item_ref}'."
    if isinstance(quantity, str):
        if quantity.casefold() != "all":
            return "Quantity must be a positive integer or all."
        quantity = stack.quantity
    if quantity <= 0:
        return "Quantity must be positive."
    if quantity > stack.quantity:
        return f"Only {stack.quantity} units available."
    unit = local_price(state, stack.item_id)
    if unit is None:
        return "Must be docked at a station market to sell."
    total = unit * quantity
    stack.quantity -= quantity
    if stack.quantity <= 0:
        state.player.cargo = [c for c in state.player.cargo if c.quantity > 0]
    state.player.credits += total
    station = _current_station(state)
    if station:
        station.inventory[stack.item_id] = station.inventory.get(stack.item_id, 0) + quantity
    state.log(f"Sold {quantity}x {stack.name} for {total:.0f} cr ({unit:.0f}/ea).")
    state.station_view = "market"
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
    if sum(cargo.quantity for cargo in state.player.cargo) + quantity > state.player.max_cargo:
        return f"Not enough cargo space (hold {state.player.max_cargo} units)."
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
    state.station_view = "market"
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


def _append_table_section(
    out: Text,
    title: str,
    item_ids: list[str],
    quantities: dict[str, int],
    state: GameState,
    width: int,
    row_limit: int,
) -> None:
    name_width = max(8, width - 27)
    out.append(f" {title}\n", style=Style(color="#e8b84a", bold=True))
    out.append(
        f" {'item':<{name_width}}{'qty':>6}{'local':>9}{'global':>9}\n",
        style=Style(color="#aaccee", bold=True),
    )
    if not item_ids:
        out.append(" (empty)\n", style=Style(color="#778899"))
        return
    for item_id in item_ids[:row_limit]:
        name = ascii_only(ITEM_NAMES.get(item_id, item_id.replace("_", " ").title()))[:name_width]
        local = local_price(state, item_id)
        local_text = f"{local:.0f}" if local is not None else "--"
        global_value = global_price(state, item_id)
        out.append(f" {name:<{name_width}}", style=Style(color="#ddeeff"))
        out.append(f"{quantities[item_id]:>6}", style=Style(color="#ffee88"))
        out.append(f"{local_text:>9}", style=Style(color="#88ffaa"))
        out.append(f"{global_value:>9.0f}\n", style=Style(color="#99bbdd"))
    if len(item_ids) > row_limit:
        out.append(f" ... {len(item_ids) - row_limit} more\n", style=Style(color="#778899"))


def render_market_view(state: GameState, width: int, height: int) -> Text:
    station = _current_station(state)
    if not station:
        return Text("No station market available.", style=Style(color="#ff6666"))
    inner_width = max(20, width - 2)
    row_limit = max(1, (height - 5) // 2)
    out = Text()
    out.append(f" {ascii_only(station.name)} MARKET ", style=Style(color="#c9a86a", bold=True))
    out.append(f"| credits {state.player.credits:.0f} cr\n", style=Style(color="#88ccaa"))
    market_items = sorted(item_id for item_id, quantity in station.inventory.items() if quantity > 0)
    _append_table_section(
        out,
        "MARKET INVENTORY",
        market_items,
        station.inventory,
        state,
        inner_width,
        row_limit,
    )
    cargo = {stack.item_id: stack.quantity for stack in state.player.cargo if stack.quantity > 0}
    _append_table_section(
        out,
        "YOUR CARGO",
        sorted(cargo),
        cargo,
        state,
        inner_width,
        row_limit,
    )
    out.append(" buy <item> <qty> | sell <item> <qty|all> | system\n", style=Style(color="#668899"))
    return out


def render_cargo_view(state: GameState, width: int, height: int) -> Text:
    inner_width = max(20, width - 2)
    row_limit = max(1, height - 3)
    out = Text(" CARGO HOLD ", style=Style(color="#c9a86a", bold=True))
    out.append(f"| {sum(stack.quantity for stack in state.player.cargo)} / {state.player.max_cargo} units\n")
    cargo = {stack.item_id: stack.quantity for stack in state.player.cargo if stack.quantity > 0}
    _append_table_section(out, "CARGO", sorted(cargo), cargo, state, inner_width, row_limit)
    return out


def render_hangar_view(state: GameState, width: int, height: int) -> Text:
    station = _current_station(state)
    if not station or not station.hangar_inventory:
        return Text("No hangar available.", style=Style(color="#ff6666"))
    inner_width = max(20, width - 2)
    title = ascii_only(station.name)
    out = Text(f" {title} HANGAR ", style=Style(color="#c9a86a", bold=True))
    out.append(f"| credits {state.player.credits:.0f} cr\n", style=Style(color="#88ccaa"))
    out.append(
        f" {'SHIP':<16}{'CARGO':>7}{'HULL HP':>10}{'SLOTS':>7}{'PRICE':>10}{'STOCK':>8}\n",
        style=Style(color="#aaccee", bold=True),
    )
    available = [
        SHIP_TYPES_BY_ID[hull_id]
        for hull_id, quantity in sorted(station.hangar_inventory.items())
        if quantity > 0 and hull_id in SHIP_TYPES_BY_ID
    ]
    row_limit = max(1, (height - 5) // 2)
    if not available:
        out.append(" (no ships in stock)\n", style=Style(color="#778899"))
    for ship_type in available[:row_limit]:
        name = ascii_only(ship_type.name)[:16]
        row = (
            f" {name:<16}{ship_type.cargo_capacity:>7}"
            f"{ship_type.component_health * 4:>10.0f}{ship_type.component_slots:>7}"
            f"{ship_type.price:>10}"
            f"{station.hangar_inventory[ship_type.id]:>8}"
        )
        out.append(row[:inner_width] + "\n", style=Style(color="#ddeeff"))

    out.append(" FLEET\n", style=Style(color="#e8b84a", bold=True))
    for ship in state.player.fleet[:row_limit]:
        current = "*" if ship is state.player.ship else " "
        cargo_quantity = sum(stack.quantity for stack in ship.cargo)
        max_health = sum(component.max_health for component in ship.components)
        health = sum(component.health for component in ship.components)
        row = (
            f"{current} {ascii_only(ship.ship_id):<14}{ascii_only(ship.name):<14} "
            f"cargo {cargo_quantity:>3}/{ship.cargo_capacity:<3} hull {health:.0f}/{max_health:.0f}"
        )
        out.append(row[:inner_width] + "\n", style=Style(color="#88ffaa" if current == "*" else "#ddeeff"))
    if len(state.player.fleet) > row_limit:
        out.append(f" ... {len(state.player.fleet) - row_limit} more ships\n", style=Style(color="#778899"))
    out.append(
        " buy ship <hull> | switch ship <id> | sell ship <id> | hangar\n",
        style=Style(color="#668899"),
    )
    return out


def render_inventory_view(state: GameState, width: int, height: int) -> Text:
    """Compatibility alias for the standalone cargo inventory view."""
    return render_cargo_view(state, width, height)
