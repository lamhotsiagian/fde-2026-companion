from fastapi import FastAPI

from app.auth.routes import auth_router
from app.chat.routes import chat_router
from app.documents.routes import document_router
from app.lifespan import lifespan
from app.middleware import register_middleware
from app.threads.routes import thread_router
from app.users.routes import user_router
from app.memory.routes import memory_router
from app.course.routes import course_router
from app.ingestion.routes import ingestion_router
from app.websocket.routes import websocket_router
from app.evaluation.routes import evaluation_router
from app.monitoring.routes import monitoring_router
from app.analytics.routes import analytics_router
from app.api.health import health_router

version = "v1"
version_prefix = f"/api/{version}"

app = FastAPI(
    title="RAG Chatbot API",
    description="RAG Chatbot API",
    version=version,
    openapi_url=f"{version_prefix}/openapi.json",
    docs_url=f"{version_prefix}/docs",
    redoc_url=f"{version_prefix}/redoc",
    lifespan=lifespan,
    license_info={"name": "MIT License", "url": "https://opensource.org/license/mit"},
)

register_middleware(app)

app.include_router(health_router, tags=["HEALTH"])
app.include_router(auth_router, prefix=f"{version_prefix}/auth", tags=["AUTH"])
app.include_router(user_router, prefix=f"{version_prefix}/users", tags=["USERS"])
app.include_router(thread_router, prefix=f"{version_prefix}/threads", tags=["THREADS"])
app.include_router(chat_router, prefix=f"{version_prefix}/chat", tags=["CHAT"])
app.include_router(document_router, prefix=f"{version_prefix}/documents", tags=["DOCUMENTS"])
app.include_router(ingestion_router, prefix=f"{version_prefix}/ingestion", tags=["INGESTION"])
app.include_router(websocket_router, prefix=f"{version_prefix}/realtime", tags=["REALTIME"])
app.include_router(evaluation_router, prefix=f"{version_prefix}/evaluation", tags=["EVALUATION"])
app.include_router(monitoring_router, prefix=f"{version_prefix}/monitoring", tags=["MONITORING"])
app.include_router(analytics_router, prefix=f"{version_prefix}/analytics", tags=["ANALYTICS"])
app.include_router(memory_router, prefix=f"{version_prefix}/memory", tags=["MEMORY"])
app.include_router(course_router, prefix=f"{version_prefix}/course", tags=["COURSE"])

