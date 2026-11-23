import pytest

from app.config import get_settings
from app.services.rate_limit import RateLimiter, limiter
from tests.conftest import make_pdf
from tests.test_chat import fake_llm  # noqa: F401  (fixture)


@pytest.fixture
def limits(monkeypatch):
    """Activa límites chicos solo para este test."""
    settings = get_settings()
    monkeypatch.setattr(settings, "rate_limit_chat_per_hour", 2)
    monkeypatch.setattr(settings, "rate_limit_uploads_per_hour", 1)
    limiter.reset()
    yield
    limiter.reset()


def test_ventana_deslizante():
    rl = RateLimiter()
    assert rl.hit("ip", 2, 60, now=0) is None
    assert rl.hit("ip", 2, 60, now=10) is None
    assert rl.hit("ip", 2, 60, now=20) == pytest.approx(40)  # el primero vence a los 60 s
    assert rl.hit("otra-ip", 2, 60, now=20) is None  # cada clave tiene su propio contador
    assert rl.hit("ip", 2, 60, now=61) is None  # venció el primero: hay lugar de nuevo


def test_el_intento_rechazado_no_cuenta():
    rl = RateLimiter()
    rl.hit("ip", 1, 60, now=0)
    for t in range(1, 50):
        rl.hit("ip", 1, 60, now=t)
    assert rl.hit("ip", 1, 60, now=60) is None


def test_chat_limitado_por_ip(client, limits, fake_llm, session_headers):  # noqa: F811
    body = {"question": "¿Hola?", "history": []}
    assert client.post("/api/chat", headers=session_headers, json=body).status_code == 200
    assert client.post("/api/chat", headers=session_headers, json=body).status_code == 200

    # Cambiar de sesión no saltea el límite: es por IP.
    import uuid

    r = client.post("/api/chat", headers={"X-Session-ID": str(uuid.uuid4())}, json=body)
    assert r.status_code == 429
    assert "límite de uso" in r.json()["detail"]
    assert int(r.headers["Retry-After"]) > 0


def test_subida_limitada_por_ip(client, limits, session_headers):
    pdf = make_pdf(["Contenido de prueba."])
    files = {"file": ("a.pdf", pdf, "application/pdf")}
    assert client.post("/api/documents", headers=session_headers, files=files).status_code == 202
    r = client.post("/api/documents", headers=session_headers, files=files)
    assert r.status_code == 429


def test_sin_limite_con_cero(client, fake_llm, session_headers):  # noqa: F811
    limiter.reset()
    body = {"question": "¿Hola?", "history": []}
    for _ in range(5):
        assert client.post("/api/chat", headers=session_headers, json=body).status_code == 200


def test_ip_desde_encabezado_de_cloudfront(client, limits, fake_llm, monkeypatch):  # noqa: F811
    monkeypatch.setattr(get_settings(), "client_ip_header", "CloudFront-Viewer-Address")
    body = {"question": "¿Hola?", "history": []}
    import uuid

    def ask(viewer):
        h = {"X-Session-ID": str(uuid.uuid4()), "CloudFront-Viewer-Address": viewer}
        return client.post("/api/chat", headers=h, json=body).status_code

    # Mismo usuario (distinto puerto) agota su límite; otro usuario detrás del mismo CloudFront no se ve afectado.
    assert ask("203.0.113.7:50001") == 200
    assert ask("203.0.113.7:50002") == 200
    assert ask("203.0.113.7:50003") == 429
    assert ask("2001:db8::1:443") == 200  # IPv6


def test_client_ip_parsea_ipv4_e_ipv6(monkeypatch):
    from starlette.requests import Request

    from app.api.deps import client_ip

    monkeypatch.setattr(get_settings(), "client_ip_header", "CloudFront-Viewer-Address")

    def req(value):
        headers = [(b"cloudfront-viewer-address", value.encode())] if value else []
        return Request({"type": "http", "headers": headers, "client": ("10.0.0.1", 1234)})

    assert client_ip(req("203.0.113.7:50001")) == "203.0.113.7"
    assert client_ip(req("2001:db8::1:443")) == "2001:db8::1"
    assert client_ip(req("")) == "10.0.0.1"  # sin encabezado: IP de la conexión
