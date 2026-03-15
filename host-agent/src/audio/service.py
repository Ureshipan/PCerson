from __future__ import annotations

from typing import Any

from audio.windows_speech import WindowsSpeechToText

try:
    from audio.vosk_local import DEFAULT_VOSK_STT_CONFIG, VoskLocalSpeechToText
except ModuleNotFoundError:  # pragma: no cover
    DEFAULT_VOSK_STT_CONFIG = {}
    VoskLocalSpeechToText = None


def build_stt_service(stt_config: dict[str, Any] | None) -> Any:
    config = dict(stt_config or {})
    backend = str(config.get("backend", "none")).strip().lower()
    enabled = bool(config.get("enabled", False))
    if (not enabled or backend in {"", "none"}) and VoskLocalSpeechToText is not None:
        return VoskLocalSpeechToText(dict(DEFAULT_VOSK_STT_CONFIG))
    if backend == "vosk_local" and VoskLocalSpeechToText is not None:
        return VoskLocalSpeechToText(config)
    return WindowsSpeechToText(config)
