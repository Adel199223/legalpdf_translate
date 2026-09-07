import json
from concurrent.futures import ThreadPoolExecutor

import pytest

from legalpdf_translate.layout_cache import LayoutCache


KEY = "a" * 64


def test_disabled_cache_touches_nothing_even_with_invalid_key(tmp_path):
    root = tmp_path / "not-created"
    cache = LayoutCache(root)
    assert cache.get("../invalid") is None
    cache.set("../invalid", {"usage": "not a layout"})
    assert not root.exists()


@pytest.mark.parametrize("key", ["../data", "A" * 64, "b" * 63, None])
def test_enabled_cache_rejects_non_digest_keys(tmp_path, key):
    cache = LayoutCache(tmp_path, enabled=True)
    with pytest.raises(ValueError):
        cache.get(key)
    with pytest.raises(ValueError):
        cache.set(key, {"layout": {}})


@pytest.mark.parametrize("payload", [{"usage": {}}, {"layout": {}, "ocr": "text"}, {"layout": []},
                                     {"layout": {"number": float("nan")}}])
def test_only_finite_layout_json_allowed(tmp_path, payload):
    cache = LayoutCache(tmp_path / "cache", enabled=True)
    with pytest.raises(ValueError):
        cache.set(KEY, payload)
    assert not cache.root.exists()


def test_cache_corruption_is_miss_and_concurrent_writes_are_complete(tmp_path):
    cache = LayoutCache(tmp_path / "cache", enabled=True)
    with ThreadPoolExecutor(max_workers=4) as executor:
        list(executor.map(lambda n: cache.set(KEY, {"layout": {"sequence": n}}), range(16)))
    assert cache.get(KEY)["layout"]["sequence"] in range(16)
    assert len(list(cache.root.iterdir())) == 1
    path = cache.root / f"{KEY}.json"
    record = json.loads(path.read_text(encoding="utf-8"))
    record["payload"]["layout"]["sequence"] = 99
    path.write_text(json.dumps(record), encoding="utf-8")
    assert cache.get(KEY) is None
    path.write_text("[", encoding="utf-8")
    assert cache.get(KEY) is None
