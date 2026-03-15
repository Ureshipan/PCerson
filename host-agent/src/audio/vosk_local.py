from __future__ import annotations

import json
import queue
import time
from pathlib import Path
from typing import Any


DEFAULT_VOSK_STT_CONFIG: dict[str, Any] = {
    "enabled": True,
    "backend": "vosk_local",
    "language": "ru-RU",
    "timeout_seconds": 8,
    "model_path": "state/runtime/vosk/models/vosk-model-small-ru-0.22",
    "model_name": "vosk-model-small-ru-0.22",
    "download_url": "https://alphacephei.com/vosk/models/vosk-model-small-ru-0.22.zip",
}


class VoskLocalSpeechToText:
    def __init__(self, stt_config: dict[str, Any] | None = None) -> None:
        raw = dict(DEFAULT_VOSK_STT_CONFIG)
        raw.update(stt_config or {})
        self.config = raw
        self.enabled = bool(raw.get("enabled", True))
        self.backend = "vosk_local"
        self.language = str(raw.get("language", "ru-RU")).strip() or "ru-RU"
        self.timeout_seconds = int(raw.get("timeout_seconds", 8) or 8)
        self.model_path = Path(str(raw.get("model_path", DEFAULT_VOSK_STT_CONFIG["model_path"]))).expanduser()

    def healthcheck(self) -> dict[str, Any]:
        if not self.enabled:
            return {"backend": self.backend, "ok": False, "enabled": False}
        try:
            import sounddevice as sd  # type: ignore
            from vosk import Model  # type: ignore
        except ModuleNotFoundError as exc:
            return {
                "backend": self.backend,
                "ok": False,
                "enabled": True,
                "message": f"Missing package: {exc.name}",
                "model_path": str(self.model_path),
            }
        if not self.model_path.exists():
            return {
                "backend": self.backend,
                "ok": False,
                "enabled": True,
                "message": "Vosk model not installed",
                "model_path": str(self.model_path),
            }
        try:
            input_device = sd.query_devices(kind="input")
            samplerate = int(float(input_device.get("default_samplerate", 16000)))
            Model(str(self.model_path))
        except Exception as exc:
            return {
                "backend": self.backend,
                "ok": False,
                "enabled": True,
                "message": str(exc),
                "model_path": str(self.model_path),
            }
        return {
            "backend": self.backend,
            "ok": True,
            "enabled": True,
            "language": self.language,
            "samplerate": samplerate,
            "model_path": str(self.model_path),
        }

    def transcribe_once(self) -> dict[str, Any]:
        if not self.enabled:
            return {"ok": False, "message": "STT disabled", "backend": self.backend}
        try:
            import sounddevice as sd  # type: ignore
            from vosk import KaldiRecognizer, Model  # type: ignore
        except ModuleNotFoundError as exc:
            return {"ok": False, "message": f"Missing package: {exc.name}", "backend": self.backend}
        if not self.model_path.exists():
            return {"ok": False, "message": "Vosk model not installed", "backend": self.backend}
        try:
            device_info = sd.query_devices(kind="input")
            samplerate = int(float(device_info.get("default_samplerate", 16000)))
            model = Model(str(self.model_path))
            recognizer = KaldiRecognizer(model, samplerate)
            audio_queue: queue.Queue[bytes] = queue.Queue()

            def callback(indata: bytes, frames: int, time_info: Any, status: Any) -> None:
                if status:
                    pass
                audio_queue.put(bytes(indata))

            result_text = ""
            partial_text = ""
            start_time = time.monotonic()
            with sd.RawInputStream(
                samplerate=samplerate,
                blocksize=8000,
                dtype="int16",
                channels=1,
                callback=callback,
            ):
                while time.monotonic() - start_time < self.timeout_seconds:
                    try:
                        data = audio_queue.get(timeout=0.4)
                    except queue.Empty:
                        continue
                    if recognizer.AcceptWaveform(data):
                        payload = json.loads(recognizer.Result())
                        result_text = str(payload.get("text", "")).strip()
                        if result_text:
                            break
                    else:
                        payload = json.loads(recognizer.PartialResult())
                        partial_text = str(payload.get("partial", "")).strip()
                if not result_text:
                    payload = json.loads(recognizer.FinalResult())
                    result_text = str(payload.get("text", "")).strip() or partial_text
            if not result_text:
                return {"ok": False, "message": "No speech recognized", "backend": self.backend}
            return {
                "ok": True,
                "text": result_text,
                "backend": self.backend,
                "samplerate": samplerate,
            }
        except Exception as exc:
            return {"ok": False, "message": str(exc), "backend": self.backend}
