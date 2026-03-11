from __future__ import annotations

import json
import difflib
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from capabilities.desktop import DesktopCapability
from config.loader import ConfigLoader
from integrations.host_bridge import LocalHostBridge
from integrations.llm import LLMClient
from integrations.news import NewsService
from integrations.shortcut_catalog import ShortcutCatalog
from integrations.vector_memory import VectorMemoryStore
from integrations.weather import WeatherService
from memory.service import MemoryEntry, MemoryService
from orchestration.router import CommandRouter
from persona.profile import PersonaProfile
from policies.response_policy import ResponsePolicy


class AssistantApp:
    def __init__(self, config_root: Path, state_root: Path) -> None:
        self.repo_root = config_root.parent
        self.config = ConfigLoader(config_root).load_all()
        self.persona = PersonaProfile.from_config(self.config["persona"])
        self.memory = MemoryService(state_root / "memory" / "assistant.sqlite3")
        self.router = CommandRouter(self.config["devices"])
        self.response_policy = ResponsePolicy(self.config["assistant"], self.config["routines"])
        self.llm = LLMClient(self.config["models"])
        self.vector_memory = VectorMemoryStore(self.config["models"])
        self.weather = WeatherService(self.config["providers"])
        self.news = NewsService(self.config["providers"])
        self.shortcut_catalog = ShortcutCatalog(state_root)
        devices_context = dict(self.config["devices"])
        devices_context["shortcut_catalog"] = self.shortcut_catalog.load()
        self.desktop = DesktopCapability(
            enabled=self.config["assistant"]["capabilities"].get("desktop", True),
            host_bridge=LocalHostBridge(
                repo_root=self.repo_root,
                devices_config=devices_context,
                assistant_config=self.config["assistant"],
            ),
        )

    def handle_text(self, text: str) -> dict[str, Any]:
        route = self.router.route(text)
        intent = route["intent"]
        time_context = self._build_time_context()

        self.memory.add(MemoryEntry(kind="session", content=text or "status"))
        self.memory.add(MemoryEntry(kind="user_message", content=text or "status"))

        if intent == "status":
            result = self._build_status()
        else:
            result = self._handle_chat_with_model_actions(text, route_hint=route, time_context=time_context)

        self.memory.add(MemoryEntry(kind="assistant_message", content=result["message"]))
        self.memory.add(MemoryEntry(kind="episodic", content=result["message"], metadata=json.dumps(result, ensure_ascii=False)))
        if intent != "status":
            self._persist_long_term_memory(
                user_text=text,
                assistant_result=result,
                time_context=time_context,
            )
        return result

    def _handle_desktop(self, intent: str, payload: dict[str, Any]) -> dict[str, Any]:
        if intent == "desktop.open_alias":
            execution = self.desktop.execute("open_alias", payload)
        elif intent == "desktop.open_shortcut":
            execution = self.desktop.execute("open_shortcut", payload)
        elif intent == "desktop.open_url":
            execution = self.desktop.execute("open_url", payload)
        elif intent == "desktop.open_path":
            execution = self.desktop.execute("open_path", payload)
        elif intent == "desktop.open_alias_or_program":
            execution = self.desktop.execute("open_alias_or_program", payload)
        elif intent == "desktop.open_recent_file":
            execution = self.desktop.execute("open_recent", {"target_type": "file"})
        elif intent == "desktop.open_recent_folder":
            execution = self.desktop.execute("open_recent", {"target_type": "folder"})
        elif intent == "desktop.run_registered":
            execution = self.desktop.execute("run_registered", payload)
        else:
            execution = {"ok": False, "message": f"Unsupported desktop intent: {intent}"}
        execution["channels"] = self.response_policy.channels()
        return execution

    def _handle_chat_with_model_actions(self, text: str, route_hint: dict[str, Any], time_context: dict[str, Any]) -> dict[str, Any]:
        shortcuts = self.shortcut_catalog.load()
        shortcut_candidates = self._rank_shortcut_candidates(text=text, shortcuts=shortcuts)
        memory_context = self._build_memory_context(text=text, time_context=time_context)
        action_context = {
            "time_context": time_context,
            "memory_context": memory_context,
            "available_shortcut_names": [item.get("display_name") for item in shortcuts],
            "shortcut_candidates": [
                {
                    "id": item.get("id"),
                    "display_name": item.get("display_name"),
                    "target_type": item.get("target_type"),
                    "source": item.get("source"),
                    "exists": item.get("exists"),
                    "search_text": item.get("search_text", ""),
                    "match_score": round(float(item.get("match_score", 0.0)), 3),
                }
                for item in shortcut_candidates
            ],
            "desktop_aliases": sorted(self.config["devices"].get("desktop_aliases", {}).keys()),
            "registered_commands": sorted(self.config["devices"].get("registered_commands", {}).keys()),
            "router_hint": route_hint,
            "capabilities": self.config["assistant"].get("capabilities", {}),
            "providers": {
                "weather": self.weather.healthcheck(),
                "news": self.news.healthcheck(),
            },
            "allowed_actions": [
                "desktop.open_shortcut",
                "desktop.open_alias",
                "desktop.open_url",
                "desktop.open_path",
                "desktop.open_alias_or_program",
                "desktop.open_recent_file",
                "desktop.open_recent_folder",
                "desktop.run_registered",
                "info.get_weather",
                "info.get_news",
            ],
        }
        model_result = self.llm.chat_with_actions(
            user_text=text,
            system_prompt=f"{self.persona.system_prompt}\n\n{self.persona.memory_context_system_prompt}",
            planner_system_prompt=self.persona.planner_system_prompt,
            action_context=action_context,
        )
        commands = model_result.get("commands", [])
        forced_action = self._required_info_action(route_hint)
        if forced_action and not commands:
            forced_command = self.llm.force_tool_command(
                user_text=text,
                required_action=forced_action,
                system_prompt=f"{self.persona.system_prompt}\n\n{self.persona.memory_context_system_prompt}",
            )
            if forced_command is not None:
                commands = [forced_command]
        commands = self._sanitize_model_commands(text=text, commands=commands, route_hint=route_hint)
        executed: list[dict[str, Any]] = []
        for command in commands:
            executed.append(self._execute_model_command(command))

        reply = model_result.get("reply", "Готово.")
        successful = [item for item in executed if item.get("ok")]
        failed = [item for item in executed if not item.get("ok")]
        wants_action = str(route_hint.get("intent", "")).startswith("desktop.")
        if wants_action and not commands:
            recovery = self.llm.recover_after_execution_error(
                user_text=text,
                failed_results=[{"ok": False, "message": "Model did not provide actionable command"}],
                action_context=action_context,
                system_prompt=f"{self.persona.system_prompt}\n\n{self.persona.memory_context_system_prompt}",
                recovery_system_prompt=self.persona.recovery_system_prompt,
            )
            return {
                "ok": False,
                "message": recovery,
                "llm_message": model_result.get("reply", ""),
                "executed_commands": [],
                "channels": self.response_policy.channels(),
            }

        if successful:
            reply = f"{reply} Выполнено действий: {len(successful)}."
        info_results = [item for item in successful if str(item.get("action", "")).startswith("info.")]
        if info_results:
            reply = self._format_info_results(info_results) or self.llm.compose_tool_reply(
                user_text=text,
                tool_results=info_results,
                system_prompt=f"{self.persona.system_prompt}\n\n{self.persona.memory_context_system_prompt}",
                tool_result_system_prompt=self.persona.tool_result_system_prompt,
            )
        if failed:
            recovery = self.llm.recover_after_execution_error(
                user_text=text,
                failed_results=failed,
                action_context=action_context,
                system_prompt=f"{self.persona.system_prompt}\n\n{self.persona.memory_context_system_prompt}",
                recovery_system_prompt=self.persona.recovery_system_prompt,
            )
            reply = recovery

        return {
            "ok": len(failed) == 0,
            "message": reply,
            "llm_message": model_result.get("reply", ""),
            "executed_commands": executed,
            "channels": self.response_policy.channels(),
        }

    def _execute_model_command(self, command: dict[str, Any]) -> dict[str, Any]:
        action = str(command.get("action", "")).strip()
        payload = command.get("payload", {})
        if not isinstance(payload, dict):
            return {"ok": False, "message": f"Invalid payload for action {action}"}
        action, payload = self._normalize_model_command(action=action, payload=payload)

        mapping = {
            "desktop.open_shortcut": lambda: self.desktop.execute("open_shortcut", payload),
            "desktop.open_alias": lambda: self.desktop.execute("open_alias", payload),
            "desktop.open_url": lambda: self.desktop.execute("open_url", payload),
            "desktop.open_path": lambda: self.desktop.execute("open_path", payload),
            "desktop.open_alias_or_program": lambda: self.desktop.execute("open_alias_or_program", payload),
            "desktop.open_recent_file": lambda: self.desktop.execute("open_recent", {"target_type": "file"}),
            "desktop.open_recent_folder": lambda: self.desktop.execute("open_recent", {"target_type": "folder"}),
            "desktop.run_registered": lambda: self.desktop.execute("run_registered", payload),
            "info.get_weather": lambda: self.weather.get_weather(location=str(payload.get("location", "")).strip() or None),
            "info.get_news": lambda: self.news.get_news(
                topic=str(payload.get("topic", "")).strip() or None,
                limit=int(payload.get("limit", 5) or 5),
            ),
        }
        executor = mapping.get(action)
        if executor is None:
            return {"ok": False, "message": f"Unsupported model action: {action}"}
        result = executor()
        result["action"] = action
        return result

    def _normalize_model_command(self, action: str, payload: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        normalized_action = action
        normalized_payload = dict(payload)
        target = str(normalized_payload.get("target", "")).strip()
        alias = str(normalized_payload.get("alias", "")).strip().lower()
        shortcut_id = str(normalized_payload.get("shortcut_id", "")).strip()

        if shortcut_id:
            shortcut_match = self._best_shortcut_match(shortcut_id)
            if shortcut_match is not None:
                return "desktop.open_shortcut", {"shortcut_id": str(shortcut_match.get("id", ""))}
            return "desktop.open_shortcut", {"shortcut_id": shortcut_id}
        if target:
            shortcut_match = self._best_shortcut_match(target)
            if shortcut_match is not None:
                return "desktop.open_shortcut", {"shortcut_id": str(shortcut_match.get("id", ""))}
        if alias in {"браузер", "browser"}:
            available = {str(name).lower() for name in self.config["devices"].get("desktop_aliases", {}).keys()}
            if "browser" in available:
                return "desktop.open_alias", {"alias": "browser"}
            return "desktop.open_url", {"target": "https://www.google.com"}

        if target:
            lowered = target.lower()
            if lowered in {"ютуб", "youtube"}:
                return "desktop.open_url", {"target": "https://www.youtube.com"}
            if lowered in {"гугл", "google"}:
                return "desktop.open_url", {"target": "https://www.google.com"}
            if lowered in {"гитхаб", "github"}:
                return "desktop.open_url", {"target": "https://github.com"}
            if self._looks_like_domain(lowered):
                return "desktop.open_url", {"target": self._ensure_url_scheme(target)}
            if normalized_action == "desktop.open_alias_or_program" and self._looks_like_site_phrase(lowered):
                return "desktop.open_url", {"target": self._site_phrase_to_url(lowered)}
            if normalized_action == "desktop.open_alias_or_program" and lowered in {"браузер", "browser"}:
                return "desktop.open_url", {"target": "https://www.google.com"}

        return normalized_action, normalized_payload

    def _looks_like_domain(self, value: str) -> bool:
        if value.startswith(("http://", "https://")):
            return True
        if " " in value:
            return False
        if "\\" in value:
            return False
        return bool(re.match(r"^[a-z0-9.-]+\.[a-z]{2,}(/.*)?$", value))

    def _ensure_url_scheme(self, value: str) -> str:
        if value.startswith(("http://", "https://")):
            return value
        return f"https://{value}"

    def _looks_like_site_phrase(self, value: str) -> bool:
        indicators = ("сайт", "site", "ютуб", "youtube", "гитхаб", "github", "гугл", "google")
        return any(token in value for token in indicators)

    def _site_phrase_to_url(self, value: str) -> str:
        lowered = value.lower()
        if "ютуб" in lowered or "youtube" in lowered:
            return "https://www.youtube.com"
        if "гитхаб" in lowered or "github" in lowered:
            return "https://github.com"
        if "гугл" in lowered or "google" in lowered:
            return "https://www.google.com"
        cleaned = re.sub(r"\b(сайт|site)\b", "", lowered).strip()
        cleaned = re.sub(r"\s+", " ", cleaned)
        if self._looks_like_domain(cleaned):
            return self._ensure_url_scheme(cleaned)
        return f"https://www.google.com/search?q={cleaned or lowered}"

    def _rank_shortcut_candidates(self, text: str, shortcuts: list[dict[str, Any]]) -> list[dict[str, Any]]:
        lowered_text = text.lower()
        query_tokens = self._normalize_tokens(text)
        ranked: list[tuple[float, dict[str, Any]]] = []
        for shortcut in shortcuts:
            display_name = str(shortcut.get("display_name", ""))
            lowered_name = display_name.lower()
            search_text = str(shortcut.get("search_text", lowered_name))
            shortcut_tokens = shortcut.get("search_tokens", [])
            if not isinstance(shortcut_tokens, list):
                shortcut_tokens = []
            normalized_shortcut_tokens = [str(token).lower() for token in shortcut_tokens]
            score = difflib.SequenceMatcher(a=lowered_text, b=lowered_name).ratio()
            if lowered_name and lowered_name in lowered_text:
                score += 1.0
            if search_text and lowered_text in search_text.lower():
                score += 0.65
            score += self._token_overlap_score(query_tokens, normalized_shortcut_tokens)
            if str(shortcut.get("source", "")).lower() == "taskbar":
                score += 0.08
            enriched = dict(shortcut)
            enriched["match_score"] = score
            ranked.append((score, enriched))
        ranked.sort(key=lambda item: item[0], reverse=True)
        top = [shortcut for score, shortcut in ranked if score > 0.18][:12]
        return top

    def _best_shortcut_match(self, text: str) -> dict[str, Any] | None:
        ranked = self._rank_shortcut_candidates(text=text, shortcuts=self.shortcut_catalog.load())
        if not ranked:
            return None
        best = ranked[0]
        if float(best.get("match_score", 0.0)) < 0.72:
            return None
        return best

    def _normalize_tokens(self, text: str) -> list[str]:
        raw_tokens = re.findall(r"[a-zA-Zа-яА-Я0-9]+", text.lower())
        tokens: list[str] = []
        for token in raw_tokens:
            if len(token) < 2:
                continue
            tokens.append(token)
            transliterated = self._transliterate_token(token)
            if transliterated != token:
                tokens.append(transliterated)
            stem = self._stem_token(token)
            if stem != token:
                tokens.append(stem)
                transliterated_stem = self._transliterate_token(stem)
                if transliterated_stem != stem:
                    tokens.append(transliterated_stem)
        return list(dict.fromkeys(tokens))

    def _stem_token(self, token: str) -> str:
        endings = (
            "иями", "ями", "ами", "ого", "ему", "ому", "ими", "его",
            "ее", "ие", "ые", "ий", "ый", "ой", "ая", "яя", "ое",
            "ам", "ям", "ах", "ях", "ов", "ев", "ом", "ем",
            "ую", "юю", "ы", "и", "а", "я", "е", "у", "ю", "о",
        )
        if len(token) <= 4:
            return token
        for ending in endings:
            if token.endswith(ending) and len(token) - len(ending) >= 4:
                return token[: -len(ending)]
        return token

    def _token_overlap_score(self, query_tokens: list[str], shortcut_tokens: list[str]) -> float:
        if not query_tokens or not shortcut_tokens:
            return 0.0
        shortcut_set = set(shortcut_tokens)
        score = 0.0
        for token in query_tokens:
            if token in shortcut_set:
                score += 0.45
                continue
            best = 0.0
            for shortcut_token in shortcut_set:
                best = max(best, difflib.SequenceMatcher(a=token, b=shortcut_token).ratio())
            if best >= 0.86:
                score += 0.28
            elif best >= 0.74:
                score += 0.16
        return min(score, 1.8)

    def _transliterate_token(self, token: str) -> str:
        mapping = {
            "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e",
            "ж": "zh", "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m",
            "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
            "ф": "f", "х": "h", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "sch", "ъ": "",
            "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
        }
        if re.fullmatch(r"[a-z0-9]+", token):
            return token
        return "".join(mapping.get(char, char) for char in token.lower())

    def _required_info_action(self, route_hint: dict[str, Any]) -> str | None:
        intent = str(route_hint.get("intent", "")).strip().lower()
        if intent == "info.weather":
            return "info.get_weather"
        if intent == "info.news":
            return "info.get_news"
        return None

    def _sanitize_model_commands(
        self,
        text: str,
        commands: list[dict[str, Any]],
        route_hint: dict[str, Any],
    ) -> list[dict[str, Any]]:
        if not isinstance(commands, list):
            return []
        cleaned = [item for item in commands if isinstance(item, dict)]
        if len(cleaned) <= 1:
            return cleaned
        intent = str(route_hint.get("intent", "")).strip().lower()
        if intent in {"info.weather", "info.news"}:
            return cleaned[:1]
        lowered = text.lower()
        multi_intent_markers = (" и ", " затем ", " потом ", " а еще ", " и ещё ", ",")
        explicitly_multiple = any(marker in lowered for marker in multi_intent_markers)
        if explicitly_multiple:
            return cleaned[:2]
        return []

    def _format_info_results(self, info_results: list[dict[str, Any]]) -> str:
        if not info_results:
            return ""
        first = info_results[0]
        action = str(first.get("action", ""))
        data = first.get("data", {})
        if not isinstance(data, dict):
            return ""
        if action == "info.get_weather":
            location = data.get("location", {})
            current = data.get("current", {})
            today = data.get("today", {})
            if not isinstance(location, dict) or not isinstance(current, dict) or not isinstance(today, dict):
                return ""
            return (
                f"Погода в {location.get('name', 'указанном месте')}: {current.get('weather_text', 'неизвестно')}. "
                f"Сейчас {current.get('temperature_c')}°C, ощущается как {current.get('apparent_temperature_c')}°C. "
                f"Сегодня от {today.get('temperature_min_c')}°C до {today.get('temperature_max_c')}°C, "
                f"ветер {current.get('wind_speed_kmh')} км/ч, вероятность осадков до {today.get('precipitation_probability_max')}%."
            )
        if action == "info.get_news":
            items = data.get("items", [])
            if not isinstance(items, list) or not items:
                return ""
            lines = []
            for item in items[:3]:
                if not isinstance(item, dict):
                    continue
                title = str(item.get("title", "")).strip()
                source = str(item.get("source", "")).strip()
                if title:
                    lines.append(f"- {title}" + (f" ({source})" if source else ""))
            if not lines:
                return ""
            topic = str(data.get("topic", "")).strip()
            prefix = f"Короткая выжимка по новостям" + (f" про {topic}" if topic else "") + ":\n"
            return prefix + "\n".join(lines)
        return ""

    def _build_status(self) -> dict[str, Any]:
        return {
            "ok": True,
            "message": "assistant-core active",
            "channels": self.response_policy.channels(),
            "persona": self.persona.name,
            "llm": self.llm.healthcheck(),
            "semantic_memory": self.vector_memory.healthcheck(),
            "shortcut_catalog_entries": len(self.shortcut_catalog.load()),
            "desktop": self.desktop.healthcheck(),
            "recent_memory": self.memory.recent(limit=5),
        }

    def runtime_snapshot(self) -> dict[str, Any]:
        return {
            "persona": self.persona.name,
            "llm": self.llm.healthcheck(),
            "semantic_memory": self.vector_memory.healthcheck(),
            "shortcut_catalog_entries": len(self.shortcut_catalog.load()),
            "desktop": self.desktop.healthcheck(),
        }

    def _build_time_context(self) -> dict[str, Any]:
        now = datetime.now().astimezone()
        return {
            "iso": now.isoformat(),
            "date": now.strftime("%Y-%m-%d"),
            "time": now.strftime("%H:%M"),
            "weekday": now.strftime("%A"),
            "timezone": str(now.tzinfo),
            "quiet_hours": self.config["routines"].get("quiet_hours", {}),
        }

    def _build_memory_context(self, text: str, time_context: dict[str, Any]) -> dict[str, Any]:
        recent_dialogue = self.memory.recent_dialogue(limit=8)
        profile_facts = self.memory.recent_by_kinds(["user_profile_fact"], limit=6)
        preferences = self.memory.recent_by_kinds(["user_preference"], limit=6)
        schedule_items = self.memory.recent_by_kinds(["schedule_item"], limit=6)
        summaries = self.memory.recent_by_kinds(["conversation_summary"], limit=4)
        semantic_hits = self.vector_memory.search(
            query=text,
            embed_texts=self.llm.embed_texts,
            limit=int(self.config["models"].get("memory", {}).get("top_k", 6)),
        )
        return {
            "time_context": time_context,
            "recent_dialogue": recent_dialogue,
            "user_profile": [item["content"] for item in profile_facts],
            "user_preferences": [item["content"] for item in preferences],
            "schedule_items": [item["content"] for item in schedule_items],
            "recent_summaries": [item["content"] for item in summaries],
            "relevant_memories": semantic_hits,
        }

    def _persist_long_term_memory(self, user_text: str, assistant_result: dict[str, Any], time_context: dict[str, Any]) -> None:
        assistant_text = str(assistant_result.get("llm_message") or assistant_result.get("message") or "").strip()
        extracted = self.llm.extract_memory(
            user_text=user_text,
            assistant_text=assistant_text,
            executed_commands=assistant_result.get("executed_commands", []),
            system_prompt=self.persona.system_prompt,
            memory_system_prompt=self.persona.memory_extraction_system_prompt,
            time_context=time_context,
        )
        vector_items: list[dict[str, Any]] = []
        created_at = time_context.get("iso", "")
        for kind, source_key in (
            ("user_profile_fact", "profile_facts"),
            ("user_preference", "preferences"),
        ):
            for item in extracted.get(source_key, []):
                text = str(item.get("text", "")).strip() if isinstance(item, dict) else ""
                confidence = float(item.get("confidence", 0.0)) if isinstance(item, dict) else 0.0
                if not text or confidence < 0.45:
                    continue
                if self.memory.contains(kind=kind, content=text):
                    continue
                metadata = {"confidence": confidence}
                self.memory.add_structured(kind=kind, content=text, metadata=metadata)
                vector_items.append(
                    {
                        "kind": kind,
                        "text": text,
                        "created_at": created_at,
                        "metadata": metadata,
                    }
                )
        for item in extracted.get("schedule_items", []):
            if not isinstance(item, dict):
                continue
            text = str(item.get("text", "")).strip()
            confidence = float(item.get("confidence", 0.0))
            if not text or confidence < 0.45:
                continue
            if self.memory.contains(kind="schedule_item", content=text):
                continue
            metadata = {
                "confidence": confidence,
                "time_hint": str(item.get("time_hint", "")).strip(),
            }
            self.memory.add_structured(kind="schedule_item", content=text, metadata=metadata)
            vector_items.append(
                {
                    "kind": "schedule_item",
                    "text": text,
                    "created_at": created_at,
                    "metadata": metadata,
                }
            )
        summary = str(extracted.get("summary", "")).strip()
        if summary and not self.memory.contains(kind="conversation_summary", content=summary):
            self.memory.add_structured(kind="conversation_summary", content=summary, metadata={"source": "llm"})
            vector_items.append(
                {
                    "kind": "conversation_summary",
                    "text": summary,
                    "created_at": created_at,
                    "metadata": {"source": "llm"},
                }
            )
        self.vector_memory.upsert_text_memories(vector_items, embed_texts=self.llm.embed_texts)
