"""Login/logout de sesion (H4)."""

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from src.api.deps import SESSION_COOKIE_NAME, require_session
from src.api.schemas import LoginRequest, MeResponse
from src.api.session_store import create_session, delete_session
from src.core.repositories.audit_log_repository import record_event
from src.core.settings import AUTHORIZED_EMAIL, Settings, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", status_code=status.HTTP_200_OK)
def login(payload: LoginRequest, response: Response):
    stored_hash = Settings().get_password_hash()
    valido = (
        stored_hash is not None
        and payload.email == AUTHORIZED_EMAIL
        and verify_password(payload.password, stored_hash)
    )
    if not valido:
        record_event("login_failure", email=payload.email)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciales invalidas.")

    token = create_session(payload.email)
    record_event("login_success", email=payload.email)
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="lax",
        secure=False,  # ponytail: sin TLS en localhost; cambiar a True cuando exista despliegue real
        max_age=8 * 3600,
    )
    return {"email": payload.email}


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: Request, response: Response, email: str = Depends(require_session)):
    token = request.cookies.get(SESSION_COOKIE_NAME)
    delete_session(token)
    record_event("logout", email=email)
    response.delete_cookie(SESSION_COOKIE_NAME)
    return None


@router.get("/me", response_model=MeResponse)
def me(email: str = Depends(require_session)):
    return MeResponse(email=email)
