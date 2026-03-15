from __future__ import annotations

import json
import subprocess
from typing import Any


DEFAULT_STT_CONFIG: dict[str, Any] = {
    "enabled": True,
    "backend": "windows_speech",
    "language": "ru-RU",
    "timeout_seconds": 8,
}


def opportunistic_stt_config(stt_config: dict[str, Any] | None) -> dict[str, Any]:
    raw = dict(stt_config or {})
    backend = str(raw.get("backend", "none")).strip().lower()
    enabled = bool(raw.get("enabled", False))
    if enabled and backend not in {"", "none"}:
        return raw
    fallback = dict(DEFAULT_STT_CONFIG)
    fallback["implicit"] = True
    return fallback


class WindowsSpeechToText:
    def __init__(self, stt_config: dict[str, Any] | None = None) -> None:
        self.config = opportunistic_stt_config(stt_config)
        self.backend = str(self.config.get("backend", "windows_speech")).strip().lower()
        self.enabled = bool(self.config.get("enabled", True))
        self.language = str(self.config.get("language", "ru-RU")).strip() or "ru-RU"
        self.timeout_seconds = int(self.config.get("timeout_seconds", 8) or 8)
        self.implicit = bool(self.config.get("implicit", False))

    def healthcheck(self) -> dict[str, Any]:
        if not self.enabled:
            return {"backend": self.backend, "ok": False, "enabled": False}
        if self.backend != "windows_speech":
            return {"backend": self.backend, "ok": False, "error": "Unsupported STT backend"}
        payload = self._run_powershell_json(self._healthcheck_script())
        payload["backend"] = self.backend
        payload["enabled"] = self.enabled
        payload["implicit"] = self.implicit
        return payload

    def transcribe_once(self) -> dict[str, Any]:
        if not self.enabled:
            return {"ok": False, "message": "STT disabled"}
        if self.backend != "windows_speech":
            return {"ok": False, "message": f"Unsupported STT backend: {self.backend}"}
        payload = self._run_powershell_json(self._transcribe_script())
        payload["backend"] = self.backend
        return payload

    def _run_powershell_json(self, command: str) -> dict[str, Any]:
        completed = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                command,
            ],
            capture_output=True,
            text=True,
            check=False,
            encoding="utf-8",
        )
        if completed.returncode != 0:
            message = completed.stderr.strip() or completed.stdout.strip() or "PowerShell STT command failed"
            return {"ok": False, "message": message}
        raw = completed.stdout.strip()
        if not raw:
            return {"ok": False, "message": "Empty STT response"}
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return {"ok": False, "message": raw}
        if not isinstance(data, dict):
            return {"ok": False, "message": "Invalid STT response"}
        return data

    def _healthcheck_script(self) -> str:
        preferred = self.language.replace("'", "''")
        return (
            "try { "
            "Add-Type -AssemblyName System.Speech; "
            f"$preferred = '{preferred}'; "
            "$recognizers = [System.Speech.Recognition.SpeechRecognitionEngine]::InstalledRecognizers(); "
            "if (-not $recognizers -or $recognizers.Count -eq 0) { "
            "  @{ ok = $false; message = 'No installed speech recognizers'; recognizers = @() } | ConvertTo-Json -Compress; exit 0 "
            "} "
            "$selected = $recognizers | Where-Object { $_.Culture.Name -eq $preferred } | Select-Object -First 1; "
            "if (-not $selected) { $selected = $recognizers | Select-Object -First 1 } "
            "$microphoneReady = $true; "
            "try { "
            "  $engine = [System.Speech.Recognition.SpeechRecognitionEngine]::new($selected.Culture); "
            "  $engine.SetInputToDefaultAudioDevice(); "
            "} catch { $microphoneReady = $false } "
            "@{ "
            "  ok = $microphoneReady; "
            "  recognizer = $selected.Culture.Name; "
            "  message = $(if ($microphoneReady) { 'ready' } else { 'Recognizer available, but default microphone is not accessible' }); "
            "  recognizers = @($recognizers | ForEach-Object { $_.Culture.Name }); "
            "} | ConvertTo-Json -Compress "
            "} catch { "
            "  @{ ok = $false; message = $_.Exception.Message } | ConvertTo-Json -Compress "
            "}"
        )

    def _transcribe_script(self) -> str:
        preferred = self.language.replace("'", "''")
        timeout_seconds = max(3, min(20, self.timeout_seconds))
        return (
            "try { "
            "Add-Type -AssemblyName System.Speech; "
            f"$preferred = '{preferred}'; "
            f"$timeout = {timeout_seconds}; "
            "$recognizers = [System.Speech.Recognition.SpeechRecognitionEngine]::InstalledRecognizers(); "
            "if (-not $recognizers -or $recognizers.Count -eq 0) { "
            "  @{ ok = $false; message = 'No installed speech recognizers' } | ConvertTo-Json -Compress; exit 0 "
            "} "
            "$selected = $recognizers | Where-Object { $_.Culture.Name -eq $preferred } | Select-Object -First 1; "
            "if (-not $selected) { $selected = $recognizers | Select-Object -First 1 } "
            "$engine = [System.Speech.Recognition.SpeechRecognitionEngine]::new($selected.Culture); "
            "$engine.LoadGrammar([System.Speech.Recognition.DictationGrammar]::new()); "
            "$engine.InitialSilenceTimeout = [TimeSpan]::FromSeconds(4); "
            "$engine.BabbleTimeout = [TimeSpan]::FromSeconds($timeout); "
            "$engine.EndSilenceTimeout = [TimeSpan]::FromSeconds(1); "
            "$engine.EndSilenceTimeoutAmbiguous = [TimeSpan]::FromSeconds(1); "
            "$engine.SetInputToDefaultAudioDevice(); "
            "$result = $engine.Recognize([TimeSpan]::FromSeconds($timeout)); "
            "if ($null -eq $result) { "
            "  @{ ok = $false; message = 'No speech recognized'; recognizer = $selected.Culture.Name } | ConvertTo-Json -Compress; exit 0 "
            "} "
            "@{ "
            "  ok = $true; "
            "  text = $result.Text; "
            "  confidence = [double]$result.Confidence; "
            "  recognizer = $selected.Culture.Name "
            "} | ConvertTo-Json -Compress "
            "} catch { "
            "  @{ ok = $false; message = $_.Exception.Message } | ConvertTo-Json -Compress "
            "}"
        )
