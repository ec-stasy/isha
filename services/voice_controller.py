"""
Voice controller (Cycle 6 A14) — wraps the online voice pipeline
(a_voice_input: sounddevice capture + internet speech API) behind Qt signals.
Capture ends on ~1.2 s of silence after speech or an explicit stop; the
transcript lands in the input for the user to edit — voice never
auto-executes. Requires an internet connection (the UI shows a one-time
notice about that on first use); nothing besides the audio to transcribe is
ever sent.
"""
import threading

from PySide6.QtCore import QObject, Signal

_controller = None


def get_voice_controller():
    global _controller
    if _controller is None:
        _controller = VoiceController()
    return _controller


class VoiceController(QObject):
    status = Signal(str)        # "listening" / "hearing" / "transcribing"
    final = Signal(str)         # the finished transcript, ready to edit
    stopped = Signal()          # capture ended (any reason)
    unavailable = Signal(str)   # voice can't run; reason in plain words

    def __init__(self):
        super().__init__()
        self.listening = False
        self._stop_flag = threading.Event()

    def start(self) -> None:
        if self.listening:
            return
        import a_voice_input
        if not a_voice_input.is_available():
            self.unavailable.emit(a_voice_input.unavailable_reason() or "Voice input isn't available.")
            self.stopped.emit()
            return
        self.listening = True
        self._stop_flag.clear()
        threading.Thread(target=self._capture, daemon=True, name="isha-voice").start()

    def stop(self) -> None:
        """User clicked the mic again — finish recording and transcribe what we have."""
        self._stop_flag.set()

    def _capture(self) -> None:
        try:
            import a_voice_input

            self.status.emit("listening")
            raw = a_voice_input.record_until_silence(
                stop_flag=self._stop_flag,
                status_callback=lambda s: self.status.emit(s))
            if not raw:
                self.unavailable.emit("Didn't catch anything — is the microphone working?")
                return

            self.status.emit("transcribing")
            try:
                text = a_voice_input.transcribe(raw)
            except OSError:
                self.unavailable.emit("Voice needs an internet connection right now — "
                                      "couldn't reach the speech service.")
                return
            if text:
                self.final.emit(text)
            else:
                self.unavailable.emit("Couldn't make out any words — try again a bit closer to the mic.")
        except Exception as e:
            self.unavailable.emit(f"Voice capture failed: {e}")
        finally:
            self.listening = False
            self.stopped.emit()
