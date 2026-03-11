# Runbook

## Bootstrap

```powershell
./scripts/bootstrap.ps1
```

Для полной пересборки контейнера и повторной загрузки модели:

```powershell
./scripts/bootstrap.ps1 -RebuildContainers
```

## Validate config

```powershell
./scripts/validate-config.ps1
```

## Doctor

```powershell
./scripts/doctor.ps1
```

## Run assistant-core

```powershell
.\run-assistant.ps1 "открой проводник"
```

## Model lifecycle

```powershell
.\start-model.ps1
.\attach-model.ps1
.\stop-model.ps1
```

## First run

```powershell
.\first-run.ps1
```

## Full MVP start

```powershell
.\start-mvp.ps1 "Дарова, хочу чо нибудь поиграть"
```

## Run interactive chat

```powershell
.\run-chat.ps1
```

## Run hotkey listener

```powershell
.\run-hotkey.ps1
```

## Run hotkey listener in console mode

```powershell
.\run-hotkey-console.ps1
```
