from orchestration.router import CommandRouter


def test_router_open_url() -> None:
    router = CommandRouter({"desktop_aliases": {}})
    result = router.route("open https://example.com")
    assert result["intent"] == "desktop.open_url"

