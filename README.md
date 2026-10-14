# LSL ONLINE

LSL ONLINE is an ASCII terminal space trading with, combat, travel, quests and most imporatantly: trading and scripts. 
Plays in Finnish-inspired galaxy where you play as an LSL driver (now a spaceship driver).
Uses Python + Textual.

## Play

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e .
python -m lsl_online
```

## Setup

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e .
python scripts/generate_galaxy.py --seed 42
python -m lsl_online
python -m lsl_online --no-tutorial   # skip opening tutorial, free play
python -m lsl_online --no-sound      # disable WAV sound effects

Sound uses **pygame-ce** (SDL). On Python 3.14+, stock `pygame` has no mixer — use `pip install -e .` so pygame-ce is installed.
```

Dev mode with CSS reload:

```bash
textual run --dev src/lsl_online/app.py
```

## Controls

- `Tab` / `Right` — accept inline completion ghost text
- `Up` / `Down` — browse command history and restore the current draft
- Enter commands at the prompt (look below)

## Commands (`:` line)

| Command | Effect |
|---------|--------|
| `travel <x> <y>` | Warp to 2D coordinates in the current system |
| `travel up\|right\|down\|left <units>` | Move a relative distance in that direction |
| `travel planet <name>` | (Deprecated — planets removed from map) |
| `travel station <name>` | Warp near a station |
| `jump <system>` | Jump to a linked system (costs 1 fuel) |
| `galaxy` / `system` | Switch between galaxy and current-system views |
| `zoom in` / `zoom out` | Zoom the active map view |
| `quit` | Exit the game |
| `market` | Open the docked station market and your cargo tables |
| `cargo` / `inventory` | Open your cargo hold anywhere |
| `buy <item> <quantity\|all>` | Buy stocked cargo, or `buy reactor 1` / `buy weapons 1` to upgrade |
| `path <system>` / `path clear` | Plot jump route; `jump` with no args follows next hop |
| `mark <system> <char> <color>` | User marker on galaxy map (colors: red, green, blue, …) |
| `sell <item> <quantity\|all>` | Sell cargo at a docked station |
| `hangar` | Open ship services at a station with a hangar |
| `buy ship <hull>` | Buy an in-stock hull at a hangar |
| `switch ship <id>` | Change active ship; each ship keeps its own cargo hold |
| `sell ship <id>` | Sell a ship after emptying its cargo; your last ship is protected |
| `lock <A-Z> [reactor\|shield\|01-04]` | Combat target lock |
| `fire` / `cease` | Start / stop lasers |
| `comms` | Show inbox (Commander Crosshair) |
| `quests` / `quest start <id>` / `quest status` | Quest board |