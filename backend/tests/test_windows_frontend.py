"""Check native frontend routing without requiring a production frontend build."""
from pathlib import Path
import runpy

import pytest
from starlette.applications import Starlette
from starlette.routing import Mount
from starlette.testclient import TestClient

FrontendFiles = runpy.run_path(
    str(Path(__file__).resolve().parents[2] / 'scripts' / 'windows_server.py')
)['FrontendFiles']


def test_windows_server_allows_lan_connections_by_default(monkeypatch):
    monkeypatch.delenv('POS_BIND_ADDRESS', raising=False)
    server = runpy.run_path(str(Path(__file__).resolve().parents[2] / 'scripts' / 'windows_server.py'))
    assert server['listen_address']() == '0.0.0.0'


def test_windows_server_can_be_restricted_to_localhost(monkeypatch):
    monkeypatch.setenv('POS_BIND_ADDRESS', '127.0.0.1')
    server = runpy.run_path(str(Path(__file__).resolve().parents[2] / 'scripts' / 'windows_server.py'))
    assert server['listen_address']() == '127.0.0.1'


@pytest.fixture
def frontend_client(tmp_path):
    (tmp_path / 'index.html').write_text('<main>POS frontend</main>', encoding='utf-8')
    (tmp_path / 'app.js').write_text('window.pos = true;', encoding='utf-8')
    app = Starlette(routes=[Mount('/', app=FrontendFiles(directory=tmp_path, html=True))])
    with TestClient(app) as client:
        yield client


@pytest.mark.parametrize('path', ['/', '/session/5', '/settings'])
def test_frontend_navigation_serves_application(frontend_client, path):
    response = frontend_client.get(path)
    assert response.status_code == 200
    assert response.text == '<main>POS frontend</main>'


@pytest.mark.parametrize('path', ['/api/unknown', '/api', '/assets/missing.js'])
def test_missing_api_and_assets_remain_not_found(frontend_client, path):
    assert frontend_client.get(path).status_code == 404


def test_existing_frontend_assets_are_served(frontend_client):
    response = frontend_client.get('/app.js')
    assert response.status_code == 200
    assert response.text == 'window.pos = true;'
