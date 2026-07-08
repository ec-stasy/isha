"""
Voice input — Cycle 6 A14 rewrite. The old Vosk pipeline required the user to
install packages and download a ~50 MB model by hand; this version ships
everything in the app bundle and uses an internet speech API instead:

  microphone capture: `sounddevice` (bundled — nothing for the user to install)
  recognition:        Google's web speech API via the `SpeechRecognition`
                      package (no key or account needed)

Privacy note (and the reason for the one-time notice in the UI): unlike the
rest of Isha, a voice command's *audio* is sent to the speech service to be
transcribed. Nothing else — no logs, no config, no identity — is sent, and
voice stays entirely optional. The notice is shown once, on the very first
mic use (settings.voice.online_notice_shown).

Recording is silence-terminated: capture starts on mic click and ends after
~1.2 s of quiet following speech (or 12 s hard cap), so there's nothing to
configure and no fixed awkward window.
"""
import sys

_SAMPLE_RATE = 16000
_BLOCK = 1600            # 0.1 s chunks
_MAX_SECONDS = 12.0
_SILENCE_AFTER_SPEECH_S = 1.2
_SILENCE_RMS = 300       # int16 RMS below this counts as silence
_MIN_SPEECH_BLOCKS = 3   # need ~0.3 s of audible speech before silence can end capture


def is_available() -> bool:
    try:
        import sounddevice  # noqa: F401
        import speech_recognition  # noqa: F401
    except ImportError:
        return False
    return True


def unavailable_reason() -> str:
    try:
        import sounddevice  # noqa: F401
    except ImportError:
        return "Microphone capture isn't available in this build."
    try:
        import speech_recognition  # noqa: F401
    except ImportError:
        return "Speech recognition isn't available in this build."
    return ""


def _rms(block: bytes) -> float:
    import array
    samples = array.array("h")
    samples.frombytes(block)
    if not samples:
        return 0.0
    return (sum(s * s for s in samples) / len(samples)) ** 0.5


def record_until_silence(stop_flag=None, status_callback=None) -> bytes:
    """Records mono 16 kHz int16 audio until ~1.2 s of silence follows speech,
    a 12 s cap, or stop_flag is set. Returns raw PCM bytes ('' if nothing)."""
    import queue as _queue
    import sounddevice as sd

    audio = _queue.Queue()

    def _on_audio(indata, frames, time_info, status):
        audio.put(bytes(indata))

    chunks = []
    speech_blocks = 0
    silent_streak = 0.0
    max_blocks = int(_MAX_SECONDS * _SAMPLE_RATE / _BLOCK)

    with sd.RawInputStream(samplerate=_SAMPLE_RATE, blocksize=_BLOCK,
                           dtype="int16", channels=1, callback=_on_audio):
        for _ in range(max_blocks):
            if stop_flag is not None and stop_flag.is_set():
                break
            try:
                block = audio.get(timeout=1.0)
            except _queue.Empty:
                continue
            chunks.append(block)
            level = _rms(block)
            if level >= _SILENCE_RMS:
                speech_blocks += 1
                silent_streak = 0.0
                if status_callback is not None:
                    status_callback("hearing")
            else:
                silent_streak += _BLOCK / _SAMPLE_RATE
                if speech_blocks >= _MIN_SPEECH_BLOCKS and silent_streak >= _SILENCE_AFTER_SPEECH_S:
                    break
    return b"".join(chunks)


def transcribe(raw_pcm: bytes):
    """Sends the recorded audio to the online speech API; returns the
    transcript string, or None if nothing was understood, or raises OSError
    on a network problem."""
    if not raw_pcm:
        return None
    import speech_recognition as sr

    recognizer = sr.Recognizer()
    audio = sr.AudioData(raw_pcm, _SAMPLE_RATE, 2)  # 2 bytes/sample (int16)
    try:
        return recognizer.recognize_google(audio)
    except sr.UnknownValueError:
        return None
    except sr.RequestError as e:
        raise OSError(f"speech service unreachable: {e}")


def listen_and_transcribe(duration: float = None):
    """One-shot convenience for non-GUI callers: record (silence-terminated),
    transcribe online, return text or None. Never raises."""
    if not is_available():
        return None
    try:
        raw = record_until_silence()
        return transcribe(raw)
    except Exception:
        return None
