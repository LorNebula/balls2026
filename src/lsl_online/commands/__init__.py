"""Player command dispatch."""

from lsl_online.commands.registry import (
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
