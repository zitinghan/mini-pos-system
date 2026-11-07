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
