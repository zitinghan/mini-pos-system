import json
import logging
import os
import time
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, OperationalError
from app.database.db import transaction
from app.api.routes import router

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger('keke.api')
app = FastAPI(title='KEKE WANTAN MEE POS', version='1.0.0',
    docs_url='/api/docs', openapi_url='/api/openapi.json', redoc_url='/api/redoc')
origins = [o.strip() for o in os.getenv('CORS_ORIGINS', 'http://localhost:5173').split(',') if o.strip()]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_methods=['GET', 'POST', 'PATCH', 'PUT', 'DELETE'], allow_headers=['Authorization', 'Content-Type', 'Idempotency-Key'])
app.include_router(router)

@app.middleware('http')
async def log_request(request: Request, call_next):
    start = time.monotonic()
    response = await call_next(request)
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Cache-Control'] = 'no-store'
    logger.info(json.dumps({'event': 'request', 'method': request.method, 'path': request.url.path,
        'status': response.status_code, 'duration_ms': int((time.monotonic()-start)*1000)}))
    return response

@app.exception_handler(IntegrityError)
async def integrity_error(request, exception):
    return JSONResponse(status_code=409, content={'detail': 'Concurrent update conflicts with current state; refresh and retry'})

@app.exception_handler(OperationalError)
async def database_error(request, exception):
    logger.error(json.dumps({'event': 'database_unavailable', 'error': str(exception)}))
    return JSONResponse(status_code=503, content={'detail': 'Database busy or unavailable; retry the same request key'})

@app.get('/api/health')
def health():
    with transaction() as db:
        db.execute(text('SELECT 1 FROM restaurant_tables LIMIT 1'))
    return {'status': 'ok', 'service': 'keke-pos'}
