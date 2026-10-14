"""Quest definitions, procedural board, and progress hooks."""

from __future__ import annotations

import random
from collections import deque

from lsl_online.ascii_ui import ascii_only
from lsl_online.market import ITEM_NAMES
from lsl_online.materials import MATERIALS
from lsl_online.models import GameState, Quest, QuestStatus, TutorialStep

from lsl_online import mining

MAX_QUEST_TRAVEL_HOPS = 5

QUEST_REWARDS: dict[str, float] = {
    "kill": 1800.0,
    "mine": 1400.0,
    "buy": 900.0,
    "sell": 1100.0,
    "generic": 600.0,
}


def _legacy_quests() -> list[Quest]:
    return [
        Quest(
            id="q_scout",
            title="Scout the Rim",
            summary="Jump to a neighboring system and report status.",
            kind="scout",
        ),
        Quest(
            id="q_station",
            title="Station Approach",
            summary="Dock at any station.",
            kind="dock",
        ),
        Quest(
            id="q_survive",
            title="Hold the Line",
            summary="Destroy one hostile ship.",
            kind="kill",
            target_count=1,
        ),
    ]


def _pick_station_systems(state: GameState, rng: random.Random, count: int) -> list:
    systems = [s for s in state.galaxy.systems.values() if s.stations]
    rng.shuffle(systems)
    return systems[:count]


def generate_quest_board(state: GameState) -> list[Quest]:
    rng = random.Random(state.galaxy.seed ^ 0x71E57)
    quests = _legacy_quests()
    systems = _pick_station_systems(state, rng, 4)
    if not systems:
        return quests

    bounty_sys = systems[0]
    kill_qty = rng.randint(2, 5)
    bounty_name = ascii_only(bounty_sys.name)
    quests.append(
        Quest(
            id="q_bounty_contract",
            title=f"Bounty: {kill_qty} hostiles @ {bounty_name}",
            summary=f"Destroy {kill_qty} hostile ships in {bounty_name}.",
            kind="kill",
            target_system_id=bounty_sys.id,
            target_count=kill_qty,
        )
    )

    mine_sys = systems[1 % len(systems)]
    mat = _pick_mine_material_for_system(state, mine_sys.id, rng)
    mine_qty = rng.randint(6, 12)
    quests.append(
        Quest(
            id="q_mine_contract",
            title=f"Extract {ascii_only(mat.name)}",
            summary=(
                f"Mine {mine_qty} units of {ascii_only(mat.name)} "
                f"in {ascii_only(mine_sys.name)}."
            ),
            kind="mine",
            target_system_id=mine_sys.id,
            target_material_id=mat.id,
            target_count=mine_qty,
        )
    )

    trade_sys = systems[2 % len(systems)]
    buy_pick = _pick_buy_item_for_system(trade_sys, rng)
    if buy_pick:
        buy_item, buy_qty = buy_pick
        buy_name = ITEM_NAMES.get(buy_item, buy_item)
        quests.append(
            Quest(
                id="q_buy_contract",
                title=f"Procurement run",
                summary=(
                    f"Buy {buy_qty}x {ascii_only(buy_name)} at a station in "
                    f"{ascii_only(trade_sys.name)}."
                ),
                kind="buy",
                target_system_id=trade_sys.id,
                target_item_id=buy_item,
                target_count=buy_qty,
            )
        )

    sell_sys = systems[3 % len(systems)]
    sell_pick = _pick_sell_item_for_system(sell_sys, rng)
    if sell_pick:
        sell_item, sell_qty = sell_pick
        sell_name = ITEM_NAMES.get(sell_item, sell_item)
        quests.append(
            Quest(
                id="q_sell_contract",
                title=f"Market offload",
                summary=(
                    f"Sell {sell_qty}x {ascii_only(sell_name)} at a station in "
                    f"{ascii_only(sell_sys.name)}."
                ),
                kind="sell",
                target_system_id=sell_sys.id,
                target_item_id=sell_item,
                target_count=sell_qty,
            )
        )

    return quests


def _quest_rng(state: GameState, *parts: object) -> random.Random:
    seed = state.galaxy.seed ^ hash(parts) & 0xFFFFFFFF
    return random.Random(seed)


def _new_quest_id(kind: str, tier: int, rng: random.Random) -> str:
    return f"q_{kind}_t{tier}_{rng.randint(1000, 9999)}"


def _reachable_systems(
    state: GameState,
    max_hops: int = MAX_QUEST_TRAVEL_HOPS,
    *,
    require_station: bool = True,
) -> list:
    start_id = state.player.ship.location.system_id
    dist: dict[str, int] = {start_id: 0}
    queue: deque[str] = deque([start_id])
    while queue:
        current = queue.popleft()
        hop = dist[current]
        if hop >= max_hops:
            continue
        sys = state.galaxy.get_system(current)
        if not sys:
            continue
        for neighbor_id in sys.neighbors:
            if neighbor_id in dist:
                continue
            dist[neighbor_id] = hop + 1
            queue.append(neighbor_id)
    systems = []
    for system_id, hop in dist.items():
        if hop == 0:
            continue
        system = state.galaxy.get_system(system_id)
        if not system:
            continue
        if require_station and not system.stations:
            continue
        systems.append(system)
    if not systems and require_station:
        return _reachable_systems(state, max_hops, require_station=False)
    return systems


def _pick_quest_system(state: GameState, rng: random.Random):
    pool = _reachable_systems(state, MAX_QUEST_TRAVEL_HOPS)
    if pool:
        return rng.choice(pool)
    current = state.galaxy.get_system(state.player.ship.location.system_id)
    if current and current.stations:
        return current
    with_stations = [s for s in state.galaxy.systems.values() if s.stations]
    return rng.choice(with_stations) if with_stations else current


def _next_count(previous: Quest | None, kind: str, fallback: int) -> int:
    if previous and previous.kind == kind:
        return previous.target_count + 1
    return fallback


def _station_trade_items(station) -> list[str]:
    return [
        item_id
        for item_id, qty in station.inventory.items()
        if qty > 0 and not item_id.endswith("_upgrade") and item_id != "flagged_cargo"
    ]


def _station_market_items(station) -> list[str]:
    keys = set(station.inventory) | set(station.prices)
    return [
        item_id
        for item_id in keys
        if not item_id.endswith("_upgrade") and item_id != "flagged_cargo"
    ]


def _pick_buy_item_for_system(system, rng: random.Random) -> tuple[str, int] | None:
    if not system.stations:
        return None
    station = system.stations[0]
    trade_items = _station_trade_items(station)
    if not trade_items:
        return None
    buy_item = rng.choice(trade_items)
    buy_qty = rng.randint(3, min(8, station.inventory.get(buy_item, 8)))
    buy_qty = max(3, buy_qty)
    return buy_item, buy_qty


def _pick_sell_item_for_system(system, rng: random.Random) -> tuple[str, int] | None:
    if not system.stations:
        return None
    station = system.stations[0]
    sell_items = _station_market_items(station)
    if not sell_items:
        return None
    sell_item = rng.choice(sell_items)
    sell_qty = rng.randint(4, 10)
    return sell_item, sell_qty


def generate_followup_quest(
    state: GameState,
    kind: str,
    tier: int,
    previous: Quest | None = None,
) -> Quest | None:
    """New contract of the same kind, scaled by tier (higher = harder)."""
    rng = _quest_rng(state, "followup", kind, tier, len(state.quests))

    if kind == "kill":
        bounty_sys = _pick_quest_system(state, rng)
        if not bounty_sys:
            return None
        kill_qty = _next_count(previous, "kill", 2)
        bounty_name = ascii_only(bounty_sys.name)
        return Quest(
            id=_new_quest_id("kill", tier, rng),
            title=f"Bounty II-{tier}: {kill_qty} hostiles @ {bounty_name}",
            summary=f"Destroy {kill_qty} hostile ships in {bounty_name}.",
            kind="kill",
            target_system_id=bounty_sys.id,
            target_count=kill_qty,
            tier=tier,
        )

    if kind == "mine":
        mine_sys = _pick_quest_system(state, rng)
        if not mine_sys:
            return None
        mat = _pick_mine_material_for_system(state, mine_sys.id, rng, tier=tier)
        mine_qty = _next_count(previous, "mine", 10)
        return Quest(
            id=_new_quest_id("mine", tier, rng),
            title=f"Extract {ascii_only(mat.name)} (tier {tier})",
            summary=(
                f"Mine {mine_qty} units of {ascii_only(mat.name)} "
                f"in {ascii_only(mine_sys.name)}."
            ),
            kind="mine",
            target_system_id=mine_sys.id,
            target_material_id=mat.id,
            target_count=mine_qty,
            tier=tier,
        )

    if kind == "buy":
        trade_sys = _pick_quest_system(state, rng)
        if not trade_sys:
            return None
        buy_pick = _pick_buy_item_for_system(trade_sys, rng)
        if not buy_pick:
            return None
        buy_item, _ = buy_pick
        buy_qty = _next_count(previous, "buy", 5)
        buy_name = ITEM_NAMES.get(buy_item, buy_item)
        return Quest(
            id=_new_quest_id("buy", tier, rng),
            title=f"Procurement tier {tier}",
            summary=(
                f"Buy {buy_qty}x {ascii_only(buy_name)} at a station in "
                f"{ascii_only(trade_sys.name)}."
            ),
            kind="buy",
            target_system_id=trade_sys.id,
            target_item_id=buy_item,
            target_count=buy_qty,
            tier=tier,
        )

    if kind == "sell":
        sell_sys = _pick_quest_system(state, rng)
        if not sell_sys:
            return None
        sell_pick = _pick_sell_item_for_system(sell_sys, rng)
        if not sell_pick:
            return None
        sell_item, _ = sell_pick
        sell_qty = _next_count(previous, "sell", 6)
        sell_name = ITEM_NAMES.get(sell_item, sell_item)
        return Quest(
            id=_new_quest_id("sell", tier, rng),
            title=f"Market offload tier {tier}",
            summary=(
                f"Sell {sell_qty}x {ascii_only(sell_name)} at a station in "
                f"{ascii_only(sell_sys.name)}."
            ),
            kind="sell",
            target_system_id=sell_sys.id,
            target_item_id=sell_item,
            target_count=sell_qty,
            tier=tier,
        )

    if kind == "scout":
        jumps = _next_count(previous, "scout", 2)
        jumps = min(jumps, 6)
        return Quest(
            id=_new_quest_id("scout", tier, rng),
            title=f"Scout patrol tier {tier}",
            summary=f"Complete {jumps} jump(s) to neighboring systems.",
            kind="scout",
            target_count=jumps,
            tier=tier,
        )

    if kind == "dock":
        dock_sys = _pick_quest_system(state, rng)
        if not dock_sys:
            return None
        return Quest(
            id=_new_quest_id("dock", tier, rng),
            title=f"Station call: {ascii_only(dock_sys.name)}",
            summary=f"Dock at any station in {ascii_only(dock_sys.name)}.",
            kind="dock",
            target_system_id=dock_sys.id,
            tier=tier,
        )

    return None


def _replace_completed_quest(state: GameState, completed: Quest) -> None:
    kind = completed.kind
    tier = state.quest_kind_tiers.get(kind, 1) + 1
    state.quest_kind_tiers[kind] = tier
    replacement = generate_followup_quest(state, kind, tier, completed)
    if not replacement:
        return
    for index, quest in enumerate(state.quests):
        if quest.id == completed.id:
            state.quests[index] = replacement
            break
    state.log(f"New contract available in quests: {replacement.id} ({kind}, tier {tier}): {replacement.title}")
    


def _active_quests(state: GameState) -> list[Quest]:
    return [q for q in state.quests if q.status == QuestStatus.ACTIVE]


def _pick_mine_material_for_system(
    state: GameState,
    system_id: str,
    rng: random.Random,
    *,
    tier: int = 0,
):
    pool = mining.system_materials(state, system_id)
    if not pool:
        return MATERIALS[0]
    if tier > 0:
        weights = [max(1, m.rarity * (1 + tier * 0.15)) for m in pool]
        return rng.choices(pool, weights=weights, k=1)[0]
    return rng.choice(pool)


def active_buy_quantities_needed(state: GameState, system_id: str) -> dict[str, int]:
    """Item id -> minimum stock needed for active buy quests in this system."""
    needed: dict[str, int] = {}
    for quest in _active_quests(state):
        if quest.kind != "buy":
            continue
        if quest.target_system_id != system_id:
            continue
        if not quest.target_item_id:
            continue
        remaining = max(0, quest.target_count - quest.progress)
        if remaining <= 0:
            continue
        needed[quest.target_item_id] = max(
            needed.get(quest.target_item_id, 0),
            remaining + 5,
        )
    return needed


def active_mine_materials_needed(state: GameState, system_id: str) -> set[str]:
    """Material ids still required by active mine quests in this system."""
    needed: set[str] = set()
    for quest in _active_quests(state):
        if quest.kind != "mine":
            continue
        if quest.target_system_id != system_id:
            continue
        if quest.progress >= quest.target_count:
            continue
        if quest.target_material_id:
            needed.add(quest.target_material_id)
    return needed


def bounty_kills_remaining_in_system(state: GameState, system_id: str) -> int:
    """Hostile kills still needed for active bounty/kill quests in this system."""
    remaining = 0
    for quest in _active_quests(state):
        if quest.kind != "kill" or not quest.target_system_id:
            continue
        if quest.target_system_id != system_id:
            continue
        remaining += max(0, quest.target_count - quest.progress)
    return remaining


def _complete_quest(state: GameState, quest: Quest) -> None:
    quest.status = QuestStatus.DONE
    base = QUEST_REWARDS.get(quest.kind, QUEST_REWARDS["generic"])
    reward = base * (1.0 + 0.2 * max(0, quest.tier - 1))
    state.player.credits += reward
    state.log(f"QUEST COMPLETE: {quest.title} (+{reward:.0f} cr)")
    _replace_completed_quest(state, quest)


def _bump_progress(state: GameState, quest: Quest, amount: int = 1) -> None:
    quest.progress += amount
    if quest.progress >= quest.target_count:
        _complete_quest(state, quest)


def quest_progress_label(quest: Quest) -> str:
    if quest.kind in ("kill", "mine", "buy", "sell") and quest.status == QuestStatus.ACTIVE:
        return f"{quest.summary} ({quest.progress}/{quest.target_count})"
    return quest.summary


def note_hostile_kill(state: GameState) -> None:
    system_id = state.player.ship.location.system_id
    for quest in _active_quests(state):
        if quest.kind != "kill":
            continue
        if quest.target_system_id and quest.target_system_id != system_id:
            continue
        _bump_progress(state, quest)


def note_mined(state: GameState, material_id: str, quantity: int) -> None:
    if quantity <= 0:
        return
    system_id = state.player.ship.location.system_id
    for quest in _active_quests(state):
        if quest.kind != "mine":
            continue
        if quest.target_system_id and quest.target_system_id != system_id:
            continue
        if quest.target_material_id and quest.target_material_id != material_id:
            continue
        _bump_progress(state, quest, quantity)


def note_market_buy(state: GameState, item_id: str, quantity: int) -> None:
    if quantity <= 0:
        return
    system_id = state.player.ship.location.system_id
    for quest in _active_quests(state):
        if quest.kind != "buy":
            continue
        if quest.target_system_id and quest.target_system_id != system_id:
            continue
        if quest.target_item_id and quest.target_item_id != item_id:
            continue
        _bump_progress(state, quest, quantity)


def note_market_sell(state: GameState, item_id: str, quantity: int) -> None:
    if quantity <= 0:
        return
    system_id = state.player.ship.location.system_id
    for quest in _active_quests(state):
        if quest.kind != "sell":
            continue
        if quest.target_system_id and quest.target_system_id != system_id:
            continue
        if quest.target_item_id and quest.target_item_id != item_id:
            continue
        _bump_progress(state, quest, quantity)


def note_docked(state: GameState) -> None:
    system_id = state.player.ship.location.system_id
    for quest in _active_quests(state):
        if quest.kind != "dock":
            continue
        if quest.target_system_id and quest.target_system_id != system_id:
            continue
        _complete_quest(state, quest)


def note_jump_arrived(
    state: GameState, dest_system_id: str, origin_system_id: str | None
) -> None:
    if not origin_system_id or origin_system_id == dest_system_id:
        return
    origin = state.galaxy.get_system(origin_system_id)
    if not origin or dest_system_id not in origin.neighbors:
        return
    for quest in _active_quests(state):
        if quest.kind != "scout":
            continue
        _bump_progress(state, quest)


def current_objective(state: GameState) -> str:
    if state.tutorial_step != TutorialStep.DONE:
        from lsl_online.tutorial import tutorial_objective

        return tutorial_objective(state)
    active = _active_quests(state)
    if not active:
        return ""
    if len(active) == 1:
        quest = active[0]
        return f"{quest.title}: {quest_progress_label(quest)}"
    return " | ".join(f"{q.title}" for q in active[:3])


def unlock_quests(state: GameState) -> None:
    if state.quests:
        return
    state.quests = generate_quest_board(state)
    state.quests_unlocked = True
    state.log("Quest board unlocked. Type: quests  then  quest start <id>")


def _quest_kill_label(quest: Quest) -> str:
    return f"{quest.progress}/{quest.target_count} hostiles destroyed"


def list_quests(state: GameState) -> str | None:
    if not state.quests_unlocked:
        return "Quest board locked. Complete the tutorial first."
    if not state.quests:
        unlock_quests(state)
    state.log("── Quest board ──")
    for quest in state.quests:
        state.log(f"[{quest.status.value}] {quest.id}")
        state.log(f"  {quest.title}")
        if quest.kind == "kill":
            if quest.status == QuestStatus.ACTIVE:
                state.log(f"  {_quest_kill_label(quest)}")
            else:
                state.log(f"  Target: {quest.target_count} hostile ship(s)")
                state.log(f"  {quest.summary}")
        elif quest.status == QuestStatus.ACTIVE and quest.kind in (
            "mine",
            "buy",
            "sell",
        ):
            state.log(f"  {quest_progress_label(quest)}")
        else:
            state.log(f"  {quest.summary}")
    return None


def start_quest(state: GameState, quest_ref: str) -> str | None:
    if not state.quests_unlocked:
        return "Quest board locked."
    ref = quest_ref.lower().strip()
    for quest in state.quests:
        if (
            quest.id.lower() == ref
            or quest.title.lower() == ref
            or ref in quest.title.lower()
        ):
            if quest.status == QuestStatus.DONE:
                return "Quest already completed."
            if quest.status == QuestStatus.ACTIVE:
                return "Quest already active."
            quest.status = QuestStatus.ACTIVE
            quest.progress = 0
            state.log(f"Quest started: {quest.title}")
            state.log(quest_progress_label(quest))
            if (
                quest.target_system_id
                and quest.target_system_id == state.player.system_id
                and state.tutorial_step == TutorialStep.DONE
            ):
                if quest.kind == "mine":
                    mining.ensure_mine_quest_asteroids(state, quest.target_system_id)
                elif quest.kind == "buy":
                    from lsl_online.market import ensure_buy_quest_stock

                    ensure_buy_quest_stock(state, quest.target_system_id)
            return None
    return f"Quest not found: {quest_ref}"


def quest_status(state: GameState) -> str | None:
    if not state.quests_unlocked:
        return "Quest board locked."
    active = _active_quests(state)
    if not active:
        state.log("No active quests. Use: quests")
        return None
    for quest in active:
        state.log(f"ACTIVE {quest.id}: {quest.title} -- {quest_progress_label(quest)}")
    return None
