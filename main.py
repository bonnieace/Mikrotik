"""Canonical application entry point.

The legacy control-plane remains implemented in ``mono`` while self-service authentication
is mounted here so production, CI, and local runs share the same application object.
"""

from fastapi import Depends
from fastapi.security import OAuth2PasswordRequestForm

import mono
from services.registration_service import login as verified_login
from services.registration_service import router as registration_router


app = mono.app
pwd_context = mono.pwd_context


def _remove_route(path: str, method: str) -> None:
    app.router.routes[:] = [
        route
        for route in app.router.routes
        if not (
            getattr(route, "path", None) == path
            and method in (getattr(route, "methods", None) or set())
        )
    ]


# Replace the earlier self-registration endpoint and versioned login with the verified flow.
_remove_route("/api/v1/auth/register", "POST")
_remove_route("/api/v1/auth/token", "POST")
_remove_route("/token", "POST")
app.include_router(registration_router)


@app.post("/token", include_in_schema=False)
async def legacy_login(form_data: OAuth2PasswordRequestForm = Depends()):
    return await verified_login(form_data)


__all__ = ["app", "pwd_context"]
