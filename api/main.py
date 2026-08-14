from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from db.database import init_db
from rag.vectorstore import warmup
from api.routes import interview, sessions, reports, audit as audit_router
from api.routes import admin as admin_router
from api.websocket import ws_router


@asynccontextmanager
async def lifespan(app: FastAPI):
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
    return FileResponse("ui/templates/report.html", media_type="text/html")
