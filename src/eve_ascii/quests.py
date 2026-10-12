"""Quest definitions and commands."""

from __future__ import annotations

from eve_ascii.models import GameState, Quest, QuestStatus


def seed_quests() -> list[Quest]:
    return [
        Quest(
            id="q_scout",
            title="Scout the Rim",
            summary="Jump to a neighboring system and report status.",
        ),
        Quest(
            id="q_station",
            title="Station Approach",
            summary="Travel near any station in your current system.",
        ),
        Quest(
            id="q_survive",
            title="Hold the Line",
            summary="Win one combat encounter without retreating.",
        ),
    ]


def unlock_quests(state: GameState) -> None:
    if state.quests:
        return
    state.quests = seed_quests()
    state.quests_unlocked = True
    state.log("Quest board unlocked. Type: quests")


def list_quests(state: GameState) -> str | None:
    if not state.quests_unlocked:
        return "Quest board locked. Complete the tutorial first."
    if not state.quests:
        unlock_quests(state)
    lines = ["QUESTS:"]
    for q in state.quests:
        lines.append(f"  [{q.status.value}] {q.id}: {q.title}")
    state.log("\n".join(lines))
    return None


def start_quest(state: GameState, quest_ref: str) -> str | None:
    if not state.quests_unlocked:
        return "Quest board locked."
    ref = quest_ref.lower().strip()
    for q in state.quests:
        if q.id.lower() == ref or q.title.lower() == ref or ref in q.title.lower():
            if q.status == QuestStatus.DONE:
                return "Quest already completed."
            if q.status == QuestStatus.ACTIVE:
                return "Quest already active."
            q.status = QuestStatus.ACTIVE
            state.log(f"Quest started: {q.title}")
            state.log(q.summary)
            return None
    return f"Quest not found: {quest_ref}"


def quest_status(state: GameState) -> str | None:
    if not state.quests_unlocked:
        return "Quest board locked."
    active = [q for q in state.quests if q.status == QuestStatus.ACTIVE]
    if not active:
        state.log("No active quests. Use: quests")
        return None
    for q in active:
        state.log(f"ACTIVE {q.id}: {q.title} -- {q.summary}")
    return None
