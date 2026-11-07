"""Serve the built POS frontend and API together on this Windows PC."""
import os
from pathlib import Path
import sys

from starlette.exceptions import HTTPException
from starlette.staticfiles import StaticFiles

ROOT = Path(__file__).resolve().parents[1]


def listen_address():
    return os.environ.get('POS_BIND_ADDRESS', '0.0.0.0')


class FrontendFiles(StaticFiles):
    async def get_response(self, path, scope):
        # Starlette normalizes paths with Windows backslashes on this platform.
        url_path = path.replace('\\', '/').lstrip('/')
        if url_path == 'api' or url_path.startswith('api/'):
            raise HTTPException(status_code=404)
        try:
            return await super().get_response(path, scope)
        except HTTPException as error:
            if error.status_code == 404 and '.' not in url_path.rsplit('/', 1)[-1]:
                return await super().get_response('index.html', scope)
            raise


if __name__ == '__main__':
    os.chdir(ROOT / 'backend')
    sys.path.insert(0, str(ROOT / 'backend'))
    import uvicorn
    from app.main import app

    app.mount('/', FrontendFiles(directory=ROOT / 'frontend' / 'dist', html=True), name='frontend')
    uvicorn.run(app, host=listen_address(), port=8080, log_config=None)
