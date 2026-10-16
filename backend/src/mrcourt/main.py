import logging
import threading
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlparse

from fastapi import APIRouter, FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from mrcourt.config import get_settings
from mrcourt.logging_config import configure_logging

API_PREFIX = "/api/v1"
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    # Voice input uses the microphone from our own pages only.
    "Permissions-Policy": "microphone=(self), camera=(), geolocation=()",
}


# The API only returns data and files, never pages, so nothing may be framed or scripted.
API_CSP = "default-src 'none'; frame-ancestors 'none'"
# The website's pages: our own scripts, Google Fonts, and downloads made in the browser.
PAGE_CSP = (
    "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
    "font-src 'self' https://fonts.gstatic.com; img-src 'self' data: blob:; media-src 'self' blob:; "
    "connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
)

logger = logging.getLogger(__name__)


def _reminder_loop(minutes: int, stop: threading.Event) -> None:
    """Sends due hearing reminders every few minutes (for hosts without a scheduler)."""
    from mrcourt.db.base import get_sessionmaker
    from mrcourt.services.reminders import send_due_reminders

    while not stop.is_set():
        session = get_sessionmaker()()
        try:
            count = send_due_reminders(session)
            session.commit()
            logger.info("Reminder run sent %d message(s)", count)
        except Exception:  # noqa: BLE001 - a failed run is tried again next time
            session.rollback()
            logger.warning("Reminder run failed", exc_info=True)
        finally:
            session.close()
        stop.wait(minutes * 60)


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    minutes = get_settings().reminder_interval_minutes
    stop = threading.Event()
    if minutes > 0:
        threading.Thread(target=_reminder_loop, args=(minutes, stop), daemon=True, name="reminders").start()
        from mrcourt.services.whatsapp import jobs as whatsapp_jobs  # nudges and retries need a shorter beat

        threading.Thread(target=whatsapp_jobs.flush_loop, args=(stop,), daemon=True, name="whatsapp").start()
    yield
    stop.set()


def _serve_website(app: FastAPI, dist: Path) -> None:
    """Serves the built React app; any path that is not a file or the API gets index.html."""
    if (dist / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")
    index = dist / "index.html"

    @app.get("/{path:path}", include_in_schema=False)
    def website(path: str) -> FileResponse:
        if path.startswith("api/"):
            return JSONResponse({"detail": "Not Found"}, status_code=404)  # type: ignore[return-value]
        candidate = (dist / path).resolve()
        if path and candidate.is_file() and dist.resolve() in candidate.parents:
            return FileResponse(candidate)
        return FileResponse(index, headers={"Cache-Control": "no-cache"})


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
        "whatsapp",
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
    app = FastAPI(title="MrCourt API", version="1.0.0", docs_url="/api/docs", lifespan=_lifespan)

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
        is_api = request.url.path.startswith("/api/")
        response.headers.setdefault("Content-Security-Policy", API_CSP if is_api else PAGE_CSP)
        return response

    for router in _routers():
        app.include_router(router, prefix=API_PREFIX)
    dist = get_settings().frontend_dist
    if dist and (Path(dist) / "index.html").is_file():
        _serve_website(app, Path(dist))
    return app


app = create_app()
