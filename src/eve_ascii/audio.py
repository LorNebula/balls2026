"""Play WAV effects from repo audio/ via pygame.mixer (no display)."""

from __future__ import annotations

from pathlib import Path

from eve_ascii.models import GameState

AUDIO_DIR = Path(__file__).resolve().parents[2] / "audio"

# logical name -> filename (without .wav)
SOUND_FILES: dict[str, str] = {
    "blip": "blip",
    "explosion": "explosion",
    "hit": "hit",
    "jump": "jump",
    "laserShoot": "laserShoot",
    "miningLoop": "miningLoop",
    "pickup": "pickup",
    "sell": "sell",
    "warp": "warp",
}

_sounds: dict[str, object] = {}
_initialized = False
_init_error: str | None = None
_loop_channel = None
_loop_name: str | None = None


def audio_dir() -> Path:
    return AUDIO_DIR


def last_init_error() -> str | None:
    return _init_error


def _mixer_unavailable(pygame) -> bool:
    mixer = getattr(pygame, "mixer", None)
    if mixer is None:
        return True
    # Stock pygame on Python 3.14+ exposes mixer as MissingModule (no real init).
    if type(mixer).__name__ == "MissingModule":
        return True
    return not callable(getattr(mixer, "init", None))


def init_audio() -> bool:
    global _initialized, _loop_channel, _loop_name, _init_error
    if _initialized:
        return bool(_sounds)
    _init_error = None
    try:
        import pygame

        if _mixer_unavailable(pygame):
            _init_error = (
                "pygame mixer not built for this Python version. "
                "Run: pip install -e .  (uses pygame-ce)"
            )
            _initialized = True
            return False
        if pygame.mixer.get_init() is None:
            pygame.mixer.init(frequency=22050, size=-16, channels=8, buffer=512)
        _loop_channel = pygame.mixer.Channel(7)
        loaded = 0
        for key, stem in SOUND_FILES.items():
            path = AUDIO_DIR / f"{stem}.wav"
            if path.is_file():
                _sounds[key] = pygame.mixer.Sound(str(path))
                loaded += 1
        _initialized = True
        if loaded == 0:
            _init_error = f"No WAV files found in {AUDIO_DIR}"
            return False
        return True
    except Exception as exc:
        _init_error = str(exc)
        _sounds.clear()
        _initialized = True
        return False


def shutdown() -> None:
    global _initialized, _loop_name, _init_error
    stop_all_loops()
    try:
        import pygame

        if not _mixer_unavailable(pygame) and pygame.mixer.get_init() is not None:
            pygame.mixer.quit()
    except Exception:
        pass
    _sounds.clear()
    _initialized = False
    _init_error = None


def _ready() -> bool:
    return _initialized and bool(_sounds)


def play(name: str, *, volume: float = 1.0) -> None:
    if not _ready():
        return
    sound = _sounds.get(name)
    if sound is None:
        return
    try:
        sound.set_volume(max(0.0, min(1.0, volume)))
        sound.play()
    except Exception:
        pass


def play_loop(name: str, *, volume: float = 0.6) -> None:
    global _loop_name
    if not _ready() or _loop_channel is None:
        return
    if _loop_name == name and _loop_channel.get_busy():
        return
    stop_all_loops()
    sound = _sounds.get(name)
    if sound is None:
        return
    try:
        sound.set_volume(max(0.0, min(1.0, volume)))
        _loop_channel.play(sound, loops=-1)
        _loop_name = name
    except Exception:
        pass


def stop_loop(name: str) -> None:
    global _loop_name
    if _loop_name != name:
        return
    stop_all_loops()


def stop_all_loops() -> None:
    global _loop_name
    if _loop_channel is not None:
        try:
            _loop_channel.stop()
        except Exception:
            pass
    _loop_name = None


def request_sound(state: GameState, name: str, *, volume: float = 1.0) -> None:
    if not state.sound_enabled:
        return
    play(name, volume=volume)


def tick_mining_loop(state: GameState) -> None:
    """Called each frame from AudioBehaviour."""
    if not state.sound_enabled or not _ready():
        if state.mining_active:
            return
        stop_all_loops()
        return
    if state.mining_active:
        play_loop("miningLoop")
    else:
        stop_loop("miningLoop")
