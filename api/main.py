from contextlib import asynccontextmanager
import logging
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse
from db.database import init_db
from rag.vectorstore import warmup
from config.settings import settings
from api.routes import interview, sessions, reports, audit as audit_router
from api.routes import admin as admin_router
from api.websocket import ws_router


logger = logging.getLogger(__name__)


def _validate_bedrock_settings() -> None:
    """Warn when Nova models are configured without an inference profile."""
    uses_nova = any(
        "nova" in model_id.lower()
        for model_id in [settings.bedrock_nova_lite_model_id, settings.bedrock_nova_pro_model_id]
        if model_id
    )
    if uses_nova and not settings.bedrock_inference_profile_id:
        logger.warning(
            "BEDROCK_INFERENCE_PROFILE_ID is not set while Nova text models are configured. "
            "Answer evaluation may fail unless your account supports on-demand throughput for the model."
        )

    if settings.bedrock_inference_profile_id:
        logger.info("Using Bedrock inference profile for text models.")


@asynccontextmanager
async def lifespan(app: FastAPI):
    _validate_bedrock_settings()
    await init_db()
    warmup()  # C1: pre-load ChromaDB HNSW index before first request
    yield


app = FastAPI(title="AI Interviewer MVP", version="0.1.0", lifespan=lifespan)

app.mount("/static", StaticFiles(directory="ui/static"), name="static")

app.include_router(interview.router,    prefix="/interview", tags=["interview"])
app.include_router(sessions.router,     prefix="/sessions",  tags=["sessions"])
app.include_router(reports.router,      prefix="/reports",   tags=["reports"])
app.include_router(audit_router.router, prefix="/audit",     tags=["audit"])
app.include_router(admin_router.router, prefix="/admin",     tags=["admin"])
app.include_router(ws_router)


@app.get("/")
async def index(request: Request):
    return FileResponse("ui/templates/index.html", media_type="text/html")


@app.get("/admin")
async def admin_page(request: Request):
    return FileResponse("ui/templates/admin.html", media_type="text/html")


@app.get("/report/{session_id}")
async def report_page(request: Request, session_id: str):
    # Read the template and inject session_id
    template_path = Path("ui/templates/report.html")
    html_content = template_path.read_text(encoding="utf-8")
    html_content = html_content.replace("{{ session_id }}", session_id)
    return HTMLResponse(content=html_content)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
