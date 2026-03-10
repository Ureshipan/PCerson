# PCerson

Локальный desktop-first AI-ассистент для Windows с модульной архитектурой, централизованными конфигами, локальной памятью и безопасными desktop capability.

## Что уже есть

* каркас `assistant-core` и `host-agent`;
* централизованные YAML-конфиги с автогенерацией user override;
* SQLite-память;
* базовый capability для открытия программ/файлов/папок/URL;
* CLI-режим для первого запуска;
* bootstrap / doctor / validate scripts;
* `docker compose` для локального service layer.

## Быстрый старт

1. Установить Python 3.11+.
2. Запустить `scripts/bootstrap.ps1`.
3. Проверить состояние `scripts/doctor.ps1`.
4. Запустить ассистента:

```powershell
.\run-assistant.ps1 "открой блокнот"
```

Прямой запуск через `python -m app.main` тоже возможен, но только с выставленным `PYTHONPATH`.

## Структура

См. [SPEC.md](/d:/gits/PCerson/SPEC.md), [ARCHITECTURE.md](/d:/gits/PCerson/ARCHITECTURE.md), [RUNBOOK.md](/d:/gits/PCerson/RUNBOOK.md).
