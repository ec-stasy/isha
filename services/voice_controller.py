"""
Streaming voice (§4.3) — wraps the optional vosk/sounddevice stack with
Vosk's PartialResult events so words appear live in the command bar as they
are spoken. Capture ends on ~1.2 s of silence (a final result with text) or
an explicit stop; the transcript lands in the input for the user to edit —
voice never auto-executes. Everything stays on this machine.

If streaming misbehaves on a given microphone, `settings.voice.streaming:
false` falls back to a_voice_input's fixed 4 s record.
"""
import json
import threading

from PySide6.QtCore import QObject, Signal

_SAMPLE_RATE = 16000
_BLOCK = 4000  # 0.25 s chunks

_controller = None


def get_voice_controller():
    global _controller
    if _controller is None:
        _controller = VoiceController()
    return _controller


class VoiceController(QObject):
    partial = Signal(str)       # live words while speaking
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
            self.unavailable.emit(
                "Voice needs the optional vosk + sounddevice packages and a downloaded "
                "model — see Settings ▸ Voice.")
            self.stopped.emit()
            return
        self.listening = True
        self._stop_flag.clear()
        threading.Thread(target=self._capture, daemon=True, name="isha-voice-stream").start()

    def stop(self) -> None:
        self._stop_flag.set()

    def _capture(self) -> None:
        try:
            import queue as _queue
            import sounddevice as sd
            import vosk
            import a_voice_input

            model = a_voice_input._load_model()
            if model is None:
                self.unavailable.emit("Voice model missing — see Settings ▸ Voice.")
                return

            recognizer = vosk.KaldiRecognizer(model, _SAMPLE_RATE)
            audio = _queue.Queue()

            def _on_audio(indata, frames, time_info, status):
                audio.put(bytes(indata))

            transcript = ""
            with sd.RawInputStream(samplerate=_SAMPLE_RATE, blocksize=_BLOCK,
                                   dtype="int16", channels=1, callback=_on_audio):
                silent_final_streak = 0
                for _ in range(240):  # hard cap ~60 s
                    if self._stop_flag.is_set():
                        break
                    try:
                        chunk = audio.get(timeout=1.0)
                    except _queue.Empty:
                        continue
                    if recognizer.AcceptWaveform(chunk):
                        text = json.loads(recognizer.Result()).get("text", "")
                        if text:
                            transcript = (transcript + " " + text).strip()
                            self.partial.emit(transcript)
                            silent_final_streak = 0
                        elif transcript:
                            # a finalized empty segment after speech = the pause that ends capture
                            silent_final_streak += 1
                            if silent_final_streak >= 1:
                                break
                    else:
                        words = json.loads(recognizer.PartialResult()).get("partial", "")
                        if words:
                            self.partial.emit((transcript + " " + words).strip())

            tail = json.loads(recognizer.FinalResult()).get("text", "")
            if tail:
                transcript = (transcript + " " + tail).strip()
            if transcript:
                self.final.emit(transcript)
        except Exception as e:
            self.unavailable.emit(f"Voice capture failed: {e}")
        finally:
            self.listening = False
            self.stopped.emit()
