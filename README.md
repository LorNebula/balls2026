# EVE ASCII (Travel MVP)

Terminal EVE-inspired game: command-driven travel, Finnish-inspired galaxy, Python + Textual.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e .
python scripts/generate_galaxy.py --seed 42
python -m eve_ascii
```

Dev mode with CSS reload:

```bash
textual run --dev src/eve_ascii/app.py
```

## Controls

- `Ctrl+P` — command palette (travel, dock, jump, …)
- `:` — command line input
- `h` / `j` / `k` / `l` — pan map
- `+` / `-` — zoom map
- `g` — toggle galaxy / system view
- `q` — quit

## Commands (palette or `:` line)

| Command | Effect |
|---------|--------|
| `travel <x> <y> <z>` | Warp to coords in current system |
| `travel planet <name>` | Orbit a planet |
| `travel station <name>` | Warp near a station |
| `jump <system>` | Jump to linked system |
| `dock` / `undock` | Dock at nearby station / leave dock |

Game state is in-memory only (no backend).
