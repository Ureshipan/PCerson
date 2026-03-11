# Scope

Текущая реализация покрывает стартовую часть v1 из `TZ.md`:

* Windows-first архитектура;
* local-first конфиг и state;
* базовая долговременная память на SQLite;
* безопасный desktop action whitelist;
* hotkey activation adapter (Windows);
* text-first ответы;
* локальный LLM adapter (`ollama` + fallback);
* bootstrap и doctor;
* опциональные модули оставлены расширяемыми.

Следующий инкремент: wake-word/STT, camera/printer backends, home-assistant bridge transport.
