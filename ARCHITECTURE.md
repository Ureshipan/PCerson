# Architecture

## Слои

* `assistant-core`: оркестрация, конфиг, память, policy, capability routing.
* `host-agent`: платформенные действия, desktop notifications, future hotkeys/devices.
* `compose/`: локальные сервисы вроде `ollama` и `mqtt`.
* `config/` и `state/`: переносимые пользовательские настройки и runtime state.

## Стартовый поток

1. `ConfigLoader` объединяет `config/defaults/*.yaml` и `config/user/*.yaml`.
2. `attach/start` обновляет Windows shortcut catalog (`Desktop + pinned taskbar`) и пишет его в `state/runtime/shortcut_catalog.json`.
3. `AssistantApp` инициализирует persona, memory, shortcut catalog, capability registry и response policy.
4. `CommandRouter` обслуживает только служебные команды вроде `status/diag`; пользовательские desktop intent'ы уходят в модель.
5. `LLMClient` получает persona prompt + planner prompt и возвращает `reply + commands`.
6. `AssistantApp` валидирует и выполняет `commands` через capability mapping и policy слой.
7. `DesktopCapability` выполняет whitelisted desktop actions через `host-agent` platform adapter, включая `open_shortcut`.
8. Windows hotkey UI поднимает минимальное popup-окно ввода/ответа поверх desktop workflow.
9. При ошибке исполнения результат возвращается модели через recovery prompt.
10. Результат логируется в session и episodic memory.
