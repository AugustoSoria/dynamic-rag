import json

import pytest

from app.services import llm
from tests.conftest import make_pdf

PDF = make_pdf(
    [
        "La empresa Acme fue fundada en 1998 en Córdoba por Ana Pérez.",
        "En 2020 Acme lanzó su producto estrella, el robot aspiradora Zeta.",
        "Las ventas de Acme en 2023 alcanzaron los 12 millones de dólares.",
    ]
)


class FakeLLM:
    """Reemplaza a Groq: registra lo que recibe y devuelve respuestas fijas."""

    def __init__(self, rewrite="¿Quién fundó Acme?", answer=("Ana Pérez ", "fundó Acme [1].")):
        self.rewrite = rewrite
        self.answer = answer
        self.complete_calls: list[list[dict]] = []
        self.stream_calls: list[list[dict]] = []

    def complete(self, messages, reasoning_effort=None):
        self.complete_calls.append(messages)
        return self.rewrite

    def stream(self, messages, reasoning_effort=None):
        self.stream_calls.append(messages)
        yield from self.answer


@pytest.fixture
def fake_llm(monkeypatch):
    fake = FakeLLM()
    monkeypatch.setattr(llm, "complete", fake.complete)
    monkeypatch.setattr(llm, "stream", fake.stream)
    return fake


def parse_sse(body: str) -> list[tuple[str, dict]]:
    events = []
    for block in body.strip().split("\n\n"):
        lines = dict(line.split(": ", 1) for line in block.splitlines())
        events.append((lines["event"], json.loads(lines["data"])))
    return events


def upload(client, headers) -> str:
    r = client.post("/api/documents", headers=headers, files={"file": ("acme.pdf", PDF, "application/pdf")})
    assert r.status_code == 201
    return r.json()["doc_id"]


def test_stream_format(client, session_headers, fake_llm):
    upload(client, session_headers)
    r = client.post("/api/chat", headers=session_headers, json={"question": "¿Quién fundó la empresa?"})

    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/event-stream")
    events = parse_sse(r.text)
    names = [name for name, _ in events]
    assert names == ["sources", "token", "token", "done"]

    sources = events[0][1]["sources"]
    assert sources[0]["page"] == 1  # el fragmento más relevante es el de la fundación
    assert "".join(e[1]["text"] for e in events if e[0] == "token") == "Ana Pérez fundó Acme [1]."


def test_no_history_skips_rewrite(client, session_headers, fake_llm):
    upload(client, session_headers)
    r = client.post("/api/chat", headers=session_headers, json={"question": "¿Quién fundó la empresa?"})

    assert fake_llm.complete_calls == []
    assert parse_sse(r.text)[0][1]["search_query"] == "¿Quién fundó la empresa?"


def test_history_is_used_for_rewrite_and_answer(client, session_headers, fake_llm):
    upload(client, session_headers)
    history = [
        {"role": "user", "content": "¿Qué es Acme?"},
        {"role": "assistant", "content": "Es una empresa de robots [2]【3】 fundada en 1998【1†L2-L4】."},
    ]
    r = client.post("/api/chat", headers=session_headers, json={"question": "¿Y quién la fundó?", "history": history})

    # La búsqueda usa la pregunta reescrita...
    assert parse_sse(r.text)[0][1]["search_query"] == "¿Quién fundó Acme?"
    assert "¿Y quién la fundó?" in fake_llm.complete_calls[0][1]["content"]

    # ...y la respuesta recibe el historial (sin las citas viejas) + la pregunta original.
    messages = fake_llm.stream_calls[0]
    assert [m["role"] for m in messages] == ["system", "user", "assistant", "user"]
    assert messages[2]["content"] == "Es una empresa de robots  fundada en 1998."  # sin citas en ningún formato
    assert messages[-1]["content"].endswith("Pregunta: ¿Y quién la fundó?")


def test_rewrite_failure_falls_back_to_original(client, session_headers, fake_llm, monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("groq caído")

    monkeypatch.setattr(llm, "complete", boom)
    upload(client, session_headers)
    history = [{"role": "user", "content": "hola"}, {"role": "assistant", "content": "hola!"}]
    r = client.post("/api/chat", headers=session_headers, json={"question": "¿Quién fundó Acme?", "history": history})

    events = parse_sse(r.text)
    assert events[0][1]["search_query"] == "¿Quién fundó Acme?"
    assert events[-1][0] == "done"


def test_llm_error_is_sent_as_event(client, session_headers, fake_llm, monkeypatch):
    def broken_stream(*args, **kwargs):
        yield "Ana "
        raise RuntimeError("se cortó")

    monkeypatch.setattr(llm, "stream", broken_stream)
    upload(client, session_headers)
    r = client.post("/api/chat", headers=session_headers, json={"question": "¿Quién fundó Acme?"})

    names = [name for name, _ in parse_sse(r.text)]
    assert names == ["sources", "token", "error"]


def test_session_without_documents(client, session_headers, fake_llm):
    r = client.post("/api/chat", headers=session_headers, json={"question": "¿De qué trata?"})
    events = parse_sse(r.text)
    assert events[0][1]["sources"] == []
    assert "Subí un PDF" in events[1][1]["text"]
    assert fake_llm.stream_calls == []


def test_missing_api_key_returns_503(client, session_headers, monkeypatch):
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "groq_api_key", "")
    r = client.post("/api/chat", headers=session_headers, json={"question": "hola"})
    assert r.status_code == 503
