# Journal

## 2026-03-10

* Прочитал ТЗ и начал проект с нуля.
* Создал каркас репозитория под `assistant-core`, `host-agent`, `config`, `schemas`, `scripts`, `compose`, `state`.
* Собрал минимальный рабочий v1-поток `config -> router -> capability -> memory -> doctor/bootstrap`.
* Сделал автогенерацию `config/user/*.yaml`, SQLite memory, CLI, Windows desktop capability и локальный `host-agent` bridge.
* Проверил `bootstrap.ps1`, `validate-config.ps1`, `doctor.ps1`, `python -m app.main --json status`.
* Исправил запуск скриптов из любой директории (скрипты теперь переходят в корень репозитория).
* Добавил `run-assistant.ps1` в корне и fallback-алиасы для русских команд (`блокнот`, `проводник` и т.д.).
* Добавил локальный LLM adapter (`ollama` + `mock` fallback) и подключил его в fallback-ответы.
* Реализовал hotkey activation adapter на WinAPI и запуск через `run-hotkey.ps1`.
* Расширил desktop capability: `open_recent(file/folder)` и `run_registered`.
* Дополнил doctor: LLM healthcheck, activation/capability статус и список алиасов/команд.
* Переделал `bootstrap.ps1` в интерактивный мастер: выбор backend/модели, автонастройка user-конфигов, автоподъём `ollama`, автозагрузка модели.
* Добавил `start-mvp.ps1` для полного запуска без ручной возни (`bootstrap + doctor + assistant`).
* Добавил play-сценарий: фразы про “хочу поиграть” дают ответ LLM и запускают `steam://open/main`.
* Добавил `first-run.ps1` и `run-chat.ps1`: первый запуск с мастером и постоянный текстовый интерактивный режим.
* Добавил model command interface: модель возвращает `reply + commands`, ассистент исполняет команды через capability mapping.
* Убрал спец-сценарий по “поиграть” из роутера, теперь решение о действиях принимает модель.
* Усилил устойчивость к разговорной/кривой формулировке: normalizer + fuzzy alias matching (`блокнотик`, `откроц`, `steam открой`).
* Поправил UTF-8 кодировку консольных скриптов (`first-run`, `bootstrap`, `run-*`), чтобы убрать кракозябры.
* Добавил URL guardrails в planner prompt и пост-нормализацию model-команд (`youtube/ютуб`, `google`, домены без `https`).
* Добавил alias `browser` и автоочистку битых alias-ключей в bootstrap.
* Проверил кейсы: `ютуб`, `браузер`, `google.com` открываются корректно через `desktop.open_url`/`desktop.open_alias`.
* Перевёл `open сайт ...` и похожие фразы в model planner по умолчанию, чтобы убрать ложный `open_alias_or_program`.
* Добавил правила planner для открытия сайтов по названию (включая fallback на google search).
* Проверил: `открой ка мне сайт гитхаба` -> `https://github.com`, `а теперь открой ютуб` -> `https://www.youtube.com`.
* Убрал прямое выполнение desktop-intent до модели: теперь действия инициируются через model `commands`.
* Добавил recovery после ошибок/пустых команд: модель формирует уточнение и варианты продолжения вместо молчания.
* Добавил Windows shortcut discovery для `Desktop + pinned taskbar`, запись catalog в `state/runtime/shortcut_catalog.json` и передачу его в planner context.
* Добавил `desktop.open_shortcut`, отдельные lifecycle-скрипты `start-model.ps1`, `stop-model.ps1`, `attach-model.ps1` и doctor-runtime-state.
* После включения Docker проверил живой `ollama`: `doctor` видит `backend=ollama`, `running=true`, shortcut catalog = 71 entries.
* Сжал planner context до shortlist candidates + списка shortcut names, чтобы `qwen2.5` перестал упираться в таймауты.
* На живой модели проверил `открой блокнот` и `открой ка мне сайт гитхаба`: оба сценария исполняются через model `commands`.
* Добавил popup UI по hotkey: минимальное окно истории + поле ввода, готовое к будущему STT-оверлею.
* `run-hotkey.ps1` теперь поднимает model runtime и открывает UI-режим; консольный hotkey вынесен в `run-hotkey-console.ps1`.
* Следующий шаг: STT/wake-word, camera/printer backends, Home Assistant bridge.
2026-03-11: Added `ollama` GPU compose config, runtime processor detection in `doctor`, and persisted processor state in model start/stop scripts.
2026-03-11: Verified live Docker/Ollama GPU inference; `ollama ps` now shows `100% GPU`, and `doctor` exposes the processor state after a real request.
2026-03-11: Started full semantic memory layer with `Qdrant + Ollama embeddings`, retrieval-aware prompt context, time context, and LLM extraction for profile/preferences/schedule/summary.
2026-03-11: Improved desktop action reliability: enriched shortcut catalog with search metadata, ranked shortcut candidates more semantically, normalized model targets into known shortcuts, and added fallback launch paths for broken `.lnk` execution.
2026-03-11: Added info tools for weather and news with model-driven planning, external data fetch, and second-pass response synthesis from tool results.
2026-03-11: Reworked hotkey overlay into a richer runtime UI with status chips, action panel, quick prompts, multi-line composer, and live assistant snapshot wiring.
