from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.routes.scam_exposure import router as scam_router
from app.api.v1.routes.data_generator import router as datagen_router
from app.api.v1.routes.sharing import router as sharing_router
from app.api.v1.routes.datasets import router as datasets_router
from app.api.v1.routes.agent_routes import router as agent_router
from app.core.sharing_config import SHARING_CONFIG
from app.core.database import init_db

app = FastAPI(title="AEGIS-AML", version="0.1.0")

@app.on_event("startup")
def on_startup() -> None:
    init_db()

app.add_middleware(
	CORSMiddleware,
	allow_origins=SHARING_CONFIG.cors_origins,
	allow_credentials=not SHARING_CONFIG.is_cors_wildcard,
	allow_methods=["*"],
	allow_headers=["*"],
)

app.include_router(scam_router)
app.include_router(datagen_router)
app.include_router(sharing_router)
app.include_router(datasets_router)
app.include_router(agent_router)


@app.get("/")
def root() -> dict[str, str]:
	return {
		"service": "AEGIS-AML",
		"status": "running",
		"docs": "/docs",
		"health": "/api/v1/health",
	}


@app.get("/api")
def api_index() -> dict[str, str]:
	safety = "enabled" if SHARING_CONFIG.require_api_key else "disabled"
	return {
		"health": "/api/v1/health",
		"scam_exposure": "/api/v1/scam-exposure",
		"feedback": "/api/v1/feedback",
		"weights": "/api/v1/weights",
		"generate_data": "/api/v1/generate-data",
		"generate_data_save": "/api/v1/generate-data/save",
		"generate_data_schemas": "/api/v1/generate-data/schemas",
		"datasets": "/api/v1/datasets",
		"dataset_analytics": "/api/v1/datasets/{dataset_id}/analytics",
		"ml_predict": "/api/v1/ml/predict",
		"ml_info": "/api/v1/ml/info",
		"llm_chat": "/api/v1/llm/chat",
		"llm_chat_history": "/api/v1/llm/chat-history",
		"llm_status": "/api/v1/llm/status",
		"nlp_analyze": "/api/v1/nlp/analyze",
		"session_rules": "/api/v1/session-rules",
		"api_key_protection": safety,
	}
