# Architecture

## Слои

* `assistant-core`: оркестрация, конфиг, память, policy, capability routing.
* `host-agent`: платформенные действия, desktop notifications, future hotkeys/devices.
* `compose/`: локальные сервисы вроде `ollama` и `mqtt`.
* `config/` и `state/`: переносимые пользовательские настройки и runtime state.

## Стартовый поток

1. `ConfigLoader` объединяет `config/defaults/*.yaml` и `config/user/*.yaml`.
2. `AssistantApp` инициализирует persona, memory, capability registry и response policy.
3. `CommandRouter` разбирает простой intent.
4. `DesktopCapability` выполняет whitelisted desktop actions через `host-agent` platform adapter.
5. Результат логируется в session и episodic memory.

