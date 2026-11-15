"""
Backend privado de cubiApp (H4): FastAPI local, un unico usuario autorizado.

Arranque: `uvicorn src.api.app:create_app --factory`. Requiere haber
ejecutado antes `python scripts/set_password.py` (falla al arrancar si no
hay contrasena configurada).
"""

from fastapi import FastAPI

from src.api.auth_router import router as auth_router
from src.api.budgets_router import router as budgets_router
from src.api.traceability_router import router as traceability_router
from src.core.settings import Settings


def create_app() -> FastAPI:
    if Settings().get_password_hash() is None:
        raise RuntimeError(
            "No hay contrasena configurada. Ejecuta `python scripts/set_password.py` antes de arrancar."
        )

    app = FastAPI(title="cubiApp backend privado")
    app.include_router(auth_router)
    app.include_router(budgets_router)
    app.include_router(traceability_router)

    @app.get("/health")
    def health():
        return {"status": "ok"}

    return app
