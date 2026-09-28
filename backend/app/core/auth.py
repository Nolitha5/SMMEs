from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status

from app.core.config import Settings, get_settings


@dataclass(frozen=True)
class UserPrincipal:
    uid: str
    email: str
    role: str


def _verify_firebase_token(token: str, settings: Settings) -> UserPrincipal:
    try:
        from firebase_admin import auth
    except ImportError as exc:
        raise HTTPException(status_code=500, detail="firebase-admin is required when AUTH_MODE=firebase") from exc

    from app.core.firebase_app import ensure_firebase_app

    ensure_firebase_app(settings)
    try:
        decoded = auth.verify_id_token(token)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Firebase token") from exc
    email = decoded.get("email", "")
    role = decoded.get("role", "owner_manager")
    return UserPrincipal(uid=decoded["uid"], email=email, role=role)


async def current_user(
    authorization: Annotated[str | None, Header()] = None,
    x_demo_user: Annotated[str | None, Header()] = None,
    settings: Settings = Depends(get_settings),
) -> UserPrincipal:
    if settings.auth_mode.lower() == "demo":
        email = x_demo_user or settings.demo_manager_email
        return UserPrincipal(uid=f"demo:{email}", email=email, role="owner_manager")
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Bearer token required")
    return _verify_firebase_token(authorization.split(" ", 1)[1], settings)


def require_manager(user: UserPrincipal = Depends(current_user)) -> UserPrincipal:
    if user.role not in {"owner_manager", "admin", "procurement_manager"}:
        raise HTTPException(status_code=403, detail="Procurement manager role required")
    return user
