# PCerson

Локальный desktop-first AI-ассистент для Windows с модульной архитектурой, централизованными конфигами, локальной памятью и безопасными desktop capability.

## Что уже есть

* каркас `assistant-core` и `host-agent`;
* централизованные конфиги с автогенерацией user override;
* SQLite-память;
* базовый capability для открытия программ/файлов/папок/URL;
* открытие недавнего файла/папки и запуск зарегистрированных команд;
* global hotkey activation (`ctrl+alt+space` по умолчанию);
* локальный LLM integration (`ollama`, с graceful fallback);
* first-run мастер и интерактивный чат-режим;
* model command interface: модель может вернуть `commands`, и ассистент их исполнит;
* planner system prompt с правилами function-style команд (`reply + commands`) и URL-guardrails;
* запуск desktop-действий инициируется моделью; при ошибке ассистент делает recovery-уточнение;
* Windows shortcut catalog (`Desktop + pinned taskbar`) передается модели как runtime context;
* semantic memory: `Qdrant + Ollama embeddings`, извлечение профиля/предпочтений/расписания и retrieval в prompt;
* отдельные lifecycle-скрипты `start-model`, `stop-model`, `attach-model`;
* popup UI по hotkey для фонового взаимодействия с ассистентом;
* bootstrap / doctor / validate scripts;
* `docker compose` для локального service layer.

## Быстрый старт (MVP)

1. Установить Python 3.11+.
2. Первый запуск (интерактивная настройка + doctor + чат):

```powershell
.\first-run.ps1
```

Скрипт `scripts/bootstrap.ps1` интерактивный: предлагает варианты backend и модели.

Для полного автозапуска без вопросов:

```powershell
.\start-mvp.ps1 "Дарова, хочу чо нибудь поиграть"
```

Для текстового общения в интерактивном цикле:

```powershell
.\run-chat.ps1
```

Для быстрого одноразового запуска без Docker-проверок:

```powershell
.\run-assistant.ps1 "можешь открыть блокнот пожалуйста"
```

Опционально запустить hotkey-режим:

```powershell
.\run-hotkey.ps1
```

Это запускает фоновый hotkey listener и всплывающее окно ввода/ответа.
Теперь overlay показывает статус модели, памяти, число ярлыков и последние действия/инструменты.
Для консольного debug-варианта:

```powershell
.\run-hotkey-console.ps1
```

Прямой запуск через `python -m app.main` возможен только с выставленным `PYTHONPATH`.

Команды можно писать не только в формате `открой ...`, но и в обычной фразе.
Примеры: `ты чо дура а steam открой`, `а блокнот откроц`, `можешь открыть C:/Windows?`.
Ссылки и сайты тоже: `открой youtube`, `открой google.com`, `бро браузер открой`.

Важно: для контекстного распознавания и выполнения команд через модель используй `attach-model`, `first-run` или `start-mvp`. На каждом `attach/start` пересканируются ярлыки рабочего стола и pinned taskbar.

## Проверка GPU для модели

После первого реального запроса `ollama` должен загрузить модель и `doctor` покажет процессор выполнения:

```powershell
.\scripts\doctor.ps1
```

Смотри поле `model_runtime_state.processor`. Для прямой проверки рантайма:

```powershell
docker compose -f .\compose\docker-compose.yml exec -T ollama ollama ps
```

Если модель простаивает, там может быть `idle`. После запроса должно быть что-то вроде `100% GPU`.

## Память

Теперь память состоит из двух слоев:

* SQLite для сырых диалогов и локальных записей.
* `Qdrant` для семантического поиска по профилю, предпочтениям, кратким summary и элементам расписания.

После обычных диалогов ассистент пытается извлекать полезные долгоживущие факты о тебе и подмешивать их в следующие запросы как `memory_context`.

## Структура

См. [SPEC.md](/d:/gits/PCerson/SPEC.md), [ARCHITECTURE.md](/d:/gits/PCerson/ARCHITECTURE.md), [RUNBOOK.md](/d:/gits/PCerson/RUNBOOK.md).
