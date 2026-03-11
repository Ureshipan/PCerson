from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Callable


class ActivationAdapter(ABC):
    @abstractmethod
    def start(self, emit_event: Callable[[dict[str, Any]], None]) -> None:
        raise NotImplementedError

    @abstractmethod
    def stop(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def is_enabled(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    def emit_event(self, payload: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError

