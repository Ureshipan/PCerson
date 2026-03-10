# Journal

## 2026-03-10

* Прочитал ТЗ и начал проект с нуля.
* Создал каркас репозитория под `assistant-core`, `host-agent`, `config`, `schemas`, `scripts`, `compose`, `state`.
* Собрал минимальный рабочий v1-поток `config -> router -> capability -> memory -> doctor/bootstrap`.
* Сделал автогенерацию `config/user/*.yaml`, SQLite memory, CLI, Windows desktop capability и локальный `host-agent` bridge.
* Проверил `bootstrap.ps1`, `validate-config.ps1`, `doctor.ps1`, `python -m app.main --json status`.
* Исправил запуск скриптов из любой директории (скрипты теперь переходят в корень репозитория).
* Добавил `run-assistant.ps1` в корне и fallback-алиасы для русских команд (`блокнот`, `проводник` и т.д.).
* Следующий шаг: вынести transport между `assistant-core` и `host-agent`, добавить hotkey activation и реальный LLM backend.
