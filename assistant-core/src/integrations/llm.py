from __future__ import annotations

import json
import re
import socket
import urllib.error
import urllib.request
from typing import Any


class LLMClient:
    def __init__(self, models_config: dict[str, Any]) -> None:
        self.config = models_config.get("llm", {})
        self.backend = str(self.config.get("backend", "mock")).lower()
        self.model = self.config.get("model", "local-placeholder")
        self.endpoint = str(self.config.get("endpoint", "http://127.0.0.1:11434")).rstrip("/")
        self.memory_config = models_config.get("memory", {})
        self.embedding_model = str(self.memory_config.get("embedding_model", "nomic-embed-text"))

    def healthcheck(self) -> dict[str, Any]:
        if self.backend == "mock":
            return {"backend": "mock", "ok": True}
        if self.backend == "ollama":
            try:
                req = urllib.request.Request(f"{self.endpoint}/api/tags", method="GET")
                with urllib.request.urlopen(req, timeout=2) as resp:
                    return {"backend": "ollama", "ok": resp.status == 200}
            except Exception as exc:  # pragma: no cover
                return {"backend": "ollama", "ok": False, "error": str(exc)}
        return {"backend": self.backend, "ok": False, "error": "Unsupported backend"}

    def generate(self, prompt: str, system_prompt: str = "") -> str:
        if self.backend == "mock":
            return "Я готов. Для действий на ПК используй команды вида: 'открой ...'."
        if self.backend == "ollama":
            return self._generate_ollama(prompt=prompt, system_prompt=system_prompt, num_predict=120)
        return f"LLM backend '{self.backend}' не поддерживается."

    def chat_with_actions(
        self,
        user_text: str,
        system_prompt: str,
        planner_system_prompt: str,
        action_context: dict[str, Any],
    ) -> dict[str, Any]:
        if self.backend == "mock":
            return {"reply": "Я на mock-режиме. Могу общаться, но без модельного action-planner.", "commands": []}

        if self.backend != "ollama":
            return {"reply": f"LLM backend '{self.backend}' не поддерживается.", "commands": []}

        planner_system = (
            f"{system_prompt}\n\n{planner_system_prompt}\n\n"
            "Разрешенные actions:\n"
            "- desktop.open_shortcut: payload {shortcut_id}\n"
            "- desktop.open_alias: payload {alias}\n"
            "- desktop.open_url: payload {target}\n"
            "- desktop.open_path: payload {target}\n"
            "- desktop.open_alias_or_program: payload {target}\n"
            "- desktop.open_recent_file: payload {}\n"
            "- desktop.open_recent_folder: payload {}\n"
            "- desktop.run_registered: payload {name}\n"
            "- info.get_weather: payload {location?}\n"
            "- info.get_news: payload {topic?, limit?}\n"
        )

        planner_prompt = (
            f"Контекст actions:\n{json.dumps(action_context, ensure_ascii=False)}\n\n"
            f"Сообщение пользователя:\n{user_text}\n\n"
            "Верни только JSON."
        )
        raw = self._generate_ollama(
            prompt=planner_prompt,
            system_prompt=planner_system,
            json_mode=True,
            num_predict=220,
        )
        parsed = self._extract_json_object(raw)
        if parsed is None:
            fallback_reply = "Не смог надежно спланировать действие. Уточни, что именно открыть или сделать."
            if raw.strip() and not raw.lstrip().startswith("{"):
                fallback_reply = raw.strip()
            return {"reply": fallback_reply, "commands": []}
        reply = str(parsed.get("reply", "")).strip()
        commands = parsed.get("commands", [])
        if not isinstance(commands, list):
            commands = []
        normalized_commands: list[dict[str, Any]] = []
        for item in commands:
            if not isinstance(item, dict):
                continue
            action = item.get("action")
            payload = item.get("payload", {})
            if isinstance(action, str) and isinstance(payload, dict):
                normalized_commands.append({"action": action, "payload": payload})
        return {"reply": reply, "commands": normalized_commands}

    def recover_after_execution_error(
        self,
        user_text: str,
        failed_results: list[dict[str, Any]],
        action_context: dict[str, Any],
        system_prompt: str,
        recovery_system_prompt: str,
    ) -> str:
        if self.backend == "mock":
            return "Не получилось выполнить действие. Уточни: открыть сайт, другое имя программы или поиск в браузере?"
        if self.backend != "ollama":
            return "Не удалось выполнить действие. Уточни, что открыть: сайт, программу или поиск."

        recovery_system = (
            f"{system_prompt}\n\n{recovery_system_prompt}"
        )
        recovery_prompt = (
            f"Пользователь сказал: {user_text}\n"
            f"Ошибки выполнения: {json.dumps(failed_results, ensure_ascii=False)}\n"
            f"Контекст: {json.dumps(action_context, ensure_ascii=False)}\n"
        )
        return self._generate_ollama(prompt=recovery_prompt, system_prompt=recovery_system, num_predict=140)

    def extract_memory(
        self,
        user_text: str,
        assistant_text: str,
        executed_commands: list[dict[str, Any]],
        system_prompt: str,
        memory_system_prompt: str,
        time_context: dict[str, Any],
    ) -> dict[str, Any]:
        if self.backend == "mock":
            return {"profile_facts": [], "preferences": [], "schedule_items": [], "summary": ""}
        if self.backend != "ollama":
            return {"profile_facts": [], "preferences": [], "schedule_items": [], "summary": ""}
        prompt = (
            f"Текущее время: {json.dumps(time_context, ensure_ascii=False)}\n"
            f"Пользователь: {user_text}\n"
            f"Ассистент: {assistant_text}\n"
            f"Выполненные действия: {json.dumps(executed_commands, ensure_ascii=False)}\n"
            "Верни только JSON."
        )
        raw = self._generate_ollama(
            prompt=prompt,
            system_prompt=f"{system_prompt}\n\n{memory_system_prompt}",
            json_mode=True,
            num_predict=220,
        )
        parsed = self._extract_json_object(raw)
        if parsed is None:
            return {"profile_facts": [], "preferences": [], "schedule_items": [], "summary": ""}
        return {
            "profile_facts": parsed.get("profile_facts", []),
            "preferences": parsed.get("preferences", []),
            "schedule_items": parsed.get("schedule_items", []),
            "summary": str(parsed.get("summary", "")).strip(),
        }

    def compose_tool_reply(
        self,
        user_text: str,
        tool_results: list[dict[str, Any]],
        system_prompt: str,
        tool_result_system_prompt: str,
    ) -> str:
        if self.backend == "mock":
            return "Инструменты отработали, но mock-режим не умеет красиво пересказать результат."
        if self.backend != "ollama":
            return "Инструменты отработали, но этот LLM backend не поддерживается."
        prompt = (
            f"Запрос пользователя: {user_text}\n"
            f"Результаты инструментов: {json.dumps(tool_results, ensure_ascii=False)}\n"
        )
        return self._generate_ollama(
            prompt=prompt,
            system_prompt=f"{system_prompt}\n\n{tool_result_system_prompt}",
            num_predict=220,
        )

    def compose_context_reply(
        self,
        user_text: str,
        context: dict[str, Any],
        system_prompt: str,
        context_reply_system_prompt: str,
    ) -> str:
        if self.backend == "mock":
            return "Уточни, что именно тебе показать или открыть."
        if self.backend != "ollama":
            return "Уточни, что именно тебе показать или открыть."
        prompt = (
            f"Запрос пользователя: {user_text}\n"
            f"Контекст: {json.dumps(context, ensure_ascii=False)}\n"
        )
        return self._generate_ollama(
            prompt=prompt,
            system_prompt=f"{system_prompt}\n\n{context_reply_system_prompt}",
            num_predict=180,
        )

    def force_tool_command(
        self,
        user_text: str,
        required_action: str,
        system_prompt: str,
    ) -> dict[str, Any] | None:
        if self.backend != "ollama":
            return None
        tool_schema = {
            "info.get_weather": '{"action":"info.get_weather","payload":{"location":"..."}}',
            "info.get_news": '{"action":"info.get_news","payload":{"topic":"...","limit":5}}',
        }.get(required_action)
        if not tool_schema:
            return None
        prompt = (
            f"Запрос пользователя: {user_text}\n"
            f"Нужно вернуть ровно одну JSON-команду этого вида: {tool_schema}\n"
            "Верни только JSON."
        )
        raw = self._generate_ollama(
            prompt=prompt,
            system_prompt=(
                f"{system_prompt}\n\n"
                f"Ты обязан выбрать action {required_action}. Не отвечай обычным текстом."
            ),
            json_mode=True,
            num_predict=120,
        )
        parsed = self._extract_json_object(raw)
        if not parsed:
            return None
        action = str(parsed.get("action", "")).strip()
        payload = parsed.get("payload", {})
        if action != required_action or not isinstance(payload, dict):
            return None
        return {"action": action, "payload": payload}

    def force_desktop_command(
        self,
        user_text: str,
        action_context: dict[str, Any],
        system_prompt: str,
    ) -> dict[str, Any] | None:
        if self.backend != "ollama":
            return None
        prompt = (
            f"Запрос пользователя: {user_text}\n"
            f"Контекст desktop actions: {json.dumps(action_context, ensure_ascii=False)}\n"
            "Нужно вернуть ровно одну JSON-команду desktop-действия. "
            "Если есть сильный shortcut candidate, предпочти desktop.open_shortcut. "
            "Если безопасного действия нет, верни JSON вида {\"action\":\"\",\"payload\":{}}.\n"
            "Верни только JSON."
        )
        raw = self._generate_ollama(
            prompt=prompt,
            system_prompt=(
                f"{system_prompt}\n\n"
                "Ты обязан вернуть одну desktop command JSON-структуру без обычного текста."
            ),
            json_mode=True,
            num_predict=140,
        )
        parsed = self._extract_json_object(raw)
        if not parsed:
            return None
        action = str(parsed.get("action", "")).strip()
        payload = parsed.get("payload", {})
        if not action or not isinstance(payload, dict):
            return None
        if not action.startswith("desktop."):
            return None
        return {"action": action, "payload": payload}

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        cleaned = [text.strip() for text in texts if text and text.strip()]
        if not cleaned:
            return []
        if self.backend != "ollama":
            return []
        payload = {
            "model": self.embedding_model,
            "input": cleaned,
            "truncate": True,
        }
        raw = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"{self.endpoint}/api/embed",
            method="POST",
            data=raw,
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                embeddings = data.get("embeddings", [])
                return [vector for vector in embeddings if isinstance(vector, list)]
        except Exception:
            return []

    def _generate_ollama(
        self,
        prompt: str,
        system_prompt: str,
        json_mode: bool = False,
        num_predict: int = 160,
    ) -> str:
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "system": system_prompt or "",
            "options": {
                "num_predict": num_predict,
                "temperature": 0.1,
            },
        }
        if json_mode:
            payload["format"] = "json"
        raw = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"{self.endpoint}/api/generate",
            method="POST",
            data=raw,
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=45) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return str(data.get("response", "")).strip() or "Пустой ответ от LLM."
        except (TimeoutError, socket.timeout):
            try:
                with urllib.request.urlopen(req, timeout=90) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    return str(data.get("response", "")).strip() or "Пустой ответ от LLM."
            except Exception:
                return "Ошибка LLM: timed out"
        except urllib.error.URLError as exc:
            reason = getattr(exc, "reason", "")
            if isinstance(reason, TimeoutError):
                return "Ошибка LLM: timed out"
            return "Локальная LLM недоступна. Проверь, запущен ли runtime."
        except Exception as exc:  # pragma: no cover
            return f"Ошибка LLM: {exc}"

    def _extract_json_object(self, raw_text: str) -> dict[str, Any] | None:
        text = raw_text.strip()
        if not text:
            return None
        try:
            data = json.loads(text)
            if isinstance(data, dict):
                return data
        except Exception:
            pass

        fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.DOTALL | re.IGNORECASE)
        if fenced:
            candidate = fenced.group(1)
            try:
                data = json.loads(candidate)
                if isinstance(data, dict):
                    return data
            except Exception:
                return None

        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            candidate = text[start : end + 1]
            try:
                data = json.loads(candidate)
                if isinstance(data, dict):
                    return data
            except Exception:
                return None
        return None
