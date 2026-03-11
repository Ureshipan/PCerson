from __future__ import annotations

import ctypes
import ctypes.wintypes
from typing import Any, Callable

from activations.base import ActivationAdapter


WM_HOTKEY = 0x0312
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008


class WindowsHotkeyActivation(ActivationAdapter):
    def __init__(self, combo: str, enabled: bool = True) -> None:
        self.combo = combo
        self.enabled = enabled
        self._hotkey_id = 1
        self._running = False
        self._user32 = ctypes.windll.user32

    def start(self, emit_event: Callable[[dict[str, Any]], None]) -> None:
        if not self.enabled:
            return
        modifiers, vk = self._parse_combo(self.combo)
        if not self._user32.RegisterHotKey(None, self._hotkey_id, modifiers, vk):
            raise RuntimeError(f"Cannot register hotkey: {self.combo}")
        self._running = True
        msg = ctypes.wintypes.MSG()
        while self._running:
            result = self._user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
            if result == 0:
                break
            if msg.message == WM_HOTKEY and msg.wParam == self._hotkey_id:
                emit_event(self.emit_event({"source": "hotkey", "combo": self.combo}))
            self._user32.TranslateMessage(ctypes.byref(msg))
            self._user32.DispatchMessageW(ctypes.byref(msg))
        self.stop()

    def stop(self) -> None:
        if self._running:
            self._running = False
        self._user32.UnregisterHotKey(None, self._hotkey_id)

    def is_enabled(self) -> bool:
        return self.enabled

    def emit_event(self, payload: dict[str, Any]) -> dict[str, Any]:
        return payload

    def _parse_combo(self, combo: str) -> tuple[int, int]:
        parts = [part.strip().lower() for part in combo.split("+") if part.strip()]
        modifiers = 0
        key_part = ""
        for part in parts:
            if part in {"ctrl", "control"}:
                modifiers |= MOD_CONTROL
            elif part == "alt":
                modifiers |= MOD_ALT
            elif part == "shift":
                modifiers |= MOD_SHIFT
            elif part in {"win", "windows"}:
                modifiers |= MOD_WIN
            else:
                key_part = part
        vk = self._vk_code(key_part)
        return modifiers, vk

    def _vk_code(self, key: str) -> int:
        key = key.strip().lower()
        named = {
            "space": 0x20,
            "enter": 0x0D,
            "tab": 0x09,
            "esc": 0x1B,
            "escape": 0x1B,
        }
        if key in named:
            return named[key]
        if len(key) == 1 and "a" <= key <= "z":
            return ord(key.upper())
        if len(key) == 1 and "0" <= key <= "9":
            return ord(key)
        if key.startswith("f") and key[1:].isdigit():
            number = int(key[1:])
            if 1 <= number <= 24:
                return 0x70 + (number - 1)
        raise ValueError(f"Unsupported hotkey key: {key}")
