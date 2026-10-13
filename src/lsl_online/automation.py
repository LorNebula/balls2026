"""Sandboxed trade scripts: cron every 60s, courier shipments."""

from __future__ import annotations

from dataclasses import dataclass

from lsl_online.market import (
    BASE_PRICES,
    find_cargo,
    complete_station_sale,
    price_map_for_galaxy,
    primary_station,
    sell_at_station,
)
from lsl_online.models import GameState, PendingShipment
from lsl_online.galaxy import find_system_by_name

TRADE_CRON_INTERVAL = 60.0
COURIER_SPEED = 0.8

TUTORIAL_TRADE_TEMPLATE = '''\
# Trade bot: def trade(ctx) reads ctx.cargo, ctx.prices, ctx.here, ctx.credits.
# script run = once now. script enable = auto every 60s. Remote sell: add "system": "Name".
SELL_QTY = 0  # CHANGE ME: set to 10 to sell tutorial cargo

def trade(ctx):
    orders = []
    for stack in ctx.cargo:
        if stack["item_id"] == "flagged_cargo" and SELL_QTY > 0:
            orders.append({
                "action": "sell",
                "item": stack["item_id"],
                "qty": min(SELL_QTY, stack["qty"]),
            })
    return orders
'''

_SAFE_BUILTINS = {
    "True": True,
    "False": False,
    "None": None,
    "len": len,
    "min": min,
    "max": max,
    "sum": sum,
    "range": range,
    "int": int,
    "float": float,
    "str": str,
    "list": list,
    "dict": dict,
    "abs": abs,
    "round": round,
}


@dataclass
class TradeContext:
    cargo: list[dict]
    prices: dict[str, dict[str, float]]
    here: str
    credits: float


def build_trade_context(state: GameState) -> TradeContext:
    sys = state.galaxy.get_system(state.player.ship.location.system_id)
    here = sys.name if sys else "?"
    cargo = [
        {"item_id": s.item_id, "name": s.name, "qty": s.quantity}
        for s in state.player.cargo
        if s.quantity > 0
    ]
    return TradeContext(
        cargo=cargo,
        prices=price_map_for_galaxy(state),
        here=here,
        credits=state.player.credits,
    )


def run_trade_script(state: GameState, source: str | None = None) -> list[dict] | str:
    code = source if source is not None else state.trade_script_source
    if not code.strip():
        return "Trade script is empty."
    namespace: dict = {"__builtins__": _SAFE_BUILTINS}
    try:
        exec(code, namespace, namespace)
    except Exception as exc:
        return f"ERR: trade script: {exc}"
    trade_fn = namespace.get("trade")
    if not callable(trade_fn):
        return "Trade script must define: def trade(ctx): ..."
    ctx = build_trade_context(state)
    try:
        result = trade_fn(ctx)
    except Exception as exc:
        return f"ERR: trade script: {exc}"
    if result is None:
        return []
    if not isinstance(result, list):
        return "trade(ctx) must return a list of orders."
    return result


def _system_distance(state: GameState, dest_system_id: str) -> float:
    origin = state.galaxy.get_system(state.player.ship.location.system_id)
    dest = state.galaxy.get_system(dest_system_id)
    if not origin or not dest:
        return 100.0
    return origin.position.distance_to(dest.position)


def _courier_fee(state: GameState, item_id: str, qty: int, dest_system_id: str) -> float:
    base = BASE_PRICES.get(item_id, 100.0)
    dist = _system_distance(state, dest_system_id)
    hop_factor = max(1.0, dist / 50.0)
    return max(10.0, round(qty * base * 0.05 * hop_factor, 0))


def _courier_eta(state: GameState, dest_system_id: str) -> float:
    dist = _system_distance(state, dest_system_id)
    return max(5.0, dist / COURIER_SPEED)


def _resolve_dest_system(state: GameState, system_name: str):
    return find_system_by_name(state.galaxy, system_name)


def _normalize_order(raw: object) -> dict | str:
    if not isinstance(raw, dict):
        return "Each order must be a dict."
    action = str(raw.get("action", "sell")).lower()
    if action in ("ship", "sell"):
        action = "sell"
    else:
        return f"Unknown action: {action}"
    item = raw.get("item")
    if not item:
        return "Order missing 'item'."
    qty = raw.get("qty", raw.get("quantity"))
    try:
        qty_i = int(qty)
    except (TypeError, ValueError):
        return "Order 'qty' must be an integer."
    if qty_i <= 0:
        return "Order qty must be positive."
    system = raw.get("system")
    return {"action": action, "item": str(item), "qty": qty_i, "system": system}


def apply_orders(state: GameState, orders: list[dict]) -> None:
    ctx = build_trade_context(state)
    for raw in orders:
        norm = _normalize_order(raw)
        if isinstance(norm, str):
            state.log(f"Trade order skipped: {norm}")
            continue
        item_id = norm["item"]
        qty = norm["qty"]
        dest_name = norm.get("system")
        stack = find_cargo(state.player, item_id)
        if not stack or stack.quantity < qty:
            have = stack.quantity if stack else 0
            state.log(f"Trade order skipped: only {have} of {item_id}.")
            continue

        sell_here = (
            not dest_name
            or str(dest_name).casefold() == ctx.here.casefold()
        )
        if sell_here:
            sys = state.galaxy.get_system(state.player.ship.location.system_id)
            station = primary_station(sys)
            if not station:
                state.log("Trade order skipped: no station in current system.")
                continue
            err = sell_at_station(state, station, stack.item_id, qty)
            if err:
                state.log(f"Trade order skipped: {err}")
            continue

        dest_sys = _resolve_dest_system(state, str(dest_name))
        if not dest_sys:
            state.log(f"Trade order skipped: unknown system {dest_name!r}.")
            continue
        station = primary_station(dest_sys)
        if not station:
            state.log(f"Trade order skipped: no station in {dest_sys.name}.")
            continue
        fee = _courier_fee(state, stack.item_id, qty, dest_sys.id)
        if state.player.credits < fee:
            state.log(f"Trade order skipped: courier fee {fee:.0f} cr (have {state.player.credits:.0f}).")
            continue
        stack.quantity -= qty
        if stack.quantity <= 0:
            state.player.cargo = [c for c in state.player.cargo if c.quantity > 0]
        state.player.credits -= fee
        eta = _courier_eta(state, dest_sys.id)
        state.pending_shipments.append(
            PendingShipment(
                item_id=stack.item_id,
                item_name=stack.name,
                quantity=qty,
                dest_system_id=dest_sys.id,
                dest_station_id=station.id,
                eta_seconds=eta,
                fee_paid=fee,
            )
        )
        state.log(
            f"Courier: {qty}x {stack.name} -> {dest_sys.name} "
            f"(ETA {eta:.0f}s, fee {fee:.0f} cr)."
        )


def execute_trade_script(state: GameState, source: str | None = None) -> str | None:
    result = run_trade_script(state, source)
    if isinstance(result, str):
        state.log(result)
        return result if result.startswith("ERR") else None
    if not result:
        state.log("Trade script returned no orders.")
        return None
    apply_orders(state, result)
    return None


def _tick_shipments(state: GameState, dt: float) -> None:
    remaining: list[PendingShipment] = []
    for ship in state.pending_shipments:
        ship.eta_seconds -= dt
        if ship.eta_seconds > 0:
            remaining.append(ship)
            continue
        dest_sys = state.galaxy.get_system(ship.dest_system_id)
        if not dest_sys:
            state.log(f"Courier lost: unknown system for {ship.item_name}.")
            continue
        station = next(
            (st for st in dest_sys.stations if st.id == ship.dest_station_id),
            primary_station(dest_sys),
        )
        if not station:
            state.log(f"Courier lost: no station at {dest_sys.name}.")
            continue
        complete_station_sale(
            state,
            station,
            ship.item_id,
            ship.item_name,
            ship.quantity,
        )
    state.pending_shipments = remaining


def tick(state: GameState, dt: float) -> None:
    if state.game_over:
        return
    _tick_shipments(state, dt)
    if not state.trade_script_enabled or not state.trade_script_source.strip():
        return
    state.trade_script_timer += dt
    if state.trade_script_timer < TRADE_CRON_INTERVAL:
        return
    state.trade_script_timer = 0.0
    state.log("Trade cron running...")
    execute_trade_script(state)


def script_status_lines(state: GameState) -> list[str]:
    lines = [
        f"enabled: {state.trade_script_enabled}",
        f"next cron: {max(0.0, TRADE_CRON_INTERVAL - state.trade_script_timer):.0f}s",
        f"pending couriers: {len(state.pending_shipments)}",
    ]
    for ship in state.pending_shipments:
        lines.append(
            f"  {ship.quantity}x {ship.item_name} -> ETA {ship.eta_seconds:.0f}s"
        )
    return lines
