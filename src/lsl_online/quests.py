"""Quest definitions, procedural board, and progress hooks."""

from __future__ import annotations

import random

from lsl_online.ascii_ui import ascii_only
from lsl_online.market import ITEM_NAMES
from lsl_online.materials import MATERIALS
from lsl_online.models import GameState, Quest, QuestStatus, TutorialStep

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
    quests.append(
        Quest(
            id="q_bounty_contract",
            title=f"Clear {ascii_only(bounty_sys.name)}",
            summary=f"Destroy 2 hostile ships in {ascii_only(bounty_sys.name)}.",
            kind="kill",
            target_system_id=bounty_sys.id,
            target_count=2,
        )
    )

    mine_sys = systems[1 % len(systems)]
    mat = rng.choice(MATERIALS)
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
    station = trade_sys.stations[0]
    trade_items = [
        item_id
        for item_id, qty in station.inventory.items()
        if qty > 0 and not item_id.endswith("_upgrade") and item_id != "flagged_cargo"
    ]
    if not trade_items:
        trade_items = [m.id for m in MATERIALS[:4]]
    buy_item = rng.choice(trade_items)
    buy_qty = rng.randint(3, 8)
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
    sell_mat = rng.choice(MATERIALS)
    sell_qty = rng.randint(4, 10)
    quests.append(
        Quest(
            id="q_sell_contract",
            title=f"Market offload",
            summary=(
                f"Sell {sell_qty}x {ascii_only(sell_mat.name)} at a station in "
                f"{ascii_only(sell_sys.name)}."
            ),
            kind="sell",
            target_system_id=sell_sys.id,
            target_item_id=sell_mat.id,
            target_count=sell_qty,
        )
    )

    return quests


def _active_quests(state: GameState) -> list[Quest]:
    return [q for q in state.quests if q.status == QuestStatus.ACTIVE]


def _complete_quest(state: GameState, quest: Quest) -> None:
    quest.status = QuestStatus.DONE
    reward = QUEST_REWARDS.get(quest.kind, QUEST_REWARDS["generic"])
    state.player.credits += reward
    state.log(f"QUEST COMPLETE: {quest.title} (+{reward:.0f} cr)")


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
    for quest in _active_quests(state):
        if quest.kind == "dock":
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
        if quest.kind == "scout":
            _complete_quest(state, quest)


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


def list_quests(state: GameState) -> str | None:
    if not state.quests_unlocked:
        return "Quest board locked. Complete the tutorial first."
    if not state.quests:
        unlock_quests(state)
    lines = ["QUESTS:"]
    for quest in state.quests:
        extra = ""
        if quest.status == QuestStatus.ACTIVE and quest.kind in (
            "kill",
            "mine",
            "buy",
            "sell",
        ):
            extra = f" ({quest.progress}/{quest.target_count})"
        lines.append(f"  [{quest.status.value}] {quest.id}: {quest.title}{extra}")
    state.log("\n".join(lines))
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
