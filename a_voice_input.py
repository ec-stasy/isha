"""
Voice input — an optional module, loaded on demand and never imported at
startup unless the voice hotkey actually fires, per the roadmap's "heavy
things are optional modules" guardrail. Uses Vosk (offline, ~50MB, private)
rather than a cloud speech API, so a voice command never leaves the machine —
the same "no data collected" promise the rest of Isha makes.

Needs two optional dependencies neither of which is in requirements.txt's
required set: `vosk` (the recognizer) and `sounddevice` (microphone capture).
Both missing, or no downloaded Vosk model, degrades to returning None —
callers must treat that as "voice unavailable", not a crash.
"""
import os
from pathlib import Path

_VOSK_MODEL_ENV = "ISHA_VOSK_MODEL_PATH"
_SAMPLE_RATE = 16000
_model = None


def _default_model_path() -> Path:
    return Path.home() / ".isha" / "vosk-model"


def is_available() -> bool:
    try:
        import vosk  # noqa: F401
        import sounddevice  # noqa: F401
    except ImportError:
        return False
    return _model_path().is_dir()


def _model_path() -> Path:
    configured = os.environ.get(_VOSK_MODEL_ENV)
    return Path(configured) if configured else _default_model_path()


def _load_model():
    global _model
    if _model is not None:
        return _model
    try:
        import vosk
    except ImportError:
        return None
    path = _model_path()
    if not path.is_dir():
        return None
    vosk.SetLogLevel(-1)  # Vosk logs to stderr by default; keep it quiet
    _model = vosk.Model(str(path))
    return _model


def listen_and_transcribe(duration: float = 4.0):
    """
    Records `duration` seconds of mono 16kHz audio from the default microphone
    and returns the best-effort transcript, or None if voice input isn't
    available (missing vosk/sounddevice, no downloaded model, or no working
    microphone) — callers must handle None as "voice unavailable", not an error.
    """
    try:
        import sounddevice as sd
    except ImportError:
        return None

    model = _load_model()
    if model is None:
        return None

    try:
        import vosk
        import json as _json

        recording = sd.rec(int(duration * _SAMPLE_RATE), samplerate=_SAMPLE_RATE, channels=1, dtype="int16")
        sd.wait()

        recognizer = vosk.KaldiRecognizer(model, _SAMPLE_RATE)
        recognizer.AcceptWaveform(recording.tobytes())
        result = _json.loads(recognizer.FinalResult())
        text = result.get("text")
        return text or None
    except Exception:
        return None
