# EVE ASCII

Terminal EVE-inspired game: tutorial, combat, travel, quests. Finnish-inspired galaxy, Python + Textual.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e .
python scripts/generate_galaxy.py --seed 42
python -m eve_ascii
python -m eve_ascii --no-tutorial   # skip opening tutorial, free play
```

Dev mode with CSS reload:

```bash
textual run --dev src/eve_ascii/app.py
```

## Controls

- `:` — focus command line (always visible at bottom)
- `Tab` / `Right` — accept inline completion ghost text
- `Esc` — focus map (so `g`, `h/j/k/l` work)
- `?` — list commands in the log
- `h` / `j` / `k` / `l` — pan map
- `+` / `-` — zoom map; galaxy view centers on your system and lists its linked systems
- `g` — toggle galaxy / system view
- `system` / `close` — exit the market and show the current system
- `q` — quit

## UI (ASCII)

The game UI uses **7-bit ASCII** characters only (`+`, `-`, `|`, letters, digits). ANSI colors (Rich) add contrast; there are no Unicode box-drawing characters.

- **Top and bottom bars** — single-line `| ... |` chrome (title + footer).
- **Playfield** — map and event log share one `+---|` frame (map ~2/3, log ~1/3).
- **Status, command input, completions** — plain ASCII lines (no extra `| ... |` bars).
- **Ship inspect** — modal content wrapped in `+---|`.

Open-space view: your ship stays left-center; world scrolls around it with ASCII ship shapes and colors.

## Commands (`:` line)

| Command | Effect |
|---------|--------|
| `travel <x> <y> <z>` | Warp to coords in current system |
| `travel planet <name>` | Orbit a planet |
| `travel station <name>` | Warp near a station |
| `jump <system>` | Jump to a linked system (costs 1 fuel) |
| `market` / `inventory` | Open the docked station market |
| `buy <item> <quantity>` | Buy stocked cargo, or `buy reactor 1` / `buy weapons 1` to upgrade |
| `sell <item> <quantity>` | Sell cargo at a docked station |
| `lock <A-Z> [reactor\|shield\|01-04]` | Combat target lock |
| `fire` / `cease` | Start / stop lasers |
| `comms` | Show inbox (Commander Crosshair) |
| `quests` / `quest start <id>` / `quest status` | Quest board |

New games start the **tutorial** (hyperspace → pirate fight → jump → galaxy → quests). During combat try: `lock A`, `fire`.

Asteroid fields appear in some systems without stations. Lock an asteroid and fire to mine ore; mined asteroids stay depleted for the current game session. Galaxy generation is deterministic for a seed; regenerate with `python scripts/generate_galaxy.py --seed <seed>`.

Game state is in-memory only (no backend).
