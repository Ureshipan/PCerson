from orchestration.router import CommandRouter


def test_router_open_url() -> None:
    router = CommandRouter({"desktop_aliases": {}})
    result = router.route("open https://example.com")
    assert result["intent"] == "chat.fallback"


def test_router_recent_file_ru() -> None:
    router = CommandRouter({"desktop_aliases": {}})
    result = router.route("открой недавний файл")
    assert result["intent"] == "chat.fallback"


def test_router_registered_command_ru() -> None:
    router = CommandRouter({"desktop_aliases": {}})
    result = router.route("открой команду open_downloads")
    assert result["intent"] == "chat.fallback"


def test_router_play_request_goes_to_model_planner() -> None:
    router = CommandRouter({"desktop_aliases": {}})
    result = router.route("Дарова, хочу чо нибудь поиграть")
    assert result["intent"] == "chat.fallback"


def test_router_embedded_open_alias() -> None:
    router = CommandRouter({"desktop_aliases": {"steam": {"type": "url", "target": "steam://open/main"}}})
    result = router.route("Дарова, открой steam пожалуйста")
    assert result["intent"] == "chat.fallback"


def test_router_embedded_open_path() -> None:
    router = CommandRouter({"desktop_aliases": {}})
    result = router.route("можешь открыть C:/Windows?")
    assert result["intent"] == "chat.fallback"


def test_router_embedded_open_infinitive_alias() -> None:
    router = CommandRouter({"desktop_aliases": {"steam": {"type": "url", "target": "steam://open/main"}}})
    result = router.route("можешь открыть steam?")
    assert result["intent"] == "chat.fallback"


def test_router_open_diminutive_program() -> None:
    router = CommandRouter({"desktop_aliases": {}})
    result = router.route("открой ка мне блокнотик")
    assert result["intent"] == "chat.fallback"


def test_router_open_site_phrase_delegates_to_model() -> None:
    router = CommandRouter({"desktop_aliases": {}})
    result = router.route("открой ка мне сайт гитхаба")
    assert result["intent"] == "chat.fallback"
