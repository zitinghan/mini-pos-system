from datetime import datetime, timezone
from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from app.database.db import transaction
from app.models.entities import AuthSession, User
from app.core.credentials import hash_pin as hash_pin, verify_pin as verify_pin, token_hash


def current_user(request: Request):
    token = request.headers.get('Authorization', '').removeprefix('Bearer ')
    with transaction() as db:
        session = db.scalar(select(AuthSession).where(AuthSession.token_hash == token_hash(token)))
        if not session or session.expires_at <= datetime.now(timezone.utc).isoformat():
            raise HTTPException(401, 'Session expired; please sign in')
        user = db.get(User, session.user_id)
        return {'id': user.id, 'name': user.name, 'role': user.role}


def admin(user=Depends(current_user)):
    if user['role'] != 'ADMIN':
        raise HTTPException(403, 'Cashier/admin permission required')
    return user
