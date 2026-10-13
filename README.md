# LSL ONLINE

LSL ONLINE — ASCII terminal space trading: tutorial, combat, travel, quests. Finnish-inspired galaxy, Python + Textual.

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

- `:` — focus command line (always visible at bottom)
- `Tab` / `Right` — accept inline completion ghost text
- `Up` / `Down` — browse command history and restore the current draft
- Enter commands at the prompt: `galaxy`, `system`, `zoom in`, `zoom out`, `help`, `quit`

## UI (ASCII)

The game UI uses **7-bit ASCII** characters only (`+`, `-`, `|`, letters, digits). ANSI colors (Rich) add contrast; there are no Unicode box-drawing characters.

- **Top and bottom bars** — single-line `| ... |` chrome (title + footer).
- **Playfield** — map and event log share one `+---|` frame (map ~2/3, log ~1/3).
- **Status, command input, completions** — plain ASCII lines (no extra `| ... |` bars).

Open-space view: your ship stays left-center; world scrolls around it with ASCII ship shapes and colors.

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

New games start the **tutorial** (hyperspace → pirate fight → jump → galaxy → quests). During combat try: `lock A`, `fire`.

The default galaxy has 72 systems arranged in a central ring and spiral arms, with each arm connecting only to the ring. Every generated station has a hangar with a small ship selection. Station markets stock a rotating selection of pirate salvage and asteroid minerals; prices respond to supply. Use `skip` to bypass the opening tutorial. Asteroid fields appear in some systems without stations. Lock an asteroid and fire to mine ore; mined asteroids stay depleted for the current game session. Galaxy generation is deterministic for a seed; regenerate with `python scripts/generate_galaxy.py --seed <seed>`.
