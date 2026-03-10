from pathlib import Path

from host_platform.windows.adapter import WindowsPlatformAdapter


def test_policy_denies_unknown_root(tmp_path: Path) -> None:
    adapter = WindowsPlatformAdapter({"allowed_paths": [str(tmp_path)]})
    denied = adapter._is_allowed_path(Path("C:/Windows"))
    assert denied is False
