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
- `+` / `-` — zoom map
- `g` — toggle galaxy / system view
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
| `jump <system>` | Jump to linked system (costs fuel) |
| `lock <A-Z> [reactor\|shield\|01-04]` | Combat target lock |
| `fire` / `cease` | Start / stop lasers |
| `comms` | Show inbox (Commander Crosshair) |
| `quests` / `quest start <id>` / `quest status` | Quest board |

New games start the **tutorial** (hyperspace → pirate fight → jump → galaxy → quests). During combat try: `lock A`, `fire`.

Game state is in-memory only (no backend).
