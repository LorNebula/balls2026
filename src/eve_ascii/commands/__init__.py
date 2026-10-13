"""Player command dispatch."""

from eve_ascii.commands.registry import (
    COMMANDS,
    completion_candidates,
    execute_command,
    palette_suggestions,
)

__all__ = [
    "COMMANDS",
    "completion_candidates",
    "execute_command",
    "palette_suggestions",
]
