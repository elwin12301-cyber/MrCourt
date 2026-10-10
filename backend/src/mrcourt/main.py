from urllib.parse import urlparse

from fastapi import APIRouter, FastAPI, Request
from fastapi.responses import JSONResponse

from mrcourt.config import get_settings
from mrcourt.logging_config import configure_logging

API_PREFIX = "/api/v1"
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    # The API only returns data and files, never pages, so nothing may be framed or scripted.
    "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'",
    # Voice input uses the microphone from our own pages only.
    "Permissions-Policy": "microphone=(self), camera=(), geolocation=()",
}


def _routers() -> list[APIRouter]:
    """Routers are imported lazily so each story's module can be added independently."""
    routers: list[APIRouter] = []
    for module_name in (
        "auth",
        "me",
        "questions",
        "cases",
        "dashboard",
        "client",
        "client_admin",
        "glossary",
        "drafts",
        "admin",
        "assistant",
        "knowledge",
        "history",
        "speech",
        "text",
        "dev",
    ):
        try:
            module = __import__(f"mrcourt.api.{module_name}", fromlist=["router"])
        except ModuleNotFoundError as exc:
            if exc.name != f"mrcourt.api.{module_name}":
                raise
            continue
        routers.append(module.router)
    return routers


def create_app() -> FastAPI:
    configure_logging()
    app = FastAPI(title="MrCourt API", version="1.0.0", docs_url="/api/docs")

    @app.get(f"{API_PREFIX}/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.middleware("http")
    async def protect(request: Request, call_next):  # type: ignore[no-untyped-def]
        # Cross-site request forgery: browsers always send Origin on writes, so a write whose
        # Origin is not this site is refused. (Cookies are also SameSite=Lax.)
        if request.method not in SAFE_METHODS:
            origin = request.headers.get("origin")
            allowed = {o.strip().rstrip("/") for o in get_settings().allowed_origins.split(",") if o.strip()}
            same_host = origin is not None and urlparse(origin).netloc == request.headers.get("host", "")
            if origin and not same_host and origin.rstrip("/") not in allowed:
                return JSONResponse({"detail": "Cross-origin request refused"}, status_code=403)
        response = await call_next(request)
        for name, value in SECURITY_HEADERS.items():
            response.headers.setdefault(name, value)
        return response

    for router in _routers():
        app.include_router(router, prefix=API_PREFIX)
    return app


app = create_app()
