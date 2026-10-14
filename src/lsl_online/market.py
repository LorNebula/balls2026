"""Station market: inventory view, sell, component upgrades."""

from __future__ import annotations

import random

from rich.style import Style
from rich.text import Text

from lsl_online.ascii_ui import ascii_only
from lsl_online.materials import MATERIALS, base_prices_map
from lsl_online.models import CargoStack, GameState, ShipLocation, ShipStatus
from lsl_online.ship import find_component
from lsl_online.shipyard import SHIP_TYPES, SHIP_TYPES_BY_ID, build_ship
from lsl_online.models import CargoStack, GameState, ShipStatus, TutorialStep
from lsl_online.ship import find_component, kind_integrity

TUTORIAL_CARGO_ID = "flagged_cargo"
TUTORIAL_CARGO_NAME = "Flagged Military Cargo"

# item_id -> base credits per unit at a typical station
BASE_PRICES: dict[str, float] = {
    TUTORIAL_CARGO_ID: 1200.0,
    "scrap": 45.0,
    "pirate_salvage": 110.0,
    "ore": 80.0,
    "ice": 60.0,
    "reactor_upgrade": 2500.0,
    "weapons_upgrade": 2500.0,
    **base_prices_map(),
}

ITEM_NAMES: dict[str, str] = {
    TUTORIAL_CARGO_ID: TUTORIAL_CARGO_NAME,
    "scrap": "Scrap",
    "pirate_salvage": "Pirate salvage",
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
WEAPON_UPGRADE_DAMAGE = 10.0
REPAIR_CREDITS_PER_HP = 4.0
MARKET_RESTOCK_INTERVAL = 60.0
TUTORIAL_MIN_STATION_CREDITS = 20_000.0
BID_SPREAD = 0.72
SUPPLY_MIN = 0.35
SUPPLY_MAX = 2.0
ROW_EVEN = Style(color="#ddeeff", bgcolor="#0a1520")
ROW_ODD = Style(color="#ddeeff", bgcolor="#142030")


def starter_cargo() -> list[CargoStack]:
    return [
        CargoStack(TUTORIAL_CARGO_ID, TUTORIAL_CARGO_NAME, 10),
    ]


def _price_modifier(station, item_id: str) -> float:
    return station.price_modifiers.get(item_id, 1.0)


def ask_price(station, item_id: str) -> float:
    base = station.prices.get(item_id, BASE_PRICES.get(item_id, 100.0))
    stock = station.inventory.get(item_id, 0)
    supply_factor = max(SUPPLY_MIN, min(SUPPLY_MAX, 1.0 + (20 - stock) / 35.0))
    return round(base * supply_factor * _price_modifier(station, item_id), 0)


def bid_price(station, item_id: str) -> float:
    return round(ask_price(station, item_id) * BID_SPREAD, 0)


def _station_price(station, item_id: str) -> float:
    return ask_price(station, item_id)


def local_ask(state: GameState, item_id: str) -> float | None:
    station = _current_station(state)
    return ask_price(station, item_id) if station else None


def local_bid(state: GameState, item_id: str) -> float | None:
    station = _current_station(state)
    return bid_price(station, item_id) if station else None


def local_price(state: GameState, item_id: str) -> float | None:
    return local_ask(state, item_id)


def global_price(state: GameState, item_id: str) -> float:
    stations = [station for system in state.galaxy.systems.values() for station in system.stations]
    if not stations:
        return round(BASE_PRICES.get(item_id, 100.0), 0)
    return round(sum(bid_price(station, item_id) for station in stations) / len(stations), 0)


def _apply_station_payout(station, total: float) -> str | None:
    if station.credits < total:
        return (
            f"Station treasury: need {total:.0f} cr, has {station.credits:.0f} cr "
            f"(max {station.credits_max:.0f})."
        )
    station.credits -= total
    return None


def price_map_for_galaxy(state: GameState) -> dict[str, dict[str, float]]:
    """System name -> item_id -> unit price at that system's first station."""
    out: dict[str, dict[str, float]] = {}
    for system in state.galaxy.systems.values():
        if not system.stations:
            continue
        station = system.stations[0]
        prices: dict[str, float] = {}
        item_ids = set(station.prices) | set(station.inventory) | set(BASE_PRICES)
        for item_id in item_ids:
            if item_id.endswith("_upgrade"):
                continue
            prices[item_id] = _station_price(station, item_id)
        out[system.name] = prices
    return out


def _mark_tutorial_sell(state: GameState, item_id: str) -> None:
    if state.tutorial_step == TutorialStep.SELL and item_id == TUTORIAL_CARGO_ID:
        state.tutorial_sell_done = True


def complete_station_sale(
    state: GameState,
    station,
    item_id: str,
    item_name: str,
    quantity: int,
) -> str | None:
    """Credit player for a sale without touching cargo (courier delivery)."""
    unit = bid_price(station, item_id)
    total = unit * quantity
    err = _apply_station_payout(station, total)
    if err:
        state.log(f"Courier sale failed at {station.name}: {err}")
        return err
    state.player.credits += total
    station.inventory[item_id] = station.inventory.get(item_id, 0) + quantity
    _mark_tutorial_sell(state, item_id)
    state.log(f"Courier sold {quantity}x {item_name} for {total:.0f} cr ({unit:.0f}/ea).")
    from lsl_online.audio import request_sound

    request_sound(state, "sell")
    return None


def sell_at_station(
    state: GameState,
    station,
    item_id: str,
    quantity: int,
) -> str | None:
    """Remove cargo from hold and sell at the given station."""
    stack = find_cargo(state.player, item_id)
    if not stack:
        return f"No cargo matching '{item_id}'."
    if quantity <= 0:
        return "Quantity must be positive."
    if quantity > stack.quantity:
        return f"Only {stack.quantity} units available."
    unit = bid_price(station, stack.item_id)
    total = unit * quantity
    err = _apply_station_payout(station, total)
    if err:
        return err
    stack.quantity -= quantity
    if stack.quantity <= 0:
        state.player.cargo = [c for c in state.player.cargo if c.quantity > 0]
    state.player.credits += total
    station.inventory[stack.item_id] = station.inventory.get(stack.item_id, 0) + quantity
    state.log(f"Sold {quantity}x {stack.name} for {total:.0f} cr ({unit:.0f}/ea).")
    _mark_tutorial_sell(state, stack.item_id)
    from lsl_online.quests import note_market_sell

    note_market_sell(state, stack.item_id, quantity)
    from lsl_online.audio import request_sound

    request_sound(state, "sell")
    return None


def primary_station(system):
    return system.stations[0] if system and system.stations else None


def ensure_station_wallets(state: GameState) -> None:
    """Backfill treasury fields for stations loaded from older galaxy JSON."""
    rng = random.Random(state.galaxy.seed)
    for system in state.galaxy.systems.values():
        for station in system.stations:
            if station.credits_max > 0 and station.income_per_tick > 0:
                station.credits = min(station.credits, station.credits_max)
                continue
            station_rng = random.Random(state.galaxy.seed ^ hash(station.id) & 0xFFFFFFFF)
            station.credits_max = float(station_rng.randint(8_000, 25_000))
            station.credits = station.credits_max * station_rng.uniform(0.5, 0.85)
            station.income_per_tick = station.credits_max * station_rng.uniform(0.012, 0.028)
            for item_id in BASE_PRICES:
                if item_id.endswith("_upgrade"):
                    continue
                station.price_modifiers[item_id] = station_rng.uniform(0.55, 1.65)


def ensure_tutorial_station_credits(state: GameState) -> None:
    """Tutorial sell (10x flagged cargo) needs a station treasury that can pay bid prices."""
    floor = TUTORIAL_MIN_STATION_CREDITS
    for system in state.galaxy.systems.values():
        for station in system.stations:
            station.credits_max = max(station.credits_max, floor)
            station.credits = max(station.credits, floor)


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
            station.credits = min(
                station.credits_max,
                station.credits + station.income_per_tick * rng.uniform(0.9, 1.1),
            )
            trade_items = [item_id for item_id in station.prices if not item_id.endswith("_upgrade")]
            if not trade_items:
                trade_items = [item_id for item_id in BASE_PRICES if not item_id.endswith("_upgrade")]
            for _ in range(rng.randint(1, 2)):
                item_id = rng.choice(trade_items)
                station.inventory[item_id] = min(
                    500,
                    station.inventory.get(item_id, 0) + rng.randint(2, 8),
                )
            for item_id in trade_items:
                drift = rng.uniform(0.78, 1.22)
                station.price_modifiers[item_id] = max(
                    0.4,
                    min(3.0, station.price_modifiers.get(item_id, 1.0) * drift),
                )


def sell_inventory(state: GameState) -> str | None:
    if state.player.ship.status != ShipStatus.DOCKED:
        return "Must be docked to sell."
    station = _current_station(state)
    if not station:
        return "Must be docked at a station market to sell."
    stacks = [s for s in state.player.cargo if s.quantity > 0]
    if not stacks:
        return "Cargo hold is empty."
    credits_before = state.player.credits
    sold_lines = 0
    for stack in list(stacks):
        qty = stack.quantity
        if qty <= 0:
            continue
        err = sell_at_station(state, station, stack.item_id, qty)
        if err:
            return err
        sold_lines += 1
    gained = state.player.credits - credits_before
    state.log(f"Sold entire cargo ({sold_lines} line(s)) for {gained:.0f} cr total.")
    state.station_view = "market"
    return None


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
    station = _current_station(state)
    if not station:
        return "Must be docked at a station market to sell."
    err = sell_at_station(state, station, stack.item_id, quantity)
    if err is None:
        state.station_view = "market"
    return err


def max_affordable_quantity(
    state: GameState, station, item_id: str, stock: int, space: int
) -> int:
    if stock <= 0 or space <= 0:
        return 0
    unit = ask_price(station, item_id)
    if unit <= 0:
        return min(stock, space)
    by_credits = int(state.player.credits // unit)
    return max(0, min(stock, space, by_credits))


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
    used = sum(cargo.quantity for cargo in state.player.cargo)
    space = state.player.max_cargo - used
    if quantity > space:
        return f"Not enough cargo space (hold {state.player.max_cargo} units)."
    unit = ask_price(station, item_id)
    total = unit * quantity
    if state.player.credits < total:
        return f"Need {total:.0f} cr (have {state.player.credits:.0f})."
    station.inventory[item_id] -= quantity
    state.player.credits -= total
    stack = next((cargo for cargo in state.player.cargo if cargo.item_id == item_id), None)
    if stack:
        prev_qty = stack.quantity
        stack.quantity += quantity
        stack.avg_unit_cost = (
            (stack.avg_unit_cost * prev_qty + unit * quantity) / stack.quantity
            if stack.quantity
            else unit
        )
    else:
        from lsl_online.models import CargoStack

        state.player.cargo.append(
            CargoStack(item_id, ITEM_NAMES[item_id], quantity, avg_unit_cost=unit)
        )
    state.log(f"Bought {quantity}x {ITEM_NAMES[item_id]} for {total:.0f} cr.")
    from lsl_online.quests import note_market_buy

    note_market_buy(state, item_id, quantity)
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
    ship = state.player.ship
    if key == "weapons":
        ship.weapon_damage_bonus += WEAPON_UPGRADE_DAMAGE
        state.log(
            f"Upgraded weapons: +{WEAPON_UPGRADE_DAMAGE:.0f} laser damage ({cost:.0f} cr)."
        )
    else:
        comp.max_health += UPGRADE_HP_BONUS
        comp.health = comp.max_health
        state.log(f"Upgraded {comp.kind}: +{UPGRADE_HP_BONUS:.0f} max hp ({cost:.0f} cr).")
    if key == "reactor":
        ship.max_power += 15.0
        ship.power = min(ship.max_power, ship.power + 15.0)
    if state.tutorial_step == TutorialStep.UPGRADE:
        if key == "reactor":
            state.tutorial_upgraded_reactor = True
        elif key == "weapons":
            state.tutorial_upgraded_weapons = True
    return None


def repair_ship(state: GameState) -> str | None:
    if state.player.ship.status != ShipStatus.DOCKED:
        return "Must be docked to repair."
    if not _current_station(state):
        return "No repair bay at this station."
    ship = state.player.ship
    missing = sum(max(0.0, c.max_health - c.health) for c in ship.components)
    if missing <= 0:
        return "Hull components already at full integrity."
    cost = round(missing * REPAIR_CREDITS_PER_HP, 0)
    if state.player.credits < cost:
        return f"Need {cost:.0f} cr to repair ({missing:.0f} hp missing)."
    state.player.credits -= cost
    for comp in ship.components:
        comp.health = comp.max_health
    if kind_integrity(ship.components, "shields") > 0:
        ship.shield = ship.max_shield
    state.log(f"Repaired {missing:.0f} hull hp for {cost:.0f} cr. Shields topped off.")
    state.station_view = "hangar"
    return None


def _cargo_profit_suffix(state: GameState, item_id: str) -> str:
    stack = find_cargo(state.player, item_id)
    station = _current_station(state)
    if not stack or stack.avg_unit_cost <= 0 or not station:
        return ""
    bid = bid_price(station, item_id)
    mult = bid / stack.avg_unit_cost if stack.avg_unit_cost > 0 else 0.0
    if mult <= 0:
        return ""
    return f" x{mult:.1f}"


def _append_table_section(
    out: Text,
    title: str,
    item_ids: list[str],
    quantities: dict[str, int],
    state: GameState,
    width: int,
    row_limit: int,
    *,
    cargo_rows: bool = False,
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
    for row_index, item_id in enumerate(item_ids[:row_limit]):
        base_name = ascii_only(ITEM_NAMES.get(item_id, item_id.replace("_", " ").title()))
        if cargo_rows:
            base_name = (base_name + _cargo_profit_suffix(state, item_id))[:name_width]
        name = base_name[:name_width]
        if cargo_rows:
            local = local_bid(state, item_id)
        else:
            local = local_ask(state, item_id)
        local_text = f"{local:.0f}" if local is not None else "--"
        global_value = global_price(state, item_id)
        row_style = ROW_EVEN if row_index % 2 == 0 else ROW_ODD
        out.append(f" {name:<{name_width}}", style=row_style)
        out.append(f"{quantities[item_id]:>6}", style=Style(color="#ffee88", bgcolor=row_style.bgcolor))
        out.append(f"{local_text:>9}", style=Style(color="#88ffaa", bgcolor=row_style.bgcolor))
        out.append(f"{global_value:>9.0f}\n", style=Style(color="#99bbdd", bgcolor=row_style.bgcolor))
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
    out.append(
        f"| you {state.player.credits:.0f} cr | treasury {station.credits:.0f}/{station.credits_max:.0f}\n",
        style=Style(color="#88ccaa"),
    )
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
        cargo_rows=True,
    )
    out.append(
        " buy <item> <qty|all> | sell <item> <qty|all> | sell inventory | repair | system | hangar\n",
        style=Style(color="#668899"),
    )
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
        " buy ship <hull> | switch ship <id> | sell ship <id> | market\n",
        style=Style(color="#668899"),
    )
    return out


def render_inventory_view(state: GameState, width: int, height: int) -> Text:
    """Compatibility alias for the standalone cargo inventory view."""
    return render_cargo_view(state, width, height)
