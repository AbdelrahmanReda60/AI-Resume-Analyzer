import logging
import time

from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.exceptions import RequestValidationError
from app.database import engine, Base, SessionLocal
from app.core.exceptions import http_exception_handler, validation_exception_handler, generic_exception_handler
from app.api import auth, resumes, jobs, recommendations, improvements, chat, kb
from app.services.vector_store import seed_knowledge_base_if_empty
from app.api.jobs import seed_jobs_if_empty

LOG_FORMAT = "%(asctime)s %(levelname)-8s %(name)s: %(message)s"
logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logger = logging.getLogger("ai_resume_analyzer")

# Paths whose query string may contain a search term only (never secrets).
# The middleware below logs method/path/status/duration and deliberately
# omits headers, bodies, and query strings so tokens/passwords are never logged.
def _scrub_path(path: str) -> str:
    return path if len(path) <= 120 else path[:117] + "..."

# Initialize Database Tables
Base.metadata.create_all(bind=engine)

# Seed initial Knowledge Base and Jobs
db = SessionLocal()
try:
    seed_knowledge_base_if_empty(db)
    seed_jobs_if_empty(db)
finally:
    db.close()

# Create FastAPI App
app = FastAPI(
    title="AI Resume Analyzer API",
    description="Automated resume parsing, AI job matching, and RAG career advisor API.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Exception Handlers
app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(Exception, generic_exception_handler)


# Hardening headers. A strict Content-Security-Policy is deliberately omitted:
# the frontend is same-origin vanilla JS with no external resources, and an
# over-tight CSP would only risk breaking pages without adding much here.
SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "same-origin",
    "Cross-Origin-Opener-Policy": "same-origin",
}


@app.middleware("http")
async def request_middleware(request: Request, call_next):
    """Attach hardening headers, then log API method/path/status/duration only.

    Headers (including Authorization), request bodies, and query strings are
    intentionally never logged so JWTs, passwords, and file contents cannot
    leak into the log file.
    """
    path = request.url.path
    is_api = path.startswith("/api")
    started = time.perf_counter()
    status_code = 500
    try:
        response = await call_next(request)
        status_code = response.status_code
        for header, value in SECURITY_HEADERS.items():
            response.headers.setdefault(header, value)
        return response
    finally:
        if is_api:
            duration_ms = (time.perf_counter() - started) * 1000
            level = logging.WARNING if status_code >= 400 else logging.INFO
            logger.log(
                level,
                "%s %s -> %d (%.1fms)",
                request.method,
                _scrub_path(path),
                status_code,
                duration_ms,
            )

# Include API Routers
app.include_router(auth.router, prefix="/api")
app.include_router(resumes.router, prefix="/api")
app.include_router(jobs.router, prefix="/api")
app.include_router(recommendations.router, prefix="/api")
app.include_router(improvements.router, prefix="/api")
app.include_router(chat.router, prefix="/api")
app.include_router(kb.router, prefix="/api")

# Serve Frontend Static Files at /
app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")


@app.on_event("startup")
async def log_startup() -> None:
    from app.config import settings
    from app.services.llm_client import llm_available

    logger.info("AI Resume Analyzer started")
    logger.info("LLM provider gemini-2.5-flash: %s",
                "enabled" if llm_available() else "DISABLED (rule-based fallback active)")
    logger.info("KB data dir: %s", settings.KB_DATA_DIR)
    if settings.SECRET_KEY == "super-secret-jwt-key-for-ai-cv-analyzer-2026":
        logger.warning(
            "SECRET_KEY is still the development default — set a unique value in .env "
            "before deploying; anyone could otherwise forge tokens."
        )
