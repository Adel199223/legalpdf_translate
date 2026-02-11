from __future__ import annotations

import legalpdf_translate.secrets_store as secrets_store


class _FakeBackend:
    def __init__(self) -> None:
        self.values: dict[tuple[str, str], str] = {}

    def get_password(self, service_name: str, username: str) -> str | None:
        return self.values.get((service_name, username))

    def set_password(self, service_name: str, username: str, password: str) -> None:
        self.values[(service_name, username)] = password

    def delete_password(self, service_name: str, username: str) -> None:
        self.values.pop((service_name, username), None)


def test_delete_openai_key_removes_stored_value() -> None:
    backend = _FakeBackend()
    secrets_store.set_openai_key("abc", backend=backend)
    assert secrets_store.get_openai_key(backend=backend) == "abc"
    secrets_store.delete_openai_key(backend=backend)
    assert secrets_store.get_openai_key(backend=backend) is None


def test_delete_ocr_key_removes_stored_value() -> None:
    backend = _FakeBackend()
    secrets_store.set_ocr_key("def", backend=backend)
    assert secrets_store.get_ocr_key(backend=backend) == "def"
    secrets_store.delete_ocr_key(backend=backend)
    assert secrets_store.get_ocr_key(backend=backend) is None
