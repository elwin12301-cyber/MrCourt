"""Production setup: database addresses from hosts, the website served by the API, and page security headers."""
from pathlib import Path

from fastapi.testclient import TestClient

from mrcourt.config import Settings


def test_host_database_addresses_get_the_psycopg_driver() -> None:
    assert Settings(database_url="postgres://u:p@h:5432/d").database_url == "postgresql+psycopg://u:p@h:5432/d"
    assert Settings(database_url="postgresql://u:p@h/d").database_url == "postgresql+psycopg://u:p@h/d"
    assert Settings(database_url="sqlite:///./x.db").database_url == "sqlite:///./x.db"


def _website_app(tmp_path: Path, monkeypatch):
    (tmp_path / "assets").mkdir()
    (tmp_path / "index.html").write_text("<!doctype html><div id=root></div>", encoding="utf-8")
    (tmp_path / "assets" / "app.js").write_text("console.log(1)", encoding="utf-8")
    (tmp_path / "favicon.svg").write_text("<svg/>", encoding="utf-8")
    from mrcourt import config, main

    monkeypatch.setenv("FRONTEND_DIST", str(tmp_path))
    config.get_settings.cache_clear()
    try:
        return TestClient(main.create_app())
    finally:
        monkeypatch.delenv("FRONTEND_DIST")
        config.get_settings.cache_clear()


def test_the_website_is_served_with_page_rules_and_the_api_keeps_its_own(tmp_path, monkeypatch) -> None:
    client = _website_app(tmp_path, monkeypatch)
    page = client.get("/cases/123")  # a React route: index.html
    assert page.status_code == 200 and "id=root" in page.text
    assert "script-src 'self'" in page.headers["content-security-policy"]
    assert client.get("/assets/app.js").text == "console.log(1)"
    assert client.get("/favicon.svg").status_code == 200
    api = client.get("/api/v1/health")
    assert api.json() == {"status": "ok"} and api.headers["content-security-policy"].startswith("default-src 'none'")
    assert client.get("/api/v1/no-such-thing").status_code == 404
    assert "id=root" in client.get("/../../etc/passwd").text  # never a file outside the website
