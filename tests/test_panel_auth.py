from __future__ import annotations

import base64
import io
from pathlib import Path
from types import SimpleNamespace

import pytest

from job_panel_server import PanelAuthConfig, check_basic_auth, load_panel_auth_config, require_panel_auth, validate_panel_auth_config


class DummyHandler:
    def __init__(self, authorization: str | None, auth_config: PanelAuthConfig):
        self.headers = {}
        if authorization is not None:
            self.headers["Authorization"] = authorization
        self.server = SimpleNamespace(panel_auth=auth_config)
        self.status = None
        self.response_headers: list[tuple[str, str]] = []
        self.ended = False
        self.wfile = io.BytesIO()

    def send_response(self, status):  # noqa: D401 - assinatura compatível com BaseHTTPRequestHandler
        self.status = status

    def send_header(self, key, value):
        self.response_headers.append((key, value))

    def end_headers(self):
        self.ended = True


def _basic_auth_header(username: str, password: str) -> str:
    token = base64.b64encode(f"{username}:{password}".encode("utf-8")).decode("ascii")
    return f"Basic {token}"


def _enabled_auth() -> PanelAuthConfig:
    return PanelAuthConfig(username="usuario-local", password="senha-forte-local")


def test_missing_authorization_returns_401_when_auth_is_active():
    handler = DummyHandler(None, _enabled_auth())

    allowed = require_panel_auth(handler, handler.server.panel_auth)

    assert allowed is False
    assert handler.status == 401
    assert ("WWW-Authenticate", 'Basic realm="job-hunter-panel", charset="UTF-8"') in handler.response_headers
    assert handler.wfile.getvalue() == b"Authentication required\n"


def test_invalid_authorization_returns_401():
    handler = DummyHandler("Basic not-valid-base64", _enabled_auth())

    allowed = require_panel_auth(handler, handler.server.panel_auth)

    assert allowed is False
    assert handler.status == 401


def test_correct_authorization_allows_access():
    auth = _enabled_auth()
    handler = DummyHandler(_basic_auth_header(auth.username, auth.password), auth)

    allowed = require_panel_auth(handler, handler.server.panel_auth)

    assert allowed is True
    assert handler.status is None
    assert handler.response_headers == []


def test_auth_disabled_allows_access_without_header():
    auth = PanelAuthConfig(auth_disabled=True)
    handler = DummyHandler(None, auth)

    allowed = require_panel_auth(handler, handler.server.panel_auth)

    assert allowed is True
    assert handler.status is None


def test_missing_credentials_raise_clear_error():
    auth = load_panel_auth_config(project_dir=Path("/tmp/does-not-exist"), environ={})

    with pytest.raises(RuntimeError, match="JOB_HUNTER_PANEL_USER"):
        validate_panel_auth_config(auth)


def test_check_basic_auth_matches_credentials_safely():
    auth = _enabled_auth()
    header = _basic_auth_header(auth.username, auth.password)

    assert check_basic_auth(header, auth.username, auth.password) is True
    assert check_basic_auth(header, auth.username, "senha-errada") is False
    assert check_basic_auth(None, auth.username, auth.password) is False


def test_load_panel_auth_config_prefers_explicit_env():
    env = {
        "JOB_HUNTER_PANEL_USER": "usuario-env",
        "JOB_HUNTER_PANEL_PASSWORD": "senha-env",
    }
    auth = load_panel_auth_config(project_dir=Path("/tmp/does-not-exist"), environ=env)

    assert auth.username == "usuario-env"
    assert auth.password == "senha-env"


def test_load_panel_auth_config_reads_local_config_when_env_is_missing(tmp_path):
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        "panel_auth:\n  username: usuario-local\n  password: senha-local\n",
        encoding="utf-8",
    )

    auth = load_panel_auth_config(project_dir=tmp_path, environ={})

    assert auth.source == "config"
    assert auth.username == "usuario-local"
    assert auth.password == "senha-local"
