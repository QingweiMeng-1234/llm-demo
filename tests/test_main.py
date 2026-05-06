import types

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

import app.main as main


@pytest.fixture
def client():
    with TestClient(main.app) as test_client:
        yield test_client


def test_frontend_serves_index_html(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert response.headers["X-Latency-Ms"].isdigit()


def test_api_root_endpoint(client):
    response = client.get("/api")
    assert response.status_code == 200
    assert response.json() == {"message": "LLM API Demo is running. Visit /docs"}
    assert response.headers["X-Latency-Ms"].isdigit()


def test_health_endpoint(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_chat_rejects_when_app_api_key_missing(monkeypatch, client):
    monkeypatch.setattr(main, "APP_API_KEY", None)
    response = client.post("/chat", json={"message": "hello"}, headers={"X-API-Key": "any"})
    assert response.status_code == 500
    assert response.json()["detail"] == "Server misconfigured: APP_API_KEY missing"


def test_chat_rejects_unauthorized(monkeypatch, client):
    monkeypatch.setattr(main, "APP_API_KEY", "expected-key")
    response = client.post("/chat", json={"message": "hello"}, headers={"X-API-Key": "wrong-key"})
    assert response.status_code == 401
    assert response.json()["detail"] == "Unauthorized"


def test_chat_rejects_empty_message(monkeypatch, client):
    monkeypatch.setattr(main, "APP_API_KEY", "expected-key")
    response = client.post("/chat", json={"message": "  "}, headers={"X-API-Key": "expected-key"})
    assert response.status_code == 400
    assert response.json()["detail"] == "message is empty"


def test_chat_success(monkeypatch, client):
    monkeypatch.setattr(main, "APP_API_KEY", "expected-key")
    monkeypatch.setattr(main, "MODEL", "unit-test-model")

    class FakeCompletions:
        def __init__(self):
            self.last_kwargs = None

        def create(self, **kwargs):
            self.last_kwargs = kwargs
            return types.SimpleNamespace(
                choices=[types.SimpleNamespace(message=types.SimpleNamespace(content="  hello back  "))]
            )

    fake_completions = FakeCompletions()
    fake_client = types.SimpleNamespace(chat=types.SimpleNamespace(completions=fake_completions))
    monkeypatch.setattr(main, "get_openai_client", lambda: fake_client)

    response = client.post("/chat", json={"message": "hello"}, headers={"X-API-Key": "expected-key"})
    body = response.json()

    assert response.status_code == 200
    assert body["reply"] == "hello back"
    assert body["model"] == "unit-test-model"
    assert isinstance(body["latency_ms"], int)
    assert fake_completions.last_kwargs["model"] == "unit-test-model"
    assert fake_completions.last_kwargs["messages"][1]["content"] == "hello"


def test_chat_re_raises_http_exception(monkeypatch, client):
    monkeypatch.setattr(main, "APP_API_KEY", "expected-key")

    def _boom():
        raise HTTPException(status_code=418, detail="teapot")

    monkeypatch.setattr(main, "get_openai_client", _boom)
    response = client.post("/chat", json={"message": "hello"}, headers={"X-API-Key": "expected-key"})

    assert response.status_code == 418
    assert response.json()["detail"] == "teapot"


def test_chat_wraps_unexpected_exception(monkeypatch, client):
    monkeypatch.setattr(main, "APP_API_KEY", "expected-key")

    class BrokenCompletions:
        def create(self, **kwargs):
            raise RuntimeError("upstream failed")

    fake_client = types.SimpleNamespace(chat=types.SimpleNamespace(completions=BrokenCompletions()))
    monkeypatch.setattr(main, "get_openai_client", lambda: fake_client)

    response = client.post("/chat", json={"message": "hello"}, headers={"X-API-Key": "expected-key"})

    assert response.status_code == 500
    assert response.json()["detail"] == "LLM call failed: upstream failed"


def test_get_openai_client_raises_without_env_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="OPENAI_API_KEY is missing"):
        main.get_openai_client()


def test_get_openai_client_returns_openai_instance(monkeypatch):
    captured = {}

    class DummyOpenAI:
        def __init__(self, api_key):
            captured["api_key"] = api_key

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setattr(main, "OpenAI", DummyOpenAI)

    client = main.get_openai_client()
    assert isinstance(client, DummyOpenAI)
    assert captured["api_key"] == "sk-test"
